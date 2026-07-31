"""
NicePay (나이스페이) authenticated payment (인증결제) integration.

Reference: https://developers.nicepay.co.kr/manual-auth.php

The authenticated payment flow is two-phase:

  1. Authentication (인증) - the browser opens the NicePay payment window via
     ``goPay(form)`` from ``nicepay-pgweb.js``. The payer authenticates with
     their card issuer / bank. NicePay then POSTs the authentication result to
     the merchant server (the form target on PC, ``ReturnURL`` on mobile).

  2. Approval (승인) - the merchant server verifies the authentication result
     and POSTs it to ``NextAppURL`` to actually capture the money. If that call
     fails at the network level the merchant MUST issue a net-cancel (망취소)
     against ``NetCancelURL`` so the transaction is not left dangling.

All hashes are ``hex(sha256(...))`` over the concatenated plaintext, with the
merchant key last. The exact field order differs per message and is enforced by
the dedicated helpers below - do not inline these formulas elsewhere.
"""

import hashlib
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# JS SDK that provides goPay() / nicepaySubmit().
JS_SDK_URL = 'https://pg-web.nicepay.co.kr/v3/common/js/nicepay-pgweb.js'

# Payment methods accepted by the payment window (PayMethod).
PAY_METHOD_CARD = 'CARD'
PAY_METHOD_BANK = 'BANK'
PAY_METHOD_VBANK = 'VBANK'
PAY_METHOD_CELLPHONE = 'CELLPHONE'
PAY_METHODS = (PAY_METHOD_CARD, PAY_METHOD_BANK, PAY_METHOD_VBANK, PAY_METHOD_CELLPHONE)

# AuthResultCode indicating a successful authentication.
AUTH_SUCCESS_CODE = '0000'

# ResultCode values indicating a successful approval, keyed by PayMethod.
APPROVAL_SUCCESS_CODES = {
    PAY_METHOD_CARD: '3001',       # 신용카드
    PAY_METHOD_BANK: '4000',       # 계좌이체
    PAY_METHOD_VBANK: '4100',      # 가상계좌 발급
    PAY_METHOD_CELLPHONE: 'A000',  # 휴대폰 소액결제
}

# ResultCode indicating a successful cancellation.
CANCEL_SUCCESS_CODE = '2001'

# Human readable payment type per PayMethod, matching the Korean labels the
# rest of the codebase already stores in PaymentHistory.payment_type.
PAY_METHOD_LABELS = {
    PAY_METHOD_CARD: '카드',
    PAY_METHOD_BANK: '계좌이체',
    PAY_METHOD_VBANK: '가상계좌',
    PAY_METHOD_CELLPHONE: '휴대폰',
}

# NextAppURL / NetCancelURL arrive inside an unauthenticated POST body, so they
# are attacker-controlled. Only ever call back into hosts NicePay documents,
# otherwise the callback becomes an SSRF primitive that leaks our merchant key
# hash to an arbitrary server.
ALLOWED_API_HOSTS = {
    'dc1-api.nicepay.co.kr',
    'dc2-api.nicepay.co.kr',
    'pg-api.nicepay.co.kr',
    'webapi.nicepay.co.kr',
}

# Approval/cancel APIs are documented as euc-kr. Responses may come back in
# either encoding depending on the CharSet we request, so decode defensively.
_RESPONSE_ENCODINGS = ('utf-8', 'euc-kr', 'cp949')

_TIMEOUT = 30


class NicePayError(Exception):
    """Raised when a NicePay API call cannot be completed or is rejected."""

    def __init__(self, message, code='nicepay_error', response=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.response = response or {}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def is_configured():
    """True when the merchant credentials required to transact are present."""
    return bool(settings.NICEPAY_MID and settings.NICEPAY_MERCHANT_KEY)


def _merchant_key():
    if not is_configured():
        raise NicePayError('NicePay is not configured.', code='config_error')
    return settings.NICEPAY_MERCHANT_KEY


def now_edi_date():
    """Current timestamp in the EdiDate format NicePay expects (YYYYMMDDHHMMSS)."""
    return datetime.now().strftime('%Y%m%d%H%M%S')


# ---------------------------------------------------------------------------
# Signatures
#
# Each message type hashes a different field order. Keeping them as separate
# named functions makes the formulas auditable against the manual.
# ---------------------------------------------------------------------------

def _sha256_hex(*parts):
    return hashlib.sha256(''.join(parts).encode('utf-8')).hexdigest()


def window_sign_data(edi_date, amt, mid=None):
    """SignData for the payment window request: sha256(EdiDate + MID + Amt + MerchantKey)."""
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(str(edi_date), mid, str(amt), _merchant_key())


def auth_signature(auth_token, amt, mid=None):
    """Expected Signature on the authentication response: sha256(AuthToken + MID + Amt + MerchantKey).

    Note this one does NOT include EdiDate, unlike the approval request below.
    """
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(str(auth_token), mid, str(amt), _merchant_key())


def approval_sign_data(auth_token, amt, edi_date, mid=None):
    """SignData for the approval request: sha256(AuthToken + MID + Amt + EdiDate + MerchantKey)."""
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(str(auth_token), mid, str(amt), str(edi_date), _merchant_key())


def approval_signature(tid, amt, mid=None):
    """Expected Signature on the approval response: sha256(TID + MID + Amt + MerchantKey)."""
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(str(tid), mid, str(amt), _merchant_key())


def cancel_sign_data(cancel_amt, edi_date, mid=None):
    """SignData for the cancel request: sha256(MID + CancelAmt + EdiDate + MerchantKey)."""
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(mid, str(cancel_amt), str(edi_date), _merchant_key())


def cancel_signature(tid, cancel_amt, mid=None):
    """Expected Signature on the cancel response: sha256(TID + MID + CancelAmt + MerchantKey)."""
    mid = mid or settings.NICEPAY_MID
    return _sha256_hex(str(tid), mid, str(cancel_amt), _merchant_key())


def _constant_time_equals(a, b):
    return hashlib.sha256((a or '').encode()).digest() == hashlib.sha256((b or '').encode()).digest()


def verify_auth_response(params):
    """Verify the Signature on an authentication response.

    ``Amt`` is compared exactly as NicePay sent it, because the hash is over the
    raw string. Returns True when the signature matches (or when NicePay omitted
    it, which happens for some payment methods).
    """
    signature = params.get('Signature', '')
    if not signature:
        return True
    expected = auth_signature(params.get('AuthToken', ''), params.get('Amt', ''), params.get('MID'))
    return _constant_time_equals(signature, expected)


def verify_approval_response(params):
    """Verify the Signature on an approval response."""
    signature = params.get('Signature', '')
    if not signature:
        return True
    expected = approval_signature(params.get('TID', ''), params.get('Amt', ''), params.get('MID'))
    return _constant_time_equals(signature, expected)


# ---------------------------------------------------------------------------
# Payment window
# ---------------------------------------------------------------------------

def build_payment_window_params(
    *,
    order_id,
    amount,
    goods_name,
    return_url,
    pay_method=PAY_METHOD_CARD,
    buyer_name='',
    buyer_tel='',
    buyer_email='',
    req_reserved='',
):
    """Build the form fields for ``goPay()``.

    The returned dict is submitted verbatim as a form object by the client. The
    signature is computed here so the merchant key never reaches the browser.
    """
    if pay_method not in PAY_METHODS:
        raise NicePayError(f'Unsupported PayMethod: {pay_method}', code='invalid_pay_method')

    amt = str(int(amount))
    edi_date = now_edi_date()

    params = {
        'MID': settings.NICEPAY_MID,
        'Moid': order_id,
        'Amt': amt,
        'GoodsName': goods_name,
        'PayMethod': pay_method,
        'EdiDate': edi_date,
        'SignData': window_sign_data(edi_date, amt),
        'ReturnURL': return_url,
        # Ask NicePay to send the authentication response back as UTF-8 so the
        # callback does not have to guess at euc-kr form decoding.
        'CharSet': 'utf-8',
        'BuyerName': buyer_name or '',
        'BuyerTel': buyer_tel or '',
        'BuyerEmail': buyer_email or '',
        'ReqReserved': req_reserved or '',
    }
    return params


# ---------------------------------------------------------------------------
# Server-to-server calls
# ---------------------------------------------------------------------------

def _assert_allowed_url(url, field):
    """Reject API URLs that did not come from NicePay."""
    if not url:
        raise NicePayError(f'{field} is missing.', code='missing_url')
    host = (urlparse(url).hostname or '').lower()
    if host not in ALLOWED_API_HOSTS:
        raise NicePayError(f'{field} host is not allowed: {host}', code='untrusted_url')
    return url


def _decode(response):
    """Decode a NicePay response body, tolerating euc-kr and utf-8."""
    raw = response.content
    for encoding in _RESPONSE_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _post_form(url, data, *, encoding='euc-kr'):
    """POST an x-www-form-urlencoded body and parse the JSON response.

    NicePay's APIs are documented as euc-kr, so Korean text (e.g. CancelMsg) is
    percent-encoded in euc-kr rather than utf-8.
    """
    body = '&'.join(
        f'{key}={requests.utils.quote(str(value), safe="", encoding=encoding, errors="replace")}'
        for key, value in data.items()
    )
    response = requests.post(
        url,
        data=body.encode('ascii'),
        headers={'Content-Type': f'application/x-www-form-urlencoded; charset={encoding}'},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()

    text = _decode(response)
    try:
        return json.loads(text)
    except ValueError:
        raise NicePayError(
            'Could not parse NicePay response.',
            code='invalid_response',
            response={'raw': text[:500]},
        )


def approve(*, next_app_url, net_cancel_url, tid, auth_token, amount):
    """Call the approval API to capture an authenticated payment.

    On a network-level failure the transaction may or may not have been approved
    on NicePay's side, so a net-cancel (망취소) is issued before re-raising. That
    is what the manual requires to avoid a 거래대사 불일치 (reconciliation
    mismatch).

    Returns the parsed approval response on success; raises NicePayError
    otherwise.
    """
    _assert_allowed_url(next_app_url, 'NextAppURL')

    amt = str(int(amount))
    edi_date = now_edi_date()
    payload = {
        'TID': tid,
        'AuthToken': auth_token,
        'MID': settings.NICEPAY_MID,
        'Amt': amt,
        'EdiDate': edi_date,
        'SignData': approval_sign_data(auth_token, amt, edi_date),
        'CharSet': 'utf-8',
        'EdiType': 'JSON',
    }

    try:
        result = _post_form(next_app_url, payload)
    except (requests.RequestException, NicePayError) as exc:
        # The approval outcome is unknown - undo it defensively.
        logger.error('NicePay approval call failed for tid=%s: %s', tid, exc)
        net_cancel(
            net_cancel_url=net_cancel_url,
            tid=tid,
            auth_token=auth_token,
            amount=amt,
            edi_date=edi_date,
            sign_data=payload['SignData'],
        )
        raise NicePayError(
            'Failed to reach the payment service. The payment was cancelled.',
            code='approval_unreachable',
        )

    if not verify_approval_response(result):
        logger.error('NicePay approval signature mismatch for tid=%s', tid)
        raise NicePayError(
            'Payment response failed verification.',
            code='signature_mismatch',
            response=result,
        )

    pay_method = result.get('PayMethod', PAY_METHOD_CARD)
    expected_code = APPROVAL_SUCCESS_CODES.get(pay_method)
    result_code = result.get('ResultCode', '')

    if result_code != expected_code:
        logger.error(
            'NicePay approval rejected: tid=%s code=%s msg=%s',
            tid, result_code, result.get('ResultMsg', ''),
        )
        raise NicePayError(
            result.get('ResultMsg') or 'Payment approval was rejected.',
            code=result_code or 'approval_failed',
            response=result,
        )

    return result


def net_cancel(*, net_cancel_url, tid, auth_token, amount, edi_date, sign_data):
    """Issue a net-cancel (망취소) for an approval whose outcome is unknown.

    Best effort: failures here are logged rather than raised, because the caller
    is already handling a more important error.
    """
    try:
        _assert_allowed_url(net_cancel_url, 'NetCancelURL')
    except NicePayError as exc:
        logger.error('Skipping net-cancel for tid=%s: %s', tid, exc)
        return None

    payload = {
        'TID': tid,
        'AuthToken': auth_token,
        'MID': settings.NICEPAY_MID,
        'Amt': str(amount),
        'EdiDate': edi_date,
        'SignData': sign_data,
        'NetCancel': '1',
        'CharSet': 'utf-8',
        'EdiType': 'JSON',
    }

    try:
        result = _post_form(net_cancel_url, payload)
        logger.info(
            'NicePay net-cancel for tid=%s returned code=%s msg=%s',
            tid, result.get('ResultCode'), result.get('ResultMsg'),
        )
        return result
    except (requests.RequestException, NicePayError) as exc:
        logger.error('NicePay net-cancel failed for tid=%s: %s', tid, exc)
        return None


def cancel(*, tid, cancel_amount, reason='관리자 취소', partial=False):
    """Cancel (취소) an approved payment.

    ``partial`` maps to PartialCancelCode: 1 for a partial refund, 0 for a full
    one. Returns the parsed response; raises NicePayError when rejected.
    """
    cancel_amt = str(int(cancel_amount))
    edi_date = now_edi_date()
    payload = {
        'TID': tid,
        'MID': settings.NICEPAY_MID,
        'Moid': '',
        'CancelAmt': cancel_amt,
        'CancelMsg': reason or '관리자 취소',
        'PartialCancelCode': '1' if partial else '0',
        'EdiDate': edi_date,
        'SignData': cancel_sign_data(cancel_amt, edi_date),
        'CharSet': 'utf-8',
        'EdiType': 'JSON',
    }
    # Moid is optional for cancellation; drop it rather than send an empty value.
    payload.pop('Moid')

    try:
        result = _post_form(settings.NICEPAY_CANCEL_API_URL, payload)
    except requests.RequestException as exc:
        logger.error('NicePay cancel request failed for tid=%s: %s', tid, exc)
        raise NicePayError('Failed to connect to the payment service.', code='api_error')

    if result.get('ResultCode') != CANCEL_SUCCESS_CODE:
        logger.error(
            'NicePay cancel rejected: tid=%s code=%s msg=%s',
            tid, result.get('ResultCode'), result.get('ResultMsg'),
        )
        raise NicePayError(
            result.get('ResultMsg') or 'Payment cancellation was rejected.',
            code=result.get('ResultCode') or 'cancel_failed',
            response=result,
        )

    logger.info('NicePay payment cancelled: tid=%s amount=%s', tid, cancel_amt)
    return result
