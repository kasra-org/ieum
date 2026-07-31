import logging
from urllib.parse import urlencode, urljoin

from django.conf import settings
from django.db import transaction as db_transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from main import nicepay
from main.models import NicePayTransaction, PaymentHistory

logger = logging.getLogger(__name__)


def _site_url(request):
    """Origin of the user-facing site, used to build post-payment redirects."""
    if settings.NICEPAY_SITE_URL:
        return settings.NICEPAY_SITE_URL.rstrip('/') + '/'
    return request.build_absolute_uri('/')


def _redirect_success(request, order_id):
    query = urlencode({'provider': 'nicepay', 'orderId': order_id})
    return HttpResponseRedirect(urljoin(_site_url(request), f'payment/success?{query}'))


def _redirect_fail(request, code, message, order_id=''):
    params = {'code': code or 'payment_failed', 'message': message or 'Payment failed'}
    if order_id:
        params['orderId'] = order_id
    return HttpResponseRedirect(urljoin(_site_url(request), f'payment/fail?{urlencode(params)}'))


@csrf_exempt
@require_POST
def nicepay_callback(request):
    """
    Receive the NicePay authentication result and complete the approval.

    Serves both flows: on PC the payment window submits the merchant form to
    this URL, on mobile NicePay redirects here as ReturnURL. Either way the POST
    is cross-site, so it carries no session cookie and nothing in the body may
    be trusted on its own - every value that matters is checked against the
    NicePayTransaction created before the payment window opened.

    Responds with a redirect back into the frontend, since the payer's browser
    is what performed the POST.
    """
    params = request.POST
    order_id = params.get('Moid', '')
    auth_result_code = params.get('AuthResultCode', '')
    auth_result_msg = params.get('AuthResultMsg', '')

    if not order_id:
        logger.error("NicePay callback missing Moid")
        return _redirect_fail(request, 'invalid_callback', 'Invalid payment response.')

    try:
        transaction = NicePayTransaction.objects.select_related('attendee', 'event').get(order_id=order_id)
    except NicePayTransaction.DoesNotExist:
        logger.error("NicePay callback for unknown order_id=%s", order_id)
        return _redirect_fail(request, 'unknown_order', 'Unknown payment request.', order_id)

    # Authentication failed at the card issuer / bank - nothing to approve.
    if auth_result_code != nicepay.AUTH_SUCCESS_CODE:
        logger.info(
            "NicePay authentication failed: order_id=%s code=%s msg=%s",
            order_id, auth_result_code, auth_result_msg,
        )
        NicePayTransaction.objects.filter(pk=transaction.pk, status='pending').update(
            status='failed', result_code=auth_result_code, result_message=auth_result_msg,
        )
        return _redirect_fail(request, auth_result_code or 'auth_failed', auth_result_msg, order_id)

    # Claim the transaction so a replayed callback cannot approve it twice.
    with db_transaction.atomic():
        claimed = NicePayTransaction.objects.filter(pk=transaction.pk, status='pending').update(
            status='authenticated'
        )
    if not claimed:
        # Another callback won the race; re-read rather than trust the copy
        # fetched before the update.
        transaction.refresh_from_db()
        if transaction.status == 'approved':
            logger.info("NicePay callback replayed for approved order_id=%s", order_id)
            return _redirect_success(request, order_id)
        logger.warning(
            "NicePay callback for order_id=%s in unexpected state %s", order_id, transaction.status
        )
        return _redirect_fail(request, 'invalid_state', 'This payment cannot be processed.', order_id)

    def fail(code, message):
        NicePayTransaction.objects.filter(pk=transaction.pk).update(
            status='failed', result_code=code or '', result_message=message or '',
        )
        return _redirect_fail(request, code, message, order_id)

    # Integrity of the authentication response itself.
    if not nicepay.verify_auth_response(params):
        logger.error("NicePay auth signature mismatch: order_id=%s", order_id)
        return fail('signature_mismatch', 'Payment response failed verification.')

    if params.get('MID') != settings.NICEPAY_MID:
        logger.error("NicePay callback MID mismatch: order_id=%s", order_id)
        return fail('mid_mismatch', 'Payment response failed verification.')

    # The amount NicePay authenticated must equal the amount we asked for.
    try:
        authenticated_amount = int(params.get('Amt', '0'))
    except ValueError:
        return fail('invalid_amount', 'Invalid payment amount.')

    if authenticated_amount != transaction.amount:
        logger.error(
            "NicePay amount mismatch: order_id=%s expected=%s got=%s",
            order_id, transaction.amount, authenticated_amount,
        )
        return fail('amount_mismatch', 'Payment amount does not match the registration fee.')

    tid = params.get('TxTid', '')
    auth_token = params.get('AuthToken', '')
    if not tid or not auth_token:
        return fail('invalid_callback', 'Invalid payment response.')

    # Guard against paying twice for the same registration (e.g. two windows).
    if PaymentHistory.objects.filter(attendee=transaction.attendee, status='completed').exists():
        logger.warning("NicePay approval skipped, already paid: order_id=%s", order_id)
        return fail('already_paid', 'Payment already completed.')

    # Approve (capture). approve() net-cancels internally if it cannot tell
    # whether the approval went through.
    try:
        result = nicepay.approve(
            next_app_url=params.get('NextAppURL', ''),
            net_cancel_url=params.get('NetCancelURL', ''),
            tid=tid,
            auth_token=auth_token,
            amount=transaction.amount,
        )
    except nicepay.NicePayError as e:
        logger.error("NicePay approval failed: order_id=%s code=%s msg=%s", order_id, e.code, e.message)
        NicePayTransaction.objects.filter(pk=transaction.pk).update(
            status='failed', result_code=e.code or '', result_message=e.message or '', tid=tid,
        )
        return _redirect_fail(request, e.code, e.message, order_id)

    pay_method = result.get('PayMethod', transaction.pay_method)
    approved_tid = result.get('TID') or tid

    payment = PaymentHistory(
        attendee=transaction.attendee,
        event=transaction.event,
        amount=transaction.amount,
        status='completed',
        provider='nicepay',
        payment_type=nicepay.PAY_METHOD_LABELS.get(pay_method, pay_method),
        toss_order_id=transaction.order_id,
        toss_payment_key=approved_tid,
    )
    payment.copy_attendee_info(transaction.attendee)
    payment.copy_event_info(transaction.event)
    payment.save()

    NicePayTransaction.objects.filter(pk=transaction.pk).update(
        status='approved',
        tid=approved_tid,
        result_code=result.get('ResultCode', ''),
        result_message=result.get('ResultMsg', ''),
        payment=payment,
    )

    logger.info(
        "NicePay payment approved: order_id=%s tid=%s event=%s amount=%s",
        order_id, approved_tid, transaction.event_id, transaction.amount,
    )

    return _redirect_success(request, order_id)
