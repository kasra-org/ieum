import base64
import json
import os
import tempfile
import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from main import email_body, nicepay
from main.apis import template_attachment_paths
from main.tasks import build_email, cleanup_media_files
from main.utils import render_email_template
from main.models import CustomAnswer, CustomQuestion, Abstract, AbstractVote, Attendee, Institution, EmailAttachment, EmailTemplate, Event, EventInvitation, NicePayTransaction, OnSiteAttendee, PaymentHistory, PaymentSettings, RegistrationCategory, Speaker

User = get_user_model()

# Merchant key and signature vector published in the NicePay manual
# (https://developers.nicepay.co.kr/manual-auth.php).
TEST_MID = 'nicepay00m'
TEST_MERCHANT_KEY = 'EYzu8jGGMfqaDEp76gSckuvnaHHu+bC4opsSN6lHv3b2lurNYkVXrZ7Z1AoqQnXI3eLuaUFyoRNC6FkrzVjceg=='

def add_categories(event, *specs):
    """Give an event its priced categories. Each spec is (name, fee[, onsite_fee])."""
    created = []
    for order, spec in enumerate(specs):
        name, fee = spec[0], spec[1]
        onsite_fee = spec[2] if len(spec) > 2 else None
        created.append(RegistrationCategory.objects.create(
            event=event, order=order, name=name, fee=fee, onsite_fee=onsite_fee))
    return created


nicepay_settings = override_settings(
    NICEPAY_MID=TEST_MID,
    NICEPAY_MERCHANT_KEY=TEST_MERCHANT_KEY,
    NICEPAY_RETURN_URL='https://example.com/nicepay/callback',
    NICEPAY_SITE_URL='https://example.com',
)


@nicepay_settings
class NicePaySignatureTests(TestCase):
    """The hash field order differs per message; verify each against the manual."""

    def test_approval_sign_data_matches_documented_vector(self):
        self.assertEqual(
            nicepay.approval_sign_data(
                'NICETOKNF435F661A2D54ED799BFB9F4B3F7E369', '1004', '20191114011808'
            ),
            '599644cf3295920f3199f5f151f7abda5a85e3777fbeefe5738e265101435a65',
        )

    def test_auth_signature_excludes_edi_date(self):
        # sha256(AuthToken + MID + Amt + MerchantKey) - no EdiDate, unlike approval.
        expected = nicepay._sha256_hex('TOKEN', TEST_MID, '1004', TEST_MERCHANT_KEY)
        self.assertEqual(nicepay.auth_signature('TOKEN', '1004'), expected)

    def test_verify_auth_response_rejects_tampered_amount(self):
        params = {'AuthToken': 'TOKEN', 'MID': TEST_MID, 'Amt': '1004'}
        params['Signature'] = nicepay.auth_signature('TOKEN', '1004')
        self.assertTrue(nicepay.verify_auth_response(params))

        params['Amt'] = '10'  # payer tampered with the amount
        self.assertFalse(nicepay.verify_auth_response(params))

    def test_window_params_are_signed_and_complete(self):
        params = nicepay.build_payment_window_params(
            order_id='order123', amount=1004, goods_name='Test Event',
            return_url='https://example.com/nicepay/callback',
        )
        self.assertEqual(params['MID'], TEST_MID)
        self.assertEqual(params['Amt'], '1004')
        self.assertEqual(params['Moid'], 'order123')
        self.assertEqual(params['PayMethod'], 'CARD')
        self.assertEqual(params['CharSet'], 'utf-8')
        self.assertEqual(
            params['SignData'],
            nicepay.window_sign_data(params['EdiDate'], '1004'),
        )

    def test_untrusted_approval_url_is_rejected(self):
        # NextAppURL arrives in an unauthenticated POST body.
        nicepay._assert_allowed_url('https://dc1-api.nicepay.co.kr/webapi/pay_process.jsp', 'NextAppURL')
        with self.assertRaises(nicepay.NicePayError):
            nicepay._assert_allowed_url('https://evil.example.com/steal', 'NextAppURL')


@nicepay_settings
class NicePayCallbackTests(TestCase):
    """The callback POST is cross-site and unauthenticated - nothing in it is trusted."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='payer', email='payer@example.com', password='pw12345!'
        )
        self.event = Event.objects.create(
            name='Test Conference', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100,
        )
        category, = add_categories(self.event, ('Standard', 1004))
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Test', last_name='Payer',
            nationality=410, institute='KASRA', category=category,
        )
        self.transaction = NicePayTransaction.objects.create(
            order_id='order123', attendee=self.attendee, event=self.event,
            amount=1004, pay_method='CARD', status='pending',
        )

    def callback_params(self, **overrides):
        params = {
            'AuthResultCode': '0000',
            'AuthResultMsg': '인증성공',
            'AuthToken': 'NICETOKEN123',
            'PayMethod': 'CARD',
            'MID': TEST_MID,
            'Moid': 'order123',
            'Amt': '1004',
            'TxTid': 'nicepay00m0301191114091921',
            'NextAppURL': 'https://dc1-api.nicepay.co.kr/webapi/pay_process.jsp',
            'NetCancelURL': 'https://dc1-api.nicepay.co.kr/webapi/pay_process.jsp',
        }
        params['Signature'] = nicepay.auth_signature(params['AuthToken'], params['Amt'])
        params.update(overrides)
        return params

    def approval_response(self, tid='nicepay00m0301191114091921', amt='1004'):
        return {
            'ResultCode': '3001', 'ResultMsg': '정상 승인되었습니다',
            'TID': tid, 'MID': TEST_MID, 'Amt': amt, 'Moid': 'order123',
            'PayMethod': 'CARD', 'CardName': '비씨',
            'Signature': nicepay.approval_signature(tid, amt),
        }

    @patch('main.nicepay._post_form')
    def test_successful_payment_creates_payment_history(self, mock_post):
        mock_post.return_value = self.approval_response()

        response = self.client.post('/nicepay/callback', self.callback_params())

        self.assertEqual(response.status_code, 302)
        self.assertIn('payment/success', response['Location'])
        self.assertIn('orderId=order123', response['Location'])

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'approved')

        payment = PaymentHistory.objects.get(attendee=self.attendee)
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.provider, 'nicepay')
        self.assertEqual(payment.amount, 1004)
        self.assertEqual(payment.payment_type, '카드')
        self.assertEqual(payment.toss_order_id, 'order123')
        self.assertEqual(payment.toss_payment_key, 'nicepay00m0301191114091921')
        # Receipt fields are snapshotted at payment time.
        self.assertEqual(payment.event_name, 'Test Conference')
        self.assertEqual(payment.attendee_email, 'payer@example.com')

    @patch('main.nicepay._post_form')
    def test_tampered_amount_is_rejected_without_approval(self, mock_post):
        # A payer who rewrites Amt also has to forge Signature; they cannot.
        response = self.client.post('/nicepay/callback', self.callback_params(Amt='10'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('payment/fail', response['Location'])
        mock_post.assert_not_called()
        self.assertFalse(PaymentHistory.objects.exists())
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'failed')

    @patch('main.nicepay._post_form')
    def test_amount_must_match_the_prepared_transaction(self, mock_post):
        # Correctly signed for 10 KRW, but we asked the payer for 1004.
        params = self.callback_params(Amt='10')
        params['Signature'] = nicepay.auth_signature(params['AuthToken'], '10')

        response = self.client.post('/nicepay/callback', params)

        self.assertIn('amount_mismatch', response['Location'])
        mock_post.assert_not_called()
        self.assertFalse(PaymentHistory.objects.exists())

    @patch('main.nicepay._post_form')
    def test_failed_authentication_does_not_approve(self, mock_post):
        response = self.client.post(
            '/nicepay/callback',
            self.callback_params(AuthResultCode='9999', AuthResultMsg='사용자 취소'),
        )

        self.assertIn('payment/fail', response['Location'])
        mock_post.assert_not_called()
        self.assertFalse(PaymentHistory.objects.exists())
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'failed')

    @patch('main.nicepay._post_form')
    def test_replayed_callback_does_not_charge_twice(self, mock_post):
        mock_post.return_value = self.approval_response()

        first = self.client.post('/nicepay/callback', self.callback_params())
        second = self.client.post('/nicepay/callback', self.callback_params())

        self.assertIn('payment/success', first['Location'])
        self.assertIn('payment/success', second['Location'])
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(PaymentHistory.objects.count(), 1)

    @patch('main.nicepay._post_form')
    def test_rejected_approval_records_the_failure(self, mock_post):
        mock_post.return_value = {
            'ResultCode': '3F', 'ResultMsg': '한도초과', 'TID': 'nicepay00m0301191114091921',
            'MID': TEST_MID, 'Amt': '1004', 'PayMethod': 'CARD',
        }

        response = self.client.post('/nicepay/callback', self.callback_params())

        self.assertIn('payment/fail', response['Location'])
        self.assertFalse(PaymentHistory.objects.exists())
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'failed')
        self.assertEqual(self.transaction.result_code, '3F')

    @patch('main.nicepay._post_form')
    def test_unreachable_approval_triggers_net_cancel(self, mock_post):
        import requests

        # First call (approval) fails at the network level, second is the net-cancel.
        mock_post.side_effect = [
            requests.ConnectionError('boom'),
            {'ResultCode': '2001', 'ResultMsg': '취소성공'},
        ]

        response = self.client.post('/nicepay/callback', self.callback_params())

        self.assertIn('payment/fail', response['Location'])
        self.assertEqual(mock_post.call_count, 2)
        net_cancel_payload = mock_post.call_args_list[1][0][1]
        self.assertEqual(net_cancel_payload['NetCancel'], '1')
        self.assertFalse(PaymentHistory.objects.exists())

    def test_unknown_order_is_rejected(self):
        response = self.client.post('/nicepay/callback', self.callback_params(Moid='nope'))
        self.assertIn('unknown_order', response['Location'])

    @patch('main.nicepay._post_form')
    def test_approval_response_signature_is_verified(self, mock_post):
        result = self.approval_response()
        result['Signature'] = 'forged'
        mock_post.return_value = result

        response = self.client.post('/nicepay/callback', self.callback_params())

        self.assertIn('signature_mismatch', response['Location'])
        self.assertFalse(PaymentHistory.objects.exists())


@nicepay_settings
class NicePayCancelTests(TestCase):
    @patch('main.nicepay._post_form')
    def test_cancel_success(self, mock_post):
        mock_post.return_value = {
            'ResultCode': '2001', 'ResultMsg': '취소成功', 'TID': 'TID1',
            'MID': TEST_MID, 'CancelAmt': '1004',
        }
        result = nicepay.cancel(
            tid='TID1', moid='order123', cancel_amount=1004, reason='관리자 취소',
        )
        self.assertEqual(result['ResultCode'], '2001')

        payload = mock_post.call_args[0][1]
        self.assertEqual(payload['PartialCancelCode'], '0')
        self.assertEqual(payload['CancelAmt'], '1004')
        # The cancel API rejects the request when Moid is absent or empty.
        self.assertEqual(payload['Moid'], 'order123')
        self.assertEqual(
            payload['SignData'], nicepay.cancel_sign_data('1004', payload['EdiDate'])
        )

    @patch('main.nicepay._post_form')
    def test_cancel_rejection_raises(self, mock_post):
        mock_post.return_value = {'ResultCode': '4000', 'ResultMsg': '취소 불가'}
        with self.assertRaises(nicepay.NicePayError) as ctx:
            nicepay.cancel(tid='TID1', moid='order123', cancel_amount=1004)
        self.assertEqual(ctx.exception.code, '4000')

    @patch('main.nicepay._post_form')
    def test_cancel_without_an_order_id_never_reaches_the_api(self, mock_post):
        with self.assertRaises(nicepay.NicePayError) as ctx:
            nicepay.cancel(tid='TID1', moid='', cancel_amount=1004)
        self.assertEqual(ctx.exception.code, 'missing_moid')
        mock_post.assert_not_called()

    @patch('main.nicepay._post_form')
    def test_a_payment_cancelled_elsewhere_is_not_an_error(self, mock_post):
        # Cancelled in NicePay's web manager: the refund already happened, so
        # the rejection is a success from our side.
        mock_post.return_value = {
            'ResultCode': '2211',
            'ResultMsg': '해당거래 취소실패(기취소성공) : 전화 문의(1661-0808)',
        }
        result = nicepay.cancel(tid='TID1', moid='order123', cancel_amount=1004)
        self.assertTrue(nicepay.is_already_cancelled(result))

    def test_an_ordinary_rejection_is_not_read_as_already_cancelled(self):
        self.assertFalse(nicepay.is_already_cancelled({'ResultMsg': '취소 불가'}))
        self.assertFalse(nicepay.is_already_cancelled({}))


@nicepay_settings
class NicePayAdminCancelTests(TestCase):
    """The event admin's cancel button, end to end."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Cancellable', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        category, = add_categories(self.event, ('Regular', 200000))
        user = User.objects.create_user(
            username='payer@example.com', email='payer@example.com', password='pw12345!aA')
        self.attendee = Attendee.objects.create(
            user=user, event=self.event, first_name='Pay', last_name='Er',
            nationality=1, institute='PNU', category=category)
        self.payment = PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=200000, status='completed',
            provider='nicepay', toss_payment_key='TID1', toss_order_id='MOID-1',
        )
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

    def cancel(self):
        return self.client.post(
            f'/api/event/{self.event.id}/payment/{self.payment.id}/cancel',
            data=json.dumps({'cancel_reason': '관리자 취소'}),
            content_type='application/json',
        )

    @patch('main.nicepay._post_form')
    def test_cancel_sends_the_stored_moid(self, mock_post):
        mock_post.return_value = {'ResultCode': '2001', 'ResultMsg': '취소성공'}
        self.assertEqual(self.cancel().status_code, 200)
        self.assertEqual(mock_post.call_args[0][1]['Moid'], 'MOID-1')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'cancelled')

    @patch('main.nicepay._post_form')
    def test_a_payment_already_cancelled_at_the_gateway_updates_the_record(self, mock_post):
        mock_post.return_value = {
            'ResultCode': '2211',
            'ResultMsg': '해당거래 취소실패(기취소성공) : 전화 문의(1661-0808)',
        }
        self.assertEqual(self.cancel().status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'cancelled')

    @patch('main.nicepay._post_form')
    def test_a_genuine_rejection_leaves_the_record_alone(self, mock_post):
        mock_post.return_value = {'ResultCode': '4000', 'ResultMsg': '취소 불가'}
        self.assertEqual(self.cancel().status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'completed')


@nicepay_settings
class PaymentProviderSelectionTests(TestCase):
    """One provider per category, enforced server-side rather than in the UI."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@example.com', password='pw12345!'
        )
        self.event = Event.objects.create(
            name='Paid Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100,
        )
        category, = add_categories(self.event, ('Standard', 1004))
        Attendee.objects.create(
            user=self.user, event=self.event, first_name='Buy', last_name='Er',
            nationality=410, institute='KASRA', category=category,
        )
        self.client.force_login(self.user)

    def set_providers(self, domestic, international):
        s = PaymentSettings.get_instance()
        s.domestic_provider = domestic
        s.international_provider = international
        s.save()

    def test_defaults_are_toss_and_paypal(self):
        s = PaymentSettings.get_instance()
        self.assertEqual(s.domestic_provider, 'toss')
        self.assertEqual(s.international_provider, 'paypal')

    def test_is_enabled_reflects_selection(self):
        self.set_providers('nicepay', 'none')
        s = PaymentSettings.get_instance()
        self.assertTrue(s.is_enabled('nicepay'))
        self.assertFalse(s.is_enabled('toss'))
        self.assertFalse(s.is_enabled('paypal'))

    def test_nicepay_prepare_rejected_when_toss_is_selected(self):
        self.set_providers('toss', 'paypal')
        response = self.client.post(
            '/api/payment/nicepay/prepare',
            data={'eventId': self.event.id, 'payMethod': 'CARD'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'provider_disabled')

    @patch('main.apis.requests.post')
    def test_toss_confirm_rejected_when_nicepay_is_selected(self, mock_post):
        self.set_providers('nicepay', 'paypal')
        response = self.client.post(
            '/api/payment/confirm',
            data={'paymentKey': 'k', 'orderId': 'o', 'amount': 1004, 'eventId': self.event.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'provider_disabled')
        # Rejected before any money moves.
        mock_post.assert_not_called()

    def test_paypal_rejected_when_international_disabled(self):
        self.set_providers('toss', 'none')
        response = self.client.post(
            '/api/payment/paypal/create-order',
            data={'eventId': self.event.id, 'amount': 1004},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'provider_disabled')

    def test_nicepay_prepare_allowed_when_selected(self):
        self.set_providers('nicepay', 'none')
        response = self.client.post(
            '/api/payment/nicepay/prepare',
            data={'eventId': self.event.id, 'payMethod': 'CARD'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['params']['MID'], TEST_MID)

    def test_admin_endpoint_rejects_unknown_provider(self):
        staff = User.objects.create_user(
            username='boss', email='boss@example.com', password='pw12345!', is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.post(
            '/api/admin/payment-settings',
            data={'domestic_provider': 'stripe', 'international_provider': 'paypal'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_provider')
        self.assertEqual(PaymentSettings.get_instance().domestic_provider, 'toss')

    def test_non_staff_cannot_change_providers(self):
        response = self.client.post(
            '/api/admin/payment-settings',
            data={'domestic_provider': 'nicepay', 'international_provider': 'none'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(PaymentSettings.get_instance().domestic_provider, 'toss')


class GuestUserTests(TestCase):
    """Admin-created test accounts: real logins, never elevated."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin@example.com', email='admin@example.com',
            password='pw12345!aA', is_staff=True,
        )
        self.plain = User.objects.create_user(
            username='joe@example.com', email='joe@example.com', password='pw12345!aA',
        )

    def payload(self, **over):
        data = {
            'email': 'guest1@example.com', 'password': 'Str0ngGuestPw!23',
            'first_name': 'Guest', 'last_name': 'Tester',
        }
        data.update(over)
        return data

    def post(self, data):
        return self.client.post(
            '/api/admin/user/guest/add', data=data, content_type='application/json'
        )

    def test_staff_can_create_a_usable_guest(self):
        from allauth.account.models import EmailAddress
        self.client.force_login(self.staff)

        response = self.post(self.payload())
        self.assertEqual(response.status_code, 200)

        guest = User.objects.get(email='guest1@example.com')
        self.assertTrue(guest.is_guest)
        self.assertTrue(guest.is_active)
        self.assertEqual(guest.username, guest.email)
        # Verified up front, so the account works without an inbox round-trip.
        self.assertTrue(EmailAddress.objects.get(user=guest, primary=True).verified)
        # And it really can log in.
        self.client.logout()
        self.assertTrue(self.client.login(username='guest1@example.com', password='Str0ngGuestPw!23'))

    def test_guest_never_gets_admin_rights(self):
        self.client.force_login(self.staff)
        # Even if the caller tries to smuggle them in.
        self.post(self.payload(is_staff=True, is_superuser=True))
        guest = User.objects.get(email='guest1@example.com')
        self.assertFalse(guest.is_staff)
        self.assertFalse(guest.is_superuser)

    def test_non_staff_cannot_create_guests(self):
        self.client.force_login(self.plain)
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(email='guest1@example.com').exists())

    def test_anonymous_cannot_create_guests(self):
        response = self.post(self.payload())
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(User.objects.filter(email='guest1@example.com').exists())

    def test_duplicate_email_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.post(self.payload(email='JOE@example.com'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'email_taken')

    def test_weak_password_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.post(self.payload(password='123'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'weak_password')
        self.assertFalse(User.objects.filter(email='guest1@example.com').exists())

    def test_invalid_email_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.post(self.payload(email='not-an-email'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_email')

    def test_regular_users_are_not_marked_as_guests(self):
        self.assertFalse(self.plain.is_guest)


class GuestPasswordResetTests(TestCase):
    """Direct password set, restricted to guest accounts."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin2@example.com', email='admin2@example.com',
            password='pw12345!aA', is_staff=True,
        )
        self.guest = User.objects.create_user(
            username='g@example.com', email='g@example.com',
            password='OldGuestPw!234', is_guest=True,
        )
        self.real = User.objects.create_user(
            username='real@example.com', email='real@example.com', password='RealPw!2345',
        )
        self.superuser = User.objects.create_superuser(
            username='root@example.com', email='root@example.com', password='RootPw!2345',
        )

    def set_password(self, user, password='BrandNewPw!987'):
        return self.client.post(
            f'/api/admin/user/{user.id}/set-password',
            data={'password': password}, content_type='application/json',
        )

    def test_staff_can_set_a_guest_password(self):
        self.client.force_login(self.staff)
        response = self.set_password(self.guest)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        self.assertTrue(self.client.login(username='g@example.com', password='BrandNewPw!987'))

    def test_real_account_password_cannot_be_set_directly(self):
        self.client.force_login(self.staff)
        response = self.set_password(self.real)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'not_a_guest')
        self.real.refresh_from_db()
        self.assertTrue(self.real.check_password('RealPw!2345'))

    def test_superuser_cannot_be_taken_over(self):
        self.client.force_login(self.staff)
        response = self.set_password(self.superuser)
        self.assertEqual(response.status_code, 400)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password('RootPw!2345'))

    def test_non_staff_cannot_set_passwords(self):
        self.client.force_login(self.real)
        response = self.set_password(self.guest)
        self.assertEqual(response.status_code, 403)
        self.guest.refresh_from_db()
        self.assertTrue(self.guest.check_password('OldGuestPw!234'))

    def test_weak_password_is_rejected(self):
        self.client.force_login(self.staff)
        response = self.set_password(self.guest, password='123')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'weak_password')
        self.guest.refresh_from_db()
        self.assertTrue(self.guest.check_password('OldGuestPw!234'))

    def test_unknown_user_is_404(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            '/api/admin/user/999999/set-password',
            data={'password': 'BrandNewPw!987'}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


@nicepay_settings
class RegistrationCategoryTests(TestCase):
    """Organiser-defined categories. The server prices from the stored category,
    never from what the client claims."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='stud@example.com', email='stud@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Tiered Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100,
        )
        self.undergrad, self.grad, self.standard = add_categories(
            self.event,
            ('Undergraduate student', 50000),
            ('Graduate student / Postdoc', 100000),
            ('PI / Non-academic', 200000),
        )
        # Registration sends a confirmation mail, so the template must exist.
        self.event.email_template_registration = EmailTemplate.objects.create(
            subject='Registered', body='Thanks',
        )
        self.event.save()
        self.client.force_login(self.user)

    def test_each_category_carries_its_own_price(self):
        self.assertEqual(self.undergrad.fee, 50000)
        self.assertEqual(self.grad.fee, 100000)
        self.assertEqual(self.standard.fee, 200000)

    def test_a_single_category_is_not_a_choice(self):
        plain = Event.objects.create(
            name='Flat', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        add_categories(plain, ('Standard', 30000))
        self.assertFalse(plain.has_tiered_fees)

    def test_an_event_with_no_categories_is_free(self):
        free = Event.objects.create(
            name='Free', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        self.assertEqual(free.active_categories, [])
        self.assertFalse(free.has_tiered_fees)
        self.assertFalse(free.has_onsite_fee)
        attendee = Attendee.objects.create(
            event=free, first_name='No', last_name='Fee', nationality=1, institute='PNU',
        )
        self.assertEqual(attendee.registration_fee, 0)
        self.assertEqual(attendee.payment_status, 'free')

    def test_more_than_one_category_is_a_choice(self):
        self.assertTrue(self.event.has_tiered_fees)

    def test_a_deactivated_category_is_no_longer_offered(self):
        self.undergrad.is_active = False
        self.undergrad.save()
        event = Event.objects.get(id=self.event.id)
        self.assertEqual([c.id for c in event.active_categories],
                         [self.grad.id, self.standard.id])
        self.assertIsNone(event.category_by_id(self.undergrad.id))

    def test_another_events_category_is_not_accepted(self):
        other = Event.objects.create(
            name='Other', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Busan', capacity=10,
        )
        cheap, = add_categories(other, ('Cheap', 1))
        self.assertIsNone(self.event.category_by_id(cheap.id))

    def test_label_falls_back_to_english(self):
        self.undergrad.name_ko = '학부생'
        self.assertEqual(self.undergrad.label('ko'), '학부생')
        self.assertEqual(self.undergrad.label('en'), 'Undergraduate student')
        self.assertEqual(self.grad.label('ko'), 'Graduate student / Postdoc')

    def register(self, **extra):
        payload = {
            'first_name': 'Stu', 'last_name': 'Dent', 'nationality': 1,
            'institute': Institution.objects.create(name_en='PNU').id,
            'job_title': 'Student',
        }
        payload.update(extra)
        return self.client.post(
            f'/api/event/{self.event.id}/register',
            data=payload, content_type='application/json',
        )

    def test_registering_records_the_chosen_category(self):
        self.register(category=self.grad.id)
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.category, self.grad)
        self.assertEqual(attendee.registration_fee, 100000)

    def test_a_category_the_event_does_not_offer_is_refused(self):
        self.grad.is_active = False
        self.grad.save()
        # Claiming a retired category must not buy its price.
        self.register(category=self.grad.id)
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.category, self.undergrad)
        self.assertEqual(attendee.registration_fee, 50000)

    def test_no_category_falls_back_to_the_first_offered(self):
        self.register()
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.category, self.undergrad)

    def test_registering_for_an_event_with_no_categories_is_free(self):
        self.event.registration_categories.all().delete()
        self.register()
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertIsNone(attendee.category)
        self.assertEqual(attendee.registration_fee, 0)
        self.assertEqual(attendee.payment_status, 'free')

    @patch('main.apis.requests.post')
    def test_payment_below_the_category_price_is_rejected(self, mock_post):
        self.register(category=self.grad.id)
        response = self.client.post(
            '/api/payment/confirm',
            data={'paymentKey': 'k', 'orderId': 'o', 'amount': 50000, 'eventId': self.event.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'amount_mismatch')
        mock_post.assert_not_called()

    @patch('main.apis.requests.post')
    def test_payment_matching_the_category_price_is_accepted(self, mock_post):
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {'method': '카드'}
        self.register(category=self.grad.id)
        response = self.client.post(
            '/api/payment/confirm',
            data={'paymentKey': 'k', 'orderId': 'o', 'amount': 100000, 'eventId': self.event.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payment = PaymentHistory.objects.get(event=self.event)
        self.assertEqual(payment.amount, 100000)


    @patch('main.apis.requests.post')
    def test_a_gateway_answering_garbage_is_a_server_error_not_the_payers(self, mock_post):
        import requests as requests_lib
        mock_post.return_value.ok = True
        mock_post.return_value.json.side_effect = requests_lib.exceptions.JSONDecodeError('Expecting value', '<html>', 0)
        self.register(category=self.grad.id)
        with self.assertRaises(requests_lib.exceptions.JSONDecodeError):
            self.client.post(
                '/api/payment/confirm',
                data={'paymentKey': 'k', 'orderId': 'o', 'amount': 100000, 'eventId': self.event.id},
                content_type='application/json',
            )

class RegistrationCategoryEditingTests(TestCase):
    """Organisers add, rename, reprice, reorder and remove categories."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Editable', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        self.a, self.b = add_categories(self.event, ('A', 1000), ('B', 2000))

    def apply(self, payload):
        from main.apis import replace_registration_categories
        return replace_registration_categories(self.event, payload)

    def test_new_events_start_with_the_three_defaults(self):
        fresh = Event.objects.create(
            name='Fresh', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        fresh.seed_default_categories()
        self.assertEqual(
            [c.name for c in fresh.registration_categories.all()],
            ['Undergraduate student', 'Graduate student / Postdoc', 'PI / Non-academic'],
        )

    def test_seeding_twice_does_not_duplicate(self):
        self.event.seed_default_categories()
        self.assertEqual(self.event.registration_categories.count(), 2)

    def test_rename_and_reprice(self):
        self.assertIsNone(self.apply([
            {'id': self.a.id, 'name': 'Student', 'name_ko': '학생', 'fee': 5000, 'onsite_fee': 7000},
            {'id': self.b.id, 'name': 'B', 'fee': 2000},
        ]))
        self.a.refresh_from_db()
        self.assertEqual((self.a.name, self.a.name_ko, self.a.fee, self.a.onsite_fee),
                         ('Student', '학생', 5000, 7000))

    def test_adding_a_category(self):
        self.apply([
            {'id': self.a.id, 'name': 'A', 'fee': 1000},
            {'id': self.b.id, 'name': 'B', 'fee': 2000},
            {'name': 'C', 'fee': 3000},
        ])
        self.assertEqual([c.name for c in self.event.registration_categories.all()],
                         ['A', 'B', 'C'])

    def test_order_follows_the_submitted_list(self):
        self.apply([
            {'id': self.b.id, 'name': 'B', 'fee': 2000},
            {'id': self.a.id, 'name': 'A', 'fee': 1000},
        ])
        self.assertEqual([c.name for c in self.event.registration_categories.all()], ['B', 'A'])

    def test_an_unused_category_is_deleted_outright(self):
        self.apply([{'id': self.a.id, 'name': 'A', 'fee': 1000}])
        self.assertFalse(RegistrationCategory.objects.filter(id=self.b.id).exists())

    def test_a_category_in_use_is_retired_not_deleted(self):
        Attendee.objects.create(
            event=self.event, category=self.b, first_name='In', last_name='Use',
            nationality=1, institute='PNU',
        )
        self.apply([{'id': self.a.id, 'name': 'A', 'fee': 1000}])
        self.b.refresh_from_db()
        # Still there, still pricing that registration, but off the form.
        self.assertFalse(self.b.is_active)
        self.assertEqual(Attendee.objects.get(event=self.event).registration_fee, 2000)

    def test_removing_every_category_makes_the_event_free(self):
        self.assertIsNone(self.apply([]))
        self.assertEqual(self.event.registration_categories.count(), 0)
        self.assertEqual(Event.objects.get(id=self.event.id).active_categories, [])

    def test_removing_every_category_keeps_the_ones_in_use(self):
        Attendee.objects.create(
            event=self.event, category=self.b, first_name='In', last_name='Use',
            nationality=1, institute='PNU',
        )
        self.apply([])
        self.b.refresh_from_db()
        # Retired, so nobody is offered it, but it still prices that registration.
        self.assertFalse(self.b.is_active)
        self.assertEqual(Attendee.objects.get(event=self.event).registration_fee, 2000)
        self.assertEqual(Event.objects.get(id=self.event.id).active_categories, [])

    def test_entries_without_a_name_are_dropped(self):
        self.assertIsNone(self.apply([{'name': '  ', 'fee': 1}]))
        self.assertEqual(self.event.registration_categories.count(), 0)

    def test_a_blank_fee_means_free(self):
        self.apply([{'id': self.a.id, 'name': 'A', 'fee': ''}])
        self.a.refresh_from_db()
        self.assertEqual(self.a.fee, 0)

    def test_a_blank_onsite_fee_means_no_onsite_charge(self):
        self.apply([{'id': self.a.id, 'name': 'A', 'fee': 100, 'onsite_fee': ''}])
        self.a.refresh_from_db()
        self.assertIsNone(self.a.onsite_fee)

    def test_a_category_cannot_be_deleted_while_it_prices_a_registration(self):
        from django.db.models import RestrictedError
        Attendee.objects.create(
            event=self.event, category=self.b, first_name='In', last_name='Use',
            nationality=1, institute='PNU',
        )
        with self.assertRaises(RestrictedError):
            self.b.delete()

    def test_deleting_the_event_still_works(self):
        Attendee.objects.create(
            event=self.event, category=self.b, first_name='In', last_name='Use',
            nationality=1, institute='PNU',
        )
        self.event.delete()
        self.assertFalse(RegistrationCategory.objects.filter(id=self.b.id).exists())


class AbstractPresentationTypeTests(TestCase):
    """presentation_type is authoritative; the legacy pair is derived from it."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Symposium', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )

    def make(self, presentation_type):
        return Abstract.objects.create(
            event=self.event, title='T', file_path='abstracts/x/a.docx',
            presentation_type=presentation_type,
        )

    def test_legacy_fields_are_derived(self):
        cases = {
            'poster': ('poster', False),
            'short_talk_poster': ('poster', True),
            'short_talk': ('speaker', False),
            'flash_talk_poster': ('poster', False),
            'invited': ('speaker', False),
        }
        for presentation_type, (expected_type, expected_short) in cases.items():
            a = self.make(presentation_type)
            self.assertEqual(a.type, expected_type, presentation_type)
            self.assertEqual(a.wants_short_talk, expected_short, presentation_type)

    def test_legacy_fields_cannot_drift(self):
        a = self.make('invited')
        # Even if something writes the old fields directly, saving re-derives them.
        a.type = 'poster'
        a.wants_short_talk = True
        a.save()
        self.assertEqual(a.type, 'speaker')
        self.assertFalse(a.wants_short_talk)

    def test_all_five_options_are_offered(self):
        self.assertEqual(
            [c[0] for c in Abstract.PRESENTATION_TYPE_CHOICES],
            ['poster', 'short_talk_poster', 'short_talk', 'flash_talk_poster', 'invited'],
        )


class InvitedTalkReviewExemptionTests(TestCase):
    """Invited and plenary talks are not scored, and reviewers never see them."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Reviewed Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, accepts_abstract=True,
            abstract_deadline=date(2020, 1, 1),  # passed, so voting is open
        )
        self.reviewer_user = User.objects.create_user(
            username='rev@example.com', email='rev@example.com', password='pw12345!aA')
        self.reviewer = Attendee.objects.create(
            user=self.reviewer_user, event=self.event, first_name='Rev', last_name='Iewer',
            nationality=1, institute='PNU')
        self.event.reviewers.add(self.reviewer)
        AbstractVote.objects.create(reviewer=self.reviewer)

        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)

        author = Attendee.objects.create(
            event=self.event, first_name='Au', last_name='Thor',
            nationality=1, institute='PNU')
        self.competing = Abstract.objects.create(
            event=self.event, attendee=author, title='Competing', file_path='a/b.docx',
            presentation_type='short_talk_poster')
        self.invited = Abstract.objects.create(
            event=self.event, attendee=author, title='Invited', file_path='a/c.docx',
            presentation_type='invited')

    def test_is_reviewable_flag(self):
        self.assertTrue(self.competing.is_reviewable)
        self.assertFalse(self.invited.is_reviewable)

    def test_reviewer_does_not_see_invited_talks(self):
        self.client.force_login(self.reviewer_user)
        response = self.client.get(f'/api/event/{self.event.id}/review/abstracts')
        self.assertEqual(response.status_code, 200)
        titles = [a['title'] for a in response.json()]
        self.assertIn('Competing', titles)
        self.assertNotIn('Invited', titles)

    def test_admin_still_sees_every_abstract(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/event/{self.event.id}/abstracts')
        titles = [a['title'] for a in response.json()['items']]
        self.assertIn('Competing', titles)
        self.assertIn('Invited', titles)

    def test_voting_for_an_invited_talk_is_refused(self):
        self.client.force_login(self.reviewer_user)
        response = self.client.post(
            f'/api/event/{self.event.id}/reviewer/vote',
            data={'voted_abstracts': [self.invited.id]}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'not_reviewable')
        self.assertEqual(AbstractVote.objects.get(reviewer=self.reviewer).voted_abstracts.count(), 0)

    def test_an_unknown_ballot_entry_is_refused_not_a_crash(self):
        self.client.force_login(self.reviewer_user)
        for bad in (999999, 'x', None, True):
            response = self.client.post(
                f'/api/event/{self.event.id}/reviewer/vote',
                data={'voted_abstracts': [self.competing.id, bad]}, content_type='application/json')
            self.assertEqual(response.status_code, 400, bad)
        self.assertFalse(AbstractVote.objects.filter(reviewer=self.reviewer, voted_abstracts__isnull=False).exists())

    def test_a_ballot_that_is_not_a_list_is_refused(self):
        self.client.force_login(self.reviewer_user)
        for ballot in (None, 5, '12', {'a': 1}):
            response = self.client.post(f'/api/event/{self.event.id}/reviewer/vote',
                                        data=json.dumps({'voted_abstracts': ballot}), content_type='application/json')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_ballot'), ballot)

    def test_a_ballot_past_the_limit_is_refused(self):
        self.event.max_votes = 1
        self.event.save()
        second = Abstract.objects.create(attendee=self.competing.attendee, event=self.event, title='Second',
                                         file_path='a/s.docx')
        self.client.force_login(self.reviewer_user)
        response = self.client.post(f'/api/event/{self.event.id}/reviewer/vote',
                                    data={'voted_abstracts': [self.competing.id, second.id]},
                                    content_type='application/json')
        self.assertEqual((response.status_code, response.json()['code']), (400, 'too_many_votes'))

    def test_a_refused_ballot_records_none_of_its_votes(self):
        self.client.force_login(self.reviewer_user)
        response = self.client.post(
            f'/api/event/{self.event.id}/reviewer/vote',
            data={'voted_abstracts': [self.competing.id, self.invited.id]}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AbstractVote.objects.filter(reviewer=self.reviewer, voted_abstracts__isnull=False).exists())

    def test_voting_for_a_competing_abstract_still_works(self):
        self.client.force_login(self.reviewer_user)
        response = self.client.post(
            f'/api/event/{self.event.id}/reviewer/vote',
            data={'voted_abstracts': [self.competing.id]}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AbstractVote.objects.get(reviewer=self.reviewer).voted_abstracts.count(), 1)


class EmailTemplateEscapingTests(TestCase):
    """Emails are text/plain, so template rendering must not HTML-escape."""

    def test_ampersand_survives(self):
        rendered = render_email_template(
            'Registration for {{ event.name }}',
            {'event': Event(name='SCSOK & KSBMB Joint Symposium')},
        )
        self.assertIn('SCSOK & KSBMB', rendered)
        self.assertNotIn('&amp;', rendered)

    def test_quotes_and_angle_brackets_survive(self):
        rendered = render_email_template(
            '{{ event.name }}',
            {'event': Event(name='O\'Brien "quoted" <tagged>')},
        )
        self.assertEqual(rendered, 'O\'Brien "quoted" <tagged>')

    def test_template_variables_still_render(self):
        rendered = render_email_template(
            'Dear {{ attendee.first_name }}, see you at {{ event.name }}.',
            {'event': Event(name='Symposium'), 'attendee': Attendee(first_name='Jeongbin')},
        )
        self.assertEqual(rendered, 'Dear Jeongbin, see you at Symposium.')


class OnSiteRegistrationFeeTests(TestCase):
    """A paid-for on-site registration is not complete until staff confirm it."""

    def setUp(self):
        from zoneinfo import ZoneInfo
        from datetime import datetime as dt
        from main.models import BusinessSettings
        today = dt.now(ZoneInfo(BusinessSettings.get_instance().timezone)).date()
        self.event = Event.objects.create(
            name='Walk-in Event', start_date=today, end_date=today,
            venue='Seoul', capacity=100, onsite_code='TESTCD',
        )
        self.standard, = add_categories(self.event, ('Standard', 100000, 30000))

    def register(self):
        return self.client.post(
            f'/api/event/{self.event.id}/onsite',
            data={'code': 'TESTCD', 'name': 'Walk In', 'email': 'w@example.com',
                  'institute': 'PNU', 'job_title': 'Dev'},
            content_type='application/json',
        )

    def test_onsite_price_is_separate_from_the_standard_one(self):
        self.assertEqual(self.standard.fee, 100000)
        self.assertEqual(self.standard.onsite_fee, 30000)

    def test_walkin_is_charged_their_category(self):
        grad, = add_categories(self.event, ('Graduate', 200000, 180000))
        response = self.client.post(
            f'/api/event/{self.event.id}/onsite',
            data={'code': 'TESTCD', 'name': 'W', 'email': 'g@example.com',
                  'institute': 'P', 'job_title': 'D', 'category': grad.id},
            content_type='application/json',
        )
        self.assertEqual(response.json()['fee'], 180000)
        oa = OnSiteAttendee.objects.get(email='g@example.com')
        self.assertEqual(oa.category, grad)
        self.assertEqual(oa.registration_fee, 180000)

    def test_walkin_cannot_claim_a_category_the_event_does_not_offer(self):
        retired, = add_categories(self.event, ('Retired', 10000, 10000))
        retired.is_active = False
        retired.save()
        self.client.post(
            f'/api/event/{self.event.id}/onsite',
            data={'code': 'TESTCD', 'name': 'W', 'email': 'x@example.com',
                  'institute': 'P', 'job_title': 'D', 'category': retired.id},
            content_type='application/json',
        )
        oa = OnSiteAttendee.objects.get(email='x@example.com')
        self.assertEqual(oa.category, self.standard)
        self.assertEqual(oa.registration_fee, 30000)

    def test_registration_reports_the_fee_owed(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['payment_required'])
        self.assertEqual(body['fee'], 30000)

    def test_not_complete_until_confirmed(self):
        self.register()
        oa = OnSiteAttendee.objects.get(event=self.event, email='w@example.com')
        self.assertFalse(oa.is_confirmed)
        self.assertFalse(oa.is_registration_complete)

        oa.is_confirmed = True
        oa.save()
        self.assertTrue(oa.is_registration_complete)

    def test_free_on_site_registration_completes_immediately(self):
        self.standard.onsite_fee = None
        self.standard.save()
        response = self.register()
        self.assertFalse(response.json()['payment_required'])

        oa = OnSiteAttendee.objects.get(event=self.event, email='w@example.com')
        self.assertFalse(oa.is_confirmed)
        # No fee to collect, so confirmation is not what completes it.
        self.assertTrue(oa.is_registration_complete)

    def test_zero_fee_is_treated_as_free(self):
        self.standard.onsite_fee = 0
        self.standard.save()
        self.register()
        oa = OnSiteAttendee.objects.get(event=self.event, email='w@example.com')
        self.assertTrue(oa.is_registration_complete)


class AbstractPaymentGateTests(TestCase):
    """An unpaid registration cannot submit an abstract."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='sub@example.com', email='sub@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Gated Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, capacity_abstract=100,
            accepts_abstract=True,
        )
        self.category, = add_categories(self.event, ('Standard', 100000))
        self.event.email_template_abstract_submission = EmailTemplate.objects.create(
            subject='Submitted', body='Thanks',
        )
        self.event.save()
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Sub', last_name='Mitter',
            nationality=1, institute='PNU', job_title='Student', category=self.category,
        )
        self.client.force_login(self.user)

    def submit(self):
        # A real .docx: a zip whose first entry is the OOXML content type part.
        import base64, io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
            z.writestr('word/document.xml', '<?xml version="1.0"?><document/>')
        payload = base64.b64encode(buf.getvalue()).decode()
        return self.client.post(
            f'/api/event/{self.event.id}/abstract',
            data={
                'title': 'My Abstract',
                'presentation_type': 'poster',
                'file_name': 'a.docx',
                'file_content': f'data:application/octet-stream;base64,{payload}',
            },
            content_type='application/json',
        )

    def test_unpaid_registration_cannot_submit(self):
        self.assertTrue(self.attendee.has_outstanding_payment)
        response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'payment_required')
        self.assertFalse(Abstract.objects.filter(event=self.event).exists())

    def test_paid_registration_can_submit(self):
        PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=100000, status='completed',
        )
        self.assertFalse(self.attendee.has_outstanding_payment)
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Abstract.objects.filter(event=self.event).exists())

    def test_free_event_is_not_gated(self):
        self.category.fee = 0
        self.category.save()
        self.assertEqual(self.attendee.payment_status, 'free')
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Abstract.objects.filter(event=self.event).exists())

    def test_a_cancelled_payment_does_not_count_as_paid(self):
        PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=100000, status='cancelled',
        )
        self.assertTrue(self.attendee.has_outstanding_payment)
        self.assertEqual(self.submit().status_code, 400)

    def test_free_category_attendee_is_not_gated_on_a_paid_event(self):
        # The gate must read this attendee's category, not the headline fee.
        free, = add_categories(self.event, ('Invited speaker', 0))
        self.attendee.category = free
        self.attendee.save()
        self.attendee.refresh_from_db()
        self.assertEqual(self.attendee.payment_status, 'free')
        self.assertEqual(self.submit().status_code, 200)


class CategorySerializationTests(TestCase):
    """The API must send the category id, not the model instance.

    A plain `category: int` field made ninja hand pydantic the FK object and
    500 the whole registration endpoint, which no pricing test caught.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='ser@example.com', email='ser@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Serialized', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, onsite_code='SERCOD', published=True,
        )
        self.category, = add_categories(self.event, ('Student', 50000, 60000))
        self.category.name_ko = '학생'
        self.category.save()
        attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Ser', last_name='Ial',
            nationality=1, institute='PNU', category=self.category,
        )
        # The endpoint looks the attendee up through the M2M, not the FK.
        self.event.attendees.add(attendee)
        self.client.force_login(self.user)

    def test_registration_endpoint_serializes(self):
        response = self.client.get(f'/api/event/{self.event.id}/registration')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['category'], self.category.id)
        self.assertEqual(body['category_name'], 'Student')
        self.assertEqual(body['category_name_ko'], '학생')
        self.assertEqual(body['registration_fee'], 50000)

    def test_event_endpoint_lists_its_categories(self):
        response = self.client.get(f'/api/event/{self.event.id}')
        self.assertEqual(response.status_code, 200)
        categories = response.json()['registration_categories']
        self.assertEqual([c['name'] for c in categories], ['Student'])
        self.assertEqual(categories[0]['fee'], 50000)
        self.assertEqual(categories[0]['onsite_fee'], 60000)

    def test_retired_categories_are_not_offered_to_clients(self):
        add_categories(self.event, ('Gone', 1))
        self.event.registration_categories.filter(name='Gone').update(is_active=False)
        response = self.client.get(f'/api/event/{self.event.id}')
        self.assertEqual([c['name'] for c in response.json()['registration_categories']], ['Student'])

    def test_onsite_list_serializes(self):
        OnSiteAttendee.objects.create(
            event=self.event, name='Walk In', institute='PNU', category=self.category,
        )
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(f'/api/event/{self.event.id}/onsite')
        self.assertEqual(response.status_code, 200)
        row = response.json()['items'][0]
        self.assertEqual(row['category'], self.category.id)
        self.assertEqual(row['category_name_ko'], '학생')
        self.assertEqual(row['registration_fee'], 60000)


class SpeakerPaymentExemptionTests(TestCase):
    """A speaker on the list owes nothing - without a payment record for it."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='spk@example.com', email='spk@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Symposium', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, published=True,
        )
        self.category, = add_categories(self.event, ('Regular', 200000))
        self.event.email_template_registration = EmailTemplate.objects.create(
            subject='Registered', body='Thanks',
        )
        self.event.save()
        self.client.force_login(self.user)

    def make_attendee(self):
        attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Spea', last_name='Ker',
            nationality=1, institute='PNU', category=self.category,
        )
        self.event.attendees.add(attendee)
        return attendee

    def add_speaker(self, **extra):
        payload = {
            'name': 'Spea Ker', 'email': 'spk@example.com', 'affiliation': 'PNU',
            'is_domestic': True, 'type': 'invited',
        }
        payload.update(extra)
        self.user.is_staff = True
        self.user.save()
        return self.client.post(
            f'/api/event/{self.event.id}/speaker/add',
            data=payload, content_type='application/json',
        )

    def fresh(self, attendee):
        """Reload so the event's cached exemption list is rebuilt."""
        return Attendee.objects.select_related('event').get(id=attendee.id)

    def test_a_listed_speaker_owes_nothing(self):
        attendee = self.make_attendee()
        self.assertEqual(attendee.payment_status, 'pending')
        self.assertEqual(attendee.registration_fee, 200000)

        self.add_speaker()
        attendee = self.fresh(attendee)
        self.assertTrue(attendee.is_fee_exempt)
        self.assertEqual(attendee.registration_fee, 0)
        self.assertEqual(attendee.payment_status, 'free')

    def test_no_payment_record_is_written(self):
        attendee = self.make_attendee()
        self.add_speaker()
        # Nothing was transacted, so there is nothing to receipt and nothing to
        # show in 결제 관리.
        self.assertFalse(PaymentHistory.objects.filter(attendee=attendee).exists())

    def test_a_speaker_who_is_not_exempt_still_owes(self):
        attendee = self.make_attendee()
        self.add_speaker(is_payment_exempt=False)
        attendee = self.fresh(attendee)
        self.assertFalse(attendee.is_fee_exempt)
        self.assertEqual(attendee.payment_status, 'pending')

    def test_registering_after_being_listed_is_free(self):
        self.add_speaker()
        response = self.client.post(
            f'/api/event/{self.event.id}/register',
            data={'first_name': 'Spea', 'last_name': 'Ker', 'nationality': 1,
                  'institute': Institution.objects.create(name_en='PNU').id,
                  'job_title': 'Prof', 'category': self.category.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        attendee = Attendee.objects.select_related('event').get(event=self.event, user=self.user)
        self.assertEqual(attendee.payment_status, 'free')

    def test_matching_is_case_insensitive(self):
        attendee = self.make_attendee()
        self.add_speaker(email='SPK@Example.COM')
        self.assertEqual(self.fresh(attendee).payment_status, 'free')

    def test_unticking_the_exemption_restores_the_fee(self):
        attendee = self.make_attendee()
        self.add_speaker()
        self.assertEqual(self.fresh(attendee).payment_status, 'free')

        speaker = self.event.speakers.get()
        self.client.post(
            f'/api/event/{self.event.id}/speaker/{speaker.id}/update',
            data={'name': speaker.name, 'email': speaker.email, 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited', 'is_payment_exempt': False},
            content_type='application/json',
        )
        self.assertEqual(self.fresh(attendee).payment_status, 'pending')

    def test_removing_the_speaker_restores_the_fee(self):
        attendee = self.make_attendee()
        self.add_speaker()
        speaker = self.event.speakers.get()
        self.client.post(f'/api/event/{self.event.id}/speaker/{speaker.id}/delete',
                         data={}, content_type='application/json')
        self.assertEqual(self.fresh(attendee).payment_status, 'pending')

    def test_someone_who_already_paid_keeps_their_payment(self):
        attendee = self.make_attendee()
        paid = PaymentHistory.objects.create(
            attendee=attendee, event=self.event, amount=200000, status='completed',
            provider='toss',
        )
        self.add_speaker()
        attendee = self.fresh(attendee)
        # Paid before being listed: the listing does not exempt them, so the
        # registration keeps reading as paid and the payment is untouched.
        self.assertFalse(self.event.speakers.get().is_payment_exempt)
        self.assertEqual(attendee.payment_status, 'paid')
        self.assertEqual([p.id for p in attendee.payments.all()], [paid.id])

    def test_a_speaker_at_another_event_is_not_exempt_here(self):
        attendee = self.make_attendee()
        other = Event.objects.create(
            name='Other', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Busan', capacity=10,
        )
        other.speakers.create(name='Spea Ker', email='spk@example.com',
                              affiliation='PNU', is_domestic=True, type='invited')
        self.assertEqual(self.fresh(attendee).payment_status, 'pending')

    def test_listing_attendees_does_not_query_per_attendee(self):
        for i in range(5):
            user = User.objects.create_user(
                username=f'a{i}@example.com', email=f'a{i}@example.com', password='pw12345!aA')
            self.event.attendees.add(Attendee.objects.create(
                user=user, event=self.event, first_name=f'A{i}', last_name='T',
                nationality=1, institute='PNU', category=self.category))
        self.add_speaker()
        # The exemption list is read once from the shared event, not per row.
        # (The endpoint issues plenty of other queries; only this one matters.)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'/api/event/{self.event.id}/attendees?status=all&limit=200')
        self.assertEqual(response.status_code, 200)
        speaker_queries = [q for q in queries.captured_queries if 'main_speaker' in q['sql']]
        self.assertEqual(len(speaker_queries), 1, speaker_queries)


class AttendeeRoleTests(TestCase):
    """The roster's "type" column: general, or speaker and/or chair, read
    from the speaker list by address as the fee exemption is."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Symposium', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, published=True)
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA', is_staff=True)
        self.client.force_login(self.admin_user)

    def register(self, email):
        user = User.objects.create_user(username=email, email=email, password='pw12345!aA')
        attendee = Attendee.objects.create(user=user, event=self.event, first_name='A', last_name='B',
                                           nationality=1, institute='PNU')
        self.event.attendees.add(attendee)
        return attendee

    def roles(self):
        rows = self.client.get(f'/api/event/{self.event.id}/attendees?status=all').json()['items']
        return {row['user_email'] or row['user']['email']: (row['is_speaker'], row['is_chair']) for row in rows}

    def test_roles_follow_the_speaker_list(self):
        for email in ('plain@example.com', 'talk@example.com', 'chair@example.com',
                      'both@example.com', 'twice@example.com'):
            self.register(email)
        def speak(email, **flags):
            Speaker.objects.create(event=self.event, name='S', email=email, type='invited', **flags)
        # Address matched however it was typed; the fee exemption plays no part.
        speak(' Talk@Example.com ', is_payment_exempt=False)
        speak('chair@example.com', is_speaker=False, is_chair=True)
        speak('both@example.com', is_chair=True)
        # Listed once per role, the two rows add up.
        speak('twice@example.com')
        speak('twice@example.com', is_speaker=False, is_chair=True)
        self.assertEqual(self.roles(), {
            'plain@example.com': (False, False),
            'talk@example.com': (True, False),
            'chair@example.com': (False, True),
            'both@example.com': (True, True),
            'twice@example.com': (True, True),
        })

    def set_roles(self, attendee, roles):
        return self.client.post(f'/api/event/{self.event.id}/attendee/{attendee.id}/update',
                                data=json.dumps({'roles': roles}), content_type='application/json')

    def test_an_admin_gives_several_roles_kept_in_display_order(self):
        attendee = self.register('chair@example.com')
        Speaker.objects.create(event=self.event, name='S', email='chair@example.com', type='invited',
                               is_speaker=False, is_chair=True)
        response = self.set_roles(attendee, ['staff', 'organizer', 'staff'])
        self.assertEqual(response.status_code, 200)
        saved = response.json()['attendee']
        # Stored as given, once each, in Organizer/Chair/Speaker/Staff order;
        # the speaker list's chair is reported beside it, not stored.
        self.assertEqual((saved['roles'], saved['is_chair']), (['organizer', 'staff'], True))
        attendee.refresh_from_db()
        self.assertEqual(attendee.roles, ['organizer', 'staff'])
        # The label only: the speaker list still waives the fee.
        self.assertTrue(saved['is_fee_exempt'])
        self.assertEqual(self.set_roles(attendee, []).json()['attendee']['roles'], [])
        self.assertEqual(self.set_roles(attendee, ['speaker']).json()['attendee']['roles'], ['speaker'])
        self.assertEqual(self.set_roles(attendee, None).json()['attendee']['roles'], [])

    def test_saving_with_the_korean_institute_name_keeps_the_english_one(self):
        # The attendee modal on a Korean page sends back the Korean name it
        # showed; the English one must survive the save.
        attendee = self.register('ko@example.com')
        attendee.institute, attendee.institute_ko = 'Pusan National University', '부산대학교'
        attendee.save()
        def save(institute):
            return self.client.post(
                f'/api/event/{self.event.id}/attendee/{attendee.id}/update',
                data=json.dumps({'first_name': 'A', 'last_name': 'B', 'nationality': 1,
                                 'institute': institute}), content_type='application/json')
        for shown in ('부산대학교', 'Pusan National University'):
            self.assertEqual(save(shown).status_code, 200)
            attendee.refresh_from_db()
            self.assertEqual((attendee.institute, attendee.institute_ko),
                             ('Pusan National University', '부산대학교'))

    def test_an_unknown_role_is_refused(self):
        attendee = self.register('x@example.com')
        self.set_roles(attendee, ['staff'])
        for bad in (['boss'], 'staff', 5, [5], [['staff']], {'staff': True}, ['general']):
            response = self.set_roles(attendee, bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertEqual(response.json()['code'], 'invalid_role')
        attendee.refresh_from_db()
        self.assertEqual(attendee.roles, ['staff'])

    def test_rows_say_whether_an_abstract_was_submitted(self):
        wrote = self.register('wrote@example.com')
        self.register('silent@example.com')
        Abstract.objects.create(attendee=wrote, event=self.event, title='T', file_path='a/b.docx')
        rows = self.client.get(f'/api/event/{self.event.id}/attendees?status=all').json()['items']
        self.assertEqual({r['user']['email']: r['has_abstract'] for r in rows},
                         {'wrote@example.com': True, 'silent@example.com': False})
        row, = self.client.get(f'/api/event/{self.event.id}/attendees/export?ids={wrote.id}').json()
        self.assertTrue(row['has_abstract'])

    def test_the_export_carries_the_roles(self):
        self.register('chair@example.com')
        Speaker.objects.create(event=self.event, name='S', email='chair@example.com', type='invited',
                               is_speaker=False, is_chair=True)
        row, = self.client.get(f'/api/event/{self.event.id}/attendees/export').json()
        self.assertEqual((row['is_speaker'], row['is_chair']), (False, True))


class InstitutionEnglishNameTests(TestCase):
    """An institution's English name may not be Korean: registrations copy it,
    and the English columns of every export would carry Korean."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='st@example.com', email='st@example.com', password='pw12345!aA', is_staff=True)
        self.client.force_login(self.staff)

    def create(self, name_en, name_ko=''):
        return self.client.post('/api/institutions', data=json.dumps({'name_en': name_en, 'name_ko': name_ko}),
                                content_type='application/json')

    def update(self, institution, name_en, name_ko):
        return self.client.post(f'/api/admin/institution/{institution.id}/update',
                                data=json.dumps({'name_en': name_en, 'name_ko': name_ko}),
                                content_type='application/json')

    def test_korean_in_the_english_name_is_refused(self):
        for name in ('부산대학교', 'Pusan 대학교', 'ㅂㅅ'):
            response = self.create(name, '부산대학교')
            self.assertEqual(response.status_code, 400, name)
            self.assertEqual(response.json()['code'], 'korean_in_english_name')
        self.assertFalse(Institution.objects.exists())
        self.assertEqual(self.create('Pusan National University', '부산대학교').status_code, 200)

    def test_an_edit_may_not_put_korean_in_the_english_name(self):
        institution = Institution.objects.create(name_en='Pusan National University', name_ko='부산대학교')
        response = self.update(institution, '부산대학교', '부산대학교')
        self.assertEqual(response.json()['code'], 'korean_in_english_name')
        institution.refresh_from_db()
        self.assertEqual(institution.name_en, 'Pusan National University')

    def test_one_already_saved_in_korean_can_still_be_edited(self):
        # Kept as it was: its Korean name can change without an English one.
        institution = Institution.objects.create(name_en='부산대학교', name_ko='')
        self.assertEqual(self.update(institution, '부산대학교', '부산대학교').status_code, 200)
        institution.refresh_from_db()
        self.assertEqual((institution.name_en, institution.name_ko), ('부산대학교', '부산대학교'))
        self.assertEqual(self.update(institution, 'Pusan National University', '부산대학교').status_code, 200)


class AdminFeeWaiverTests(TestCase):
    """An event admin can excuse one registration from its category's fee."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Waivable', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, published=True,
        )
        self.category, = add_categories(self.event, ('Regular', 200000))
        user = User.objects.create_user(
            username='owes@example.com', email='owes@example.com', password='pw12345!aA')
        self.attendee = Attendee.objects.create(
            user=user, event=self.event, first_name='O', last_name='Wes',
            nationality=1, institute='PNU', category=self.category)
        self.event.attendees.add(self.attendee)

        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

    def waive(self, waived):
        return self.client.post(
            f'/api/event/{self.event.id}/attendee/{self.attendee.id}/update',
            data=json.dumps({'fee_waived': waived}),
            content_type='application/json',
        )

    def fresh(self):
        return Attendee.objects.select_related('event').get(id=self.attendee.id)

    def test_waiving_settles_the_registration(self):
        self.assertEqual(self.attendee.payment_status, 'pending')
        self.assertEqual(self.waive(True).status_code, 200)

        attendee = self.fresh()
        self.assertTrue(attendee.is_fee_exempt)
        self.assertEqual(attendee.registration_fee, 0)
        self.assertEqual(attendee.payment_status, 'free')
        self.assertFalse(attendee.has_outstanding_payment)

    def test_no_payment_record_is_written(self):
        self.waive(True)
        # Nothing was transacted, so there is nothing to receipt.
        self.assertFalse(PaymentHistory.objects.filter(attendee=self.attendee).exists())

    def test_the_waiver_can_be_lifted(self):
        self.waive(True)
        self.assertEqual(self.waive(False).status_code, 200)
        attendee = self.fresh()
        self.assertFalse(attendee.is_fee_exempt)
        self.assertEqual(attendee.registration_fee, 200000)
        self.assertEqual(attendee.payment_status, 'pending')

    def test_editing_a_registration_leaves_the_waiver_alone(self):
        # The edit form posts every other field; it must not silently un-waive.
        self.waive(True)
        response = self.client.post(
            f'/api/event/{self.event.id}/attendee/{self.attendee.id}/update',
            data=json.dumps({
                'first_name': 'Oh', 'last_name': 'Wes', 'nationality': 1,
                'institute': 'PNU', 'job_title': 'Prof',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.fresh().fee_waived)

    def test_the_admin_list_reports_the_waiver(self):
        # The roster shows a waived registration as free; the unpaid tab drops
        # it, and undoing the waiver is done by removing the registration.
        self.waive(True)
        response = self.client.get(f'/api/event/{self.event.id}/attendees')
        self.assertEqual(response.status_code, 200)
        row = next(a for a in response.json()['items'] if a['id'] == self.attendee.id)
        self.assertTrue(row['fee_waived'])
        self.assertTrue(row['is_fee_exempt'])
        self.assertEqual(row['registration_fee'], 0)
        self.assertEqual(row['payment_status'], 'free')

    def update(self, **fields):
        return self.client.post(
            f'/api/event/{self.event.id}/attendee/{self.attendee.id}/update',
            data=json.dumps(fields), content_type='application/json')

    def test_an_admin_can_move_a_registration_to_another_category(self):
        student, = add_categories(self.event, ('Student', 50000))
        self.assertEqual(self.update(category=student.id).status_code, 200)
        attendee = self.fresh()
        self.assertEqual(attendee.category, student)
        self.assertEqual(attendee.registration_fee, 50000)

    def test_a_retired_category_is_still_assignable_by_an_admin(self):
        # Registrants only see what is on offer; an admin may keep someone on
        # a tier that has since been withdrawn.
        old, = add_categories(self.event, ('Early bird', 100000))
        self.event.registration_categories.filter(id=old.id).update(is_active=False)
        self.assertEqual(self.update(category=old.id).status_code, 200)
        self.assertEqual(self.fresh().category_id, old.id)

    def test_another_events_category_is_refused(self):
        other = Event.objects.create(
            name='Other', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10)
        theirs, = add_categories(other, ('Theirs', 1))
        response = self.update(category=theirs.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_category')
        self.assertEqual(self.fresh().category, self.category)

    def test_the_update_answers_with_the_saved_row(self):
        # The admin page shows the change from this, without reloading.
        student, = add_categories(self.event, ('Student', 50000))
        body = self.update(category=student.id).json()
        self.assertEqual(body['attendee']['id'], self.attendee.id)
        self.assertEqual(body['attendee']['category'], student.id)
        self.assertEqual(body['attendee']['registration_fee'], 50000)
        self.assertEqual(body['attendee']['payment_status'], 'pending')

    def test_leaving_the_category_out_keeps_it(self):
        self.assertEqual(self.update(is_attended=True).status_code, 200)
        self.assertEqual(self.fresh().category, self.category)

    def test_a_stranger_cannot_waive_a_fee(self):
        outsider = User.objects.create_user(
            username='nosy@example.com', email='nosy@example.com', password='pw12345!aA')
        self.client.force_login(outsider)
        self.assertNotEqual(self.waive(True).status_code, 200)
        self.assertFalse(self.fresh().fee_waived)


# A 1x1 PNG, small enough to keep inline and real enough to survive the
# upload validator's magic-byte check.
PNG_BYTES = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM'
    b'IQAAAABJRU5ErkJggg=='
)


def temp_media(cls):
    """Run a test case against a throwaway MEDIA_ROOT."""
    return override_settings(MEDIA_ROOT=tempfile.mkdtemp())(cls)


@temp_media
class EmailBodyRenderTests(TestCase):
    """Markdown in, (html, inline images) out - see main.email_body."""

    def store(self, name, content=PNG_BYTES):
        return default_storage.save(f'editor/images/{name}', ContentFile(content))

    def test_markdown_becomes_html(self):
        html, _ = email_body.render('Hello **world**')
        self.assertIn('<strong>world</strong>', html)

    def test_single_newlines_survive_as_breaks(self):
        # Bodies written before rich text are plain paragraphs whose newlines
        # are real line breaks; markdown would otherwise reflow them into one.
        html, _ = email_body.render('Dear attendee,\nSee you there.')
        self.assertIn('<br', html)

    def test_a_media_image_is_inlined_by_content_id(self):
        path = self.store('poster.png')
        html, images = email_body.render(f'![poster](/media/{path})')

        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['content'], PNG_BYTES)
        self.assertEqual(images[0]['mimetype'], 'image/png')
        self.assertIn(f"cid:{images[0]['cid']}", html)
        self.assertNotIn('/media/', html)

    def test_one_image_used_twice_is_attached_once(self):
        path = self.store('logo.png')
        body = f'![logo](/media/{path})\n\n![logo again](/media/{path})'
        html, images = email_body.render(body)

        self.assertEqual(len(images), 1)
        self.assertEqual(html.count(f"cid:{images[0]['cid']}"), 2)

    def test_an_external_image_is_left_alone(self):
        html, images = email_body.render('![x](https://example.com/x.png)')
        self.assertEqual(images, [])
        self.assertIn('https://example.com/x.png', html)

    def test_a_missing_file_leaves_the_body_sendable(self):
        # A broken image beats a bounced email.
        html, images = email_body.render('![gone](/media/editor/images/gone.png)')
        self.assertEqual(images, [])
        self.assertIn('/media/editor/images/gone.png', html)

    def test_a_body_cannot_reach_outside_the_media_root(self):
        self.assertIsNone(email_body.media_path('/media/../../etc/passwd'))
        self.assertIsNone(email_body.media_path('/media//etc/passwd'))
        self.assertIsNone(email_body.media_path('https://example.com/x.png'))

    def test_attachments_skip_what_is_gone(self):
        path = default_storage.save('editor/attachments/programme.pdf', ContentFile(b'%PDF-1.4'))
        loaded = email_body.load_attachments([path, 'editor/attachments/missing.pdf'])
        self.assertEqual([f['filename'] for f in loaded], ['programme.pdf'])
        self.assertEqual(loaded[0]['mimetype'], 'application/pdf')


@temp_media
class EmailAssemblyTests(TestCase):
    """What build_email actually puts on the wire."""

    def test_a_rich_body_keeps_a_plain_text_alternative(self):
        email = build_email('Hi', 'Hello **world**', 'to@example.com', rich=True)
        # The markdown source is the text/plain part: it is written to be read.
        self.assertEqual(email.body, 'Hello **world**')
        self.assertEqual(len(email.alternatives), 1)
        html, mimetype = email.alternatives[0][0], email.alternatives[0][1]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('<strong>world</strong>', html)

    def structure(self, part, depth=0):
        """The MIME tree as (depth, content type) pairs."""
        rows = [(depth, part.get_content_type())]
        if part.is_multipart():
            for sub in part.get_payload():
                rows.extend(self.structure(sub, depth + 1))
        return rows

    def test_an_inlined_image_sits_beside_the_html_that_references_it(self):
        path = default_storage.save('editor/images/p.png', ContentFile(PNG_BYTES))
        email = build_email('Hi', f'![p](/media/{path})', 'to@example.com', rich=True)

        self.assertEqual(self.structure(email.message()), [
            (0, 'multipart/related'),
            (1, 'multipart/alternative'),
            (2, 'text/plain'),
            (2, 'text/html'),
            (1, 'image/png'),
        ])

    def test_an_attachment_stays_outside_the_related_part(self):
        # Buried inside related, some clients never offer it for download.
        image = default_storage.save('editor/images/q.png', ContentFile(PNG_BYTES))
        pdf = default_storage.save('editor/attachments/q.pdf', ContentFile(b'%PDF-1.4'))
        email = build_email('Hi', f'![q](/media/{image})', 'to@example.com',
                            rich=True, attachments=[pdf])

        self.assertEqual(self.structure(email.message()), [
            (0, 'multipart/mixed'),
            (1, 'multipart/related'),
            (2, 'multipart/alternative'),
            (3, 'text/plain'),
            (3, 'text/html'),
            (2, 'image/png'),
            (1, 'application/pdf'),
        ])

    def test_system_mail_stays_plain(self):
        # Account verification and the like: markdown would mangle the URLs.
        email = build_email('Verify', 'Go to https://x/y?a=1&b=2', 'to@example.com')
        self.assertFalse(hasattr(email, 'alternatives') and email.alternatives)
        self.assertEqual(email.body, 'Go to https://x/y?a=1&b=2')

    def test_attachments_are_attached(self):
        path = default_storage.save('editor/attachments/map.pdf', ContentFile(b'%PDF-1.4'))
        email = build_email('Hi', 'See attached', 'to@example.com',
                            rich=True, attachments=[path])
        self.assertEqual(
            [(name, mimetype) for name, _, mimetype in email.attachments],
            [('map.pdf', 'application/pdf')],
        )


@temp_media
class EmailTemplateAttachmentTests(TestCase):
    """The event admin's attachment list, saved against each template."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Mailed', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
            email_template_registration=EmailTemplate.objects.create(subject='S', body='B'),
            email_template_abstract_submission=EmailTemplate.objects.create(subject='S', body='B'),
            email_template_certificate=EmailTemplate.objects.create(subject='S', body='B'),
        )
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

        self.path = default_storage.save(
            'editor/attachments/programme.pdf', ContentFile(b'%PDF-1.4'))

    def save(self, **extra):
        payload = {
            'email_template_registration_subject': 'S',
            'email_template_registration_body': 'B',
            'email_template_abstract_submission_subject': 'S',
            'email_template_abstract_submission_body': 'B',
            'email_template_certificate_subject': 'S',
            'email_template_certificate_body': 'B',
        }
        payload.update(extra)
        return self.client.post(
            f'/api/event/{self.event.id}/emailtemplates',
            data=json.dumps(payload), content_type='application/json')

    def attachments(self):
        return list(
            self.event.email_template_registration.attachments.values_list('file_path', flat=True))

    def test_an_attachment_is_stored_against_its_template(self):
        response = self.save(email_template_registration_attachments=[
            {'url': f'/media/{self.path}', 'filename': 'programme.pdf'}])
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.attachments(), [self.path])
        attachment = self.event.email_template_registration.attachments.get()
        self.assertEqual(attachment.filename, os.path.basename(self.path))
        self.assertEqual(attachment.size, len(b'%PDF-1.4'))

    def test_saving_without_the_key_keeps_them(self):
        # An older client posting only subject and body must not wipe the list.
        self.save(email_template_registration_attachments=[{'url': f'/media/{self.path}'}])
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.attachments(), [self.path])

    def test_an_empty_list_clears_them(self):
        self.save(email_template_registration_attachments=[{'url': f'/media/{self.path}'}])
        self.save(email_template_registration_attachments=[])
        self.assertEqual(self.attachments(), [])

    def test_a_path_outside_the_media_root_is_refused(self):
        self.save(email_template_registration_attachments=[
            {'url': '/media/../../etc/passwd'},
            {'url': '/media/editor/attachments/never-uploaded.pdf'},
            {'url': 'https://example.com/evil.pdf'},
        ])
        self.assertEqual(self.attachments(), [])

    def test_the_admin_page_gets_the_attachment_list_back(self):
        # The template editor seeds its picker from this payload.
        self.save(email_template_registration_attachments=[{'url': f'/media/{self.path}'}])
        response = self.client.get(f'/api/event/{self.event.id}/email_templates')
        self.assertEqual(response.status_code, 200)
        attachments = response.json()['registration']['attachments']
        self.assertEqual([a['url'] for a in attachments], [f'/media/{self.path}'])
        self.assertEqual(attachments[0]['filename'], os.path.basename(self.path))

    def test_the_sent_email_carries_the_template_attachment(self):
        self.save(email_template_registration_attachments=[{'url': f'/media/{self.path}'}])
        paths = template_attachment_paths(self.event.email_template_registration)
        email = build_email('S', 'B', 'to@example.com', rich=True, attachments=paths)
        self.assertEqual(
            [name for name, _, _ in email.attachments], [os.path.basename(self.path)])


@temp_media
class EmailUploadRetentionTests(TestCase):
    """Files an email body depends on must outlive the orphan sweep."""

    def test_template_images_and_attachments_are_not_swept(self):
        image = default_storage.save(
            f'editor/images/{uuid.uuid4()}/keep.png', ContentFile(PNG_BYTES))
        attached = default_storage.save(
            f'editor/attachments/{uuid.uuid4()}/keep.pdf', ContentFile(b'%PDF-1.4'))
        orphan = default_storage.save(
            f'editor/images/{uuid.uuid4()}/orphan.png', ContentFile(PNG_BYTES))

        template = EmailTemplate.objects.create(subject='S', body=f'![k](/media/{image})')
        EmailAttachment.objects.create(
            template=template, file_path=attached, filename='keep.pdf', size=8)

        # min_age_hours=0 so the files just written are old enough to sweep.
        cleanup_media_files(min_age_hours=0)

        self.assertTrue(default_storage.exists(image))
        self.assertTrue(default_storage.exists(attached))
        self.assertFalse(default_storage.exists(orphan))


class InvitationTests(TestCase):
    """An admin emails a personal link; opening it registers the recipient."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Invited Symposium', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True,
            email_template_registration=EmailTemplate.objects.create(
                subject='Registered for {{ event.name }}', body='Welcome {{ attendee.first_name }}'),
        )
        self.category, = add_categories(self.event, ('Regular', 200000))
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.institution = Institution.objects.create(name_en='PNU', name_ko='부산대')

    def invite(self, emails, fee_waived=True, **extra):
        self.client.force_login(self.admin_user)
        payload = {
            'emails': emails,
            'subject': 'Come to {{ event.name }}',
            'body': 'Join here: [{{ invitation_link }}]({{ invitation_link }})',
            'fee_waived': fee_waived,
        }
        payload.update(extra)
        response = self.client.post(
            f'/api/event/{self.event.id}/invitations',
            data=json.dumps(payload), content_type='application/json')
        self.client.logout()
        return response

    def make_user(self, email='guest@example.com'):
        return User.objects.create_user(
            username=email, email=email, password='pw12345!aA',
            first_name='Gue', last_name='St', nationality=1, job_title='Prof',
            institute=self.institution,
        )

    @patch('main.invitations.send_mail')
    def test_each_address_gets_its_own_link(self, mock_send):
        response = self.invite(['a@example.com', 'b@example.com'])
        self.assertEqual(response.status_code, 200)

        rows = {inv.email: inv for inv in EventInvitation.objects.filter(event=self.event)}
        self.assertEqual(set(rows), {'a@example.com', 'b@example.com'})
        self.assertNotEqual(rows['a@example.com'].token, rows['b@example.com'].token)
        self.assertTrue(all(inv.fee_waived for inv in rows.values()))

        # The body was rendered per recipient with that recipient's link.
        sent = {call.args[2]: call.args[1] for call in mock_send.delay_on_commit.call_args_list}
        self.assertIn(f"/invite/{rows['a@example.com'].token}", sent['a@example.com'])
        self.assertIn(f"/invite/{rows['b@example.com'].token}", sent['b@example.com'])
        self.assertNotIn(rows['b@example.com'].token, sent['a@example.com'])
        self.assertEqual(mock_send.delay_on_commit.call_args.kwargs['rich'], True)

    @patch('main.invitations.send_mail')
    def test_a_body_without_the_link_is_refused(self, mock_send):
        response = self.invite(['a@example.com'], body='No link here')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'missing_link')
        mock_send.delay_on_commit.assert_not_called()

    @patch('main.invitations.send_mail')
    def test_bad_and_duplicate_addresses_are_dropped(self, mock_send):
        response = self.invite(['a@example.com', 'not-an-email', 'A@example.com', ''])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EventInvitation.objects.filter(event=self.event).count(), 1)

    def test_a_stranger_cannot_send_invitations(self):
        outsider = User.objects.create_user(
            username='nosy@example.com', email='nosy@example.com', password='pw12345!aA')
        self.client.force_login(outsider)
        response = self.client.post(
            f'/api/event/{self.event.id}/invitations',
            data=json.dumps({'emails': ['a@example.com'], 'subject': 's', 'body': '{{ invitation_link }}'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 403)

    @patch('main.invitations.send_mail')
    def test_the_invite_page_can_see_what_is_offered_without_logging_in(self, mock_send):
        self.invite(['guest@example.com'])
        token = EventInvitation.objects.get(email='guest@example.com').token
        response = self.client.get(f'/api/invitation/{token}')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['email'], 'guest@example.com')
        self.assertTrue(body['fee_waived'])
        self.assertFalse(body['is_accepted'])
        self.assertEqual(body['event_id'], self.event.id)
        self.assertEqual(body['event_name'], 'Invited Symposium')

    def test_an_unknown_token_is_a_404(self):
        self.assertEqual(self.client.get('/api/invitation/nope').status_code, 404)

    @patch('main.invitations.send_mail')
    def test_accepting_registers_from_the_profile_with_the_fee_waived(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        user = self.make_user()
        self.client.force_login(user)

        response = self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(response.status_code, 200)

        attendee = Attendee.objects.select_related('event').get(event=self.event, user=user)
        self.assertEqual(attendee.first_name, 'Gue')
        self.assertEqual(attendee.institute, 'PNU')
        self.assertEqual(attendee.institute_ko, '부산대')
        self.assertEqual(attendee.category, self.category)
        self.assertTrue(attendee.fee_waived)
        self.assertEqual(attendee.payment_status, 'free')
        # It counts as a registration everywhere the M2M is consulted.
        self.assertTrue(self.event.attendees.filter(id=attendee.id).exists())

        invitation.refresh_from_db()
        self.assertTrue(invitation.is_accepted)
        self.assertEqual(invitation.attendee, attendee)

        # The ordinary registration confirmation went out too.
        subjects = [call.args[0] for call in mock_send.delay_on_commit.call_args_list]
        self.assertIn('Registered for Invited Symposium', subjects)

    @patch('main.invitations.send_mail')
    def test_without_a_waiver_the_fee_is_still_owed(self, mock_send):
        self.invite(['guest@example.com'], fee_waived=False)
        invitation = EventInvitation.objects.get(email='guest@example.com')
        user = self.make_user()
        self.client.force_login(user)
        self.client.post(f'/api/invitation/{invitation.token}/accept')
        attendee = Attendee.objects.select_related('event').get(event=self.event, user=user)
        self.assertFalse(attendee.fee_waived)
        self.assertEqual(attendee.payment_status, 'pending')

    @patch('main.invitations.send_mail')
    def test_someone_else_cannot_spend_the_link(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        other = self.make_user('other@example.com')
        self.client.force_login(other)

        response = self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'wrong_account')
        self.assertFalse(Attendee.objects.filter(event=self.event, user=other).exists())
        invitation.refresh_from_db()
        self.assertFalse(invitation.is_accepted)

    @patch('main.invitations.send_mail')
    def test_a_verified_second_address_on_the_account_counts(self, mock_send):
        # Invited at work, signed in with a personal account that also holds
        # the work address, verified.
        from allauth.account.models import EmailAddress
        self.event.registration_deadline = date(2020, 1, 1)
        self.event.save()
        self.invite(['jp24@kaist.ac.kr'], as_speaker=True)
        invitation = EventInvitation.objects.get(email='jp24@kaist.ac.kr')
        user = self.make_user('personal@gmail.com')
        EmailAddress.objects.create(user=user, email='personal@gmail.com', verified=True, primary=True)
        EmailAddress.objects.create(user=user, email='JP24@kaist.ac.kr', verified=True, primary=False)
        self.client.force_login(user)

        response = self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Attendee.objects.filter(event=self.event, user=user).exists())
        self.assertTrue(self.event.speakers.filter(email__iexact='personal@gmail.com', is_speaker=True).exists())

    @patch('main.invitations.send_mail')
    def test_an_unverified_second_address_does_not_count(self, mock_send):
        from allauth.account.models import EmailAddress
        self.invite(['jp24@kaist.ac.kr'])
        invitation = EventInvitation.objects.get(email='jp24@kaist.ac.kr')
        user = self.make_user('personal@gmail.com')
        EmailAddress.objects.create(user=user, email='jp24@kaist.ac.kr', verified=False, primary=False)
        self.client.force_login(user)

        response = self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'wrong_account')

    @patch('main.invitations.send_mail')
    def test_the_address_match_ignores_case(self, mock_send):
        self.invite(['Guest@Example.com'])
        invitation = EventInvitation.objects.get(email='Guest@Example.com')
        user = self.make_user('guest@example.com')
        self.client.force_login(user)
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

    @patch('main.invitations.send_mail')
    def test_opening_the_link_twice_is_harmless(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        user = self.make_user()
        self.client.force_login(user)
        self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)
        self.assertEqual(Attendee.objects.filter(event=self.event, user=user).count(), 1)

    @patch('main.invitations.send_mail')
    def test_an_existing_registration_just_gains_the_waiver(self, mock_send):
        user = self.make_user()
        existing = Attendee.objects.create(
            user=user, event=self.event, first_name='Gue', last_name='St',
            nationality=1, institute='PNU', category=self.category)
        self.event.attendees.add(existing)
        self.assertEqual(existing.payment_status, 'pending')

        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(user)
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

        self.assertEqual(Attendee.objects.filter(event=self.event, user=user).count(), 1)
        existing = Attendee.objects.select_related('event').get(id=existing.id)
        self.assertTrue(existing.fee_waived)
        self.assertEqual(existing.payment_status, 'free')
        # Not a new registration, so no second confirmation email.
        subjects = [call.args[0] for call in mock_send.delay_on_commit.call_args_list]
        self.assertNotIn('Registered for Invited Symposium', subjects)

    @patch('main.invitations.send_mail')
    def test_a_full_event_refuses_even_an_invited_guest(self, mock_send):
        self.event.capacity = 1
        self.event.save()
        filler = Attendee.objects.create(
            event=self.event, first_name='Fil', last_name='Ler', nationality=1, institute='PNU')
        self.event.attendees.add(filler)

        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        response = self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'event_full')

    @patch('main.invitations.send_mail')
    def test_the_deadline_does_not_apply_to_an_invitation(self, mock_send):
        # Inviting after the deadline is the admin's override.
        self.event.registration_deadline = date(2000, 1, 1)
        self.event.save()
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

    @patch('main.invitations.send_mail')
    def test_an_invitation_only_event_needs_no_code_from_an_invitee(self, mock_send):
        self.event.invitation_code = 'SECRET'
        self.event.save()
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

    @patch('main.invitations.send_mail')
    def test_signing_up_through_the_link_registers_at_the_same_time(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')

        response = self.client.post(
            '/_allauth/browser/v1/auth/signup',
            data=json.dumps({
                'email': 'guest@example.com', 'username': 'guest@example.com',
                'password': 'a-long-passw0rd!!',
                'first_name': 'Gue', 'last_name': 'St', 'middle_initial': '',
                'nationality': 1, 'job_title': 'Prof', 'institute': self.institution.id,
                'department': '', 'disability': '', 'dietary': '',
                'invitation_token': invitation.token,
            }),
            content_type='application/json',
        )
        # 401: account created, email verification pending - the normal outcome.
        self.assertEqual(response.status_code, 401, response.content)

        user = User.objects.get(email='guest@example.com')
        attendee = Attendee.objects.select_related('event').get(event=self.event, user=user)
        self.assertEqual(attendee.institute, 'PNU')
        self.assertTrue(attendee.fee_waived)
        self.assertEqual(attendee.payment_status, 'free')
        invitation.refresh_from_db()
        self.assertEqual(invitation.attendee, attendee)

    @patch('main.invitations.send_mail')
    def test_signing_up_with_a_different_address_keeps_the_account_but_not_the_seat(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        response = self.client.post(
            '/_allauth/browser/v1/auth/signup',
            data=json.dumps({
                'email': 'someone@example.com', 'username': 'someone@example.com',
                'password': 'a-long-passw0rd!!',
                'first_name': 'Some', 'last_name': 'One', 'middle_initial': '',
                'nationality': 1, 'job_title': 'Prof', 'institute': self.institution.id,
                'department': '', 'disability': '', 'dietary': '',
                'invitation_token': invitation.token,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401, response.content)
        self.assertTrue(User.objects.filter(email='someone@example.com').exists())
        self.assertFalse(Attendee.objects.filter(event=self.event).exists())
        invitation.refresh_from_db()
        self.assertFalse(invitation.is_accepted)

    @patch('main.invitations.send_mail')
    def test_an_invited_chair_is_listed_on_acceptance(self, mock_send):
        self.invite(['guest@example.com'], fee_waived=False, as_chair=True)
        invitation = EventInvitation.objects.get(email='guest@example.com')
        # Nothing on the list yet: there is no profile to fill a row from.
        self.assertFalse(self.event.speakers.exists())

        self.client.force_login(self.make_user())
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

        listed = self.event.speakers.get()
        self.assertEqual(listed.email, 'guest@example.com')
        self.assertEqual(listed.name, 'Gue St')
        self.assertEqual(listed.affiliation, 'PNU')
        self.assertEqual(listed.affiliation_ko, '부산대')
        self.assertTrue(listed.is_domestic)
        self.assertTrue(listed.is_chair)
        self.assertFalse(listed.is_speaker)
        # The fee was not waived on the invitation, so the row does not waive it either.
        self.assertFalse(listed.is_payment_exempt)
        attendee = Attendee.objects.select_related('event').get(event=self.event)
        self.assertEqual(attendee.payment_status, 'pending')

    @patch('main.invitations.send_mail')
    def test_an_invited_speaker_with_a_waiver_is_exempt_on_the_list_too(self, mock_send):
        self.invite(['guest@example.com'], fee_waived=True, as_speaker=True, as_chair=True)
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        self.client.post(f'/api/invitation/{invitation.token}/accept')
        listed = self.event.speakers.get()
        self.assertTrue(listed.is_speaker and listed.is_chair and listed.is_payment_exempt)

    @patch('main.invitations.send_mail')
    def test_someone_already_listed_just_gains_the_role(self, mock_send):
        self.event.speakers.create(
            name='Gue St', email='Guest@Example.com', affiliation='PNU', is_domestic=True,
            type='keynote', is_speaker=True, is_chair=False, is_payment_exempt=False)
        self.invite(['guest@example.com'], fee_waived=False, as_chair=True)
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        self.client.post(f'/api/invitation/{invitation.token}/accept')

        self.assertEqual(self.event.speakers.count(), 1)
        listed = self.event.speakers.get()
        self.assertTrue(listed.is_speaker and listed.is_chair)
        self.assertEqual(listed.type, 'keynote')
        self.assertFalse(listed.is_payment_exempt)

    @patch('main.invitations.send_mail')
    def test_a_plain_invitation_adds_nobody_to_the_list(self, mock_send):
        self.invite(['guest@example.com'])
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.client.force_login(self.make_user())
        self.client.post(f'/api/invitation/{invitation.token}/accept')
        self.assertFalse(self.event.speakers.exists())

    def test_the_default_body_states_the_role(self):
        from main.apis import default_invitation_body
        from main import invitations
        body = default_invitation_body()

        def rendered(**flags):
            invitation = EventInvitation(event=self.event, email='x@example.com', token='t', **flags)
            return render_email_template(body, invitations.template_context(invitation))

        self.assertIn('as an invited speaker.', rendered(as_speaker=True))
        self.assertIn('serve as a session chair.', rendered(as_chair=True))
        self.assertIn('invited speaker and also serve as a session chair', rendered(as_speaker=True, as_chair=True))
        # A plain participant gets no role sentence, and no gap where one would be.
        plain = rendered()
        self.assertNotIn('honoured', plain)
        self.assertNotIn('participant', plain)
        self.assertIn('invite you to Invited Symposium.\n\nEvent Details:', plain)
        self.assertIn('registration fee is waived', rendered(fee_waived=True))
        self.assertNotIn('registration fee is waived', rendered())
        self.assertIn('/invite/t', rendered())
        # Sent in the committee's name, not signed by the main admin.
        self.assertTrue(plain.rstrip().endswith('The Organising Committee\nInvited Symposium'))
        self.assertNotIn('On behalf of', plain)

    @patch('main.apis.send_mail')
    @patch('main.invitations.send_mail')
    def test_an_invited_speaker_can_submit_an_abstract_after_the_deadline(self, mock_inv, mock_api):
        # The whole chain: invited as a speaker, accepted, listed, and so let
        # past the abstract deadline. Losing the role anywhere along it left
        # invited speakers registered but held to the deadline.
        import io
        import docx
        self.event.accepts_abstract = True
        self.event.abstract_deadline = date(2000, 1, 1)
        self.event.email_template_abstract_submission = EmailTemplate.objects.create(subject='S', body='B')
        self.event.save()

        self.invite(['guest@example.com'], fee_waived=True, as_speaker=True)
        invitation = EventInvitation.objects.get(email='guest@example.com')
        self.assertTrue(invitation.as_speaker)
        user = self.make_user()
        self.client.force_login(user)
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)
        self.assertTrue(self.event.speakers.filter(email__iexact='guest@example.com', is_speaker=True).exists())

        buf = io.BytesIO(); d = docx.Document(); d.add_paragraph('Abstract.'); d.save(buf)
        response = self.client.post(
            f'/api/event/{self.event.id}/abstract',
            data=json.dumps({'title': 'Invited talk', 'presentation_type': 'invited', 'file_name': 'a.docx',
                             'file_content': 'data:application/octet-stream;base64,'
                                             + base64.b64encode(buf.getvalue()).decode()}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_an_older_event_gets_an_invitation_template_on_demand(self):
        self.assertIsNone(self.event.email_template_invitation)
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/event/{self.event.id}/email_templates')
        self.assertEqual(response.status_code, 200)
        self.assertIn('{{ invitation_link }}', response.json()['invitation']['body'])
        self.event.refresh_from_db()
        self.assertIsNotNone(self.event.email_template_invitation)


class ManualEmailTests(TestCase):
    """Emails sent by hand from the attendee list render like the automatic ones."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Songdo Meeting', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Songdo Convensia', capacity=10,
        )
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        for email, first in (('ann@example.com', 'Ann'), ('bob@example.com', 'Bob')):
            user = User.objects.create_user(username=email, email=email, password='pw12345!aA')
            attendee = Attendee.objects.create(
                user=user, event=self.event, first_name=first, last_name='X',
                nationality=1, institute='PNU')
            self.event.attendees.add(attendee)
        self.client.force_login(self.admin_user)

    def send(self, to, body, subject='About {{ event.name }}'):
        return self.client.post(
            f'/api/event/{self.event.id}/send_emails',
            data=json.dumps({'to': to, 'subject': subject, 'body': body}),
            content_type='application/json')

    @patch('main.apis.send_mail')
    def test_variables_are_filled_in_per_recipient(self, mock_send):
        response = self.send(
            'ann@example.com; bob@example.com',
            'Dear {{ attendee.first_name }}, see you at {{ event.venue }}.')
        self.assertEqual(response.status_code, 200)

        sent = {call.args[2]: call.args[:2] for call in mock_send.delay_on_commit.call_args_list}
        self.assertEqual(sent['ann@example.com'][1], 'Dear Ann, see you at Songdo Convensia.')
        self.assertEqual(sent['bob@example.com'][1], 'Dear Bob, see you at Songdo Convensia.')
        self.assertEqual(sent['ann@example.com'][0], 'About Songdo Meeting')

    @patch('main.apis.send_mail')
    def test_an_address_without_a_registration_still_gets_the_email(self, mock_send):
        # Matched case-insensitively; a stranger renders the attendee blank.
        response = self.send('ANN@example.com; nobody@example.com', 'Hi {{ attendee.first_name }}!')
        self.assertEqual(response.status_code, 200)
        sent = {call.args[2]: call.args[1] for call in mock_send.delay_on_commit.call_args_list}
        self.assertEqual(sent['ANN@example.com'], 'Hi Ann!')
        self.assertEqual(sent['nobody@example.com'], 'Hi !')

    @patch('main.apis.send_mail')
    def test_a_variable_the_editor_autolinked_still_renders(self, mock_send):
        # What the rich editor made of {{ event.name }} - ".name" is a TLD.
        body = ('Welcome to {{ [event.name](http://event.name) }} at '
                '{{ [event.venue](https://event.venue/)|upper }}.')
        response = self.send('ann@example.com', body,
                             subject='{{ [event.name](http://event.name) }}')
        self.assertEqual(response.status_code, 200, response.content)
        call = mock_send.delay_on_commit.call_args
        self.assertEqual(call.args[0], 'Songdo Meeting')
        self.assertEqual(call.args[1], 'Welcome to Songdo Meeting at SONGDO CONVENSIA.')

    def test_a_real_link_next_to_a_variable_is_left_alone(self):
        body = 'See [{{ event.name }}](https://example.com/{{ event.id }})'
        out = render_email_template(body, {'event': self.event})
        self.assertEqual(out, f'See [Songdo Meeting](https://example.com/{self.event.id})')

    @patch('main.apis.send_mail')
    def test_each_presenter_reads_the_branch_for_their_own_abstract(self, mock_send):
        ann = Attendee.objects.get(user__email='ann@example.com')
        bob = Attendee.objects.get(user__email='bob@example.com')
        Abstract.objects.create(attendee=ann, event=self.event, title='Ann talk',
                                file_path='a/a.docx', presentation_type='short_talk_poster')
        Abstract.objects.create(attendee=bob, event=self.event, title='Bob flash',
                                file_path='a/b.docx', presentation_type='flash_talk_poster')
        body = ('{% if abstract.presentation_type == "short_talk" or '
                'abstract.presentation_type == "short_talk_poster" %}SHORT {{ abstract.title }}'
                '{% elif abstract.presentation_type == "flash_talk_poster" %}FLASH {{ abstract.title }}{% endif %}')
        response = self.send('ann@example.com; bob@example.com; nobody@example.com', body)
        self.assertEqual(response.status_code, 200, response.content)
        sent = {call.args[2]: call.args[1] for call in mock_send.delay_on_commit.call_args_list}
        self.assertEqual(sent['ann@example.com'], 'SHORT Ann talk')
        self.assertEqual(sent['bob@example.com'], 'FLASH Bob flash')
        # No abstract: no branch, and no error.
        self.assertEqual(sent['nobody@example.com'], '')

    @patch('main.apis.send_mail')
    def test_a_broken_template_sends_nothing(self, mock_send):
        response = self.send('ann@example.com', 'Hello {% if attendee %}unclosed')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_template')
        mock_send.delay_on_commit.assert_not_called()

    @patch('main.apis.send_mail')
    def test_markdown_and_media_pass_through_to_the_rich_sender(self, mock_send):
        body = '**Hotels**: ![map](/media/editor/images/x/map.jpg)'
        self.send('ann@example.com', body)
        call = mock_send.delay_on_commit.call_args
        self.assertEqual(call.args[1], body)
        self.assertTrue(call.kwargs['rich'])


class PaidSpeakerExemptionTests(TestCase):
    """Someone who paid and then became a speaker or chair is not exempted."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Paid First', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True,
        )
        self.category, = add_categories(self.event, ('Regular', 200000))
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.payer = User.objects.create_user(
            username='payer@example.com', email='payer@example.com', password='pw12345!aA',
            first_name='Pay', last_name='Er')
        self.attendee = Attendee.objects.create(
            user=self.payer, event=self.event, first_name='Pay', last_name='Er',
            nationality=1, institute='PNU', category=self.category)
        self.event.attendees.add(self.attendee)
        self.client.force_login(self.admin_user)

    def pay(self):
        PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=200000, status='completed')

    def add_speaker(self, **extra):
        payload = {'name': 'Pay Er', 'email': 'Payer@Example.com', 'affiliation': 'PNU',
                   'is_domestic': True, 'type': 'invited'}
        payload.update(extra)
        return self.client.post(
            f'/api/event/{self.event.id}/speaker/add',
            data=json.dumps(payload), content_type='application/json')

    def fresh_attendee(self):
        return Attendee.objects.select_related('event').get(id=self.attendee.id)

    def test_listing_a_paid_person_does_not_exempt_them(self):
        self.pay()
        # The form's default is exempt; the server overrides it for a payer.
        self.assertEqual(self.add_speaker(is_payment_exempt=True).status_code, 200)
        speaker = self.event.speakers.get()
        self.assertFalse(speaker.is_payment_exempt)
        # So the registration still reads as paid, not as free.
        self.assertEqual(self.fresh_attendee().payment_status, 'paid')

    def test_the_list_says_who_has_paid(self):
        self.pay()
        self.add_speaker()
        response = self.client.get(f'/api/event/{self.event.id}/admin/speakers')
        row = response.json()[0]
        self.assertTrue(row['has_paid'])
        self.assertFalse(row['is_payment_exempt'])

    def test_an_update_cannot_exempt_a_paid_person_either(self):
        self.pay()
        self.add_speaker()
        speaker = self.event.speakers.get()
        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/{speaker.id}/update',
            data=json.dumps({'name': 'Pay Er', 'email': 'payer@example.com', 'affiliation': 'PNU',
                             'is_domestic': True, 'type': 'invited', 'is_payment_exempt': True}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        speaker.refresh_from_db()
        self.assertFalse(speaker.is_payment_exempt)

    def test_someone_who_has_not_paid_is_exempted_as_before(self):
        self.add_speaker()
        self.assertTrue(self.event.speakers.get().is_payment_exempt)
        self.assertEqual(self.fresh_attendee().payment_status, 'free')

    def test_a_cancelled_payment_does_not_count_as_paid(self):
        PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=200000, status='cancelled')
        self.add_speaker()
        self.assertTrue(self.event.speakers.get().is_payment_exempt)

    @patch('main.invitations.send_mail')
    def test_an_invitation_does_not_waive_a_fee_already_paid(self, mock_send):
        self.pay()
        response = self.client.post(
            f'/api/event/{self.event.id}/invitations',
            data=json.dumps({'emails': ['payer@example.com'], 'subject': 's',
                             'body': '{{ invitation_link }}', 'fee_waived': True, 'as_chair': True}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        invitation = EventInvitation.objects.get(email='payer@example.com')
        self.client.force_login(self.payer)
        self.assertEqual(self.client.post(f'/api/invitation/{invitation.token}/accept').status_code, 200)

        attendee = self.fresh_attendee()
        self.assertFalse(attendee.fee_waived)
        self.assertEqual(attendee.payment_status, 'paid')
        listed = self.event.speakers.get()
        self.assertTrue(listed.is_chair)
        self.assertFalse(listed.is_payment_exempt)

    def test_the_migration_clears_exemptions_on_paid_registrations(self):
        import importlib
        from django.apps import apps as django_apps
        migration = importlib.import_module('main.migrations.0085_no_exemption_for_paid')

        # State as it could exist before this rule: paid, yet exempt both ways.
        self.pay()
        Attendee.objects.filter(id=self.attendee.id).update(fee_waived=True)
        paid_row = self.event.speakers.create(
            name='Pay Er', email='PAYER@example.com', affiliation='PNU',
            is_domestic=True, type='invited', is_payment_exempt=True)
        # Someone else, unpaid: must be left exactly as they are.
        other = User.objects.create_user(
            username='free@example.com', email='free@example.com', password='pw12345!aA')
        other_attendee = Attendee.objects.create(
            user=other, event=self.event, first_name='Fr', last_name='Ee',
            nationality=1, institute='PNU', category=self.category, fee_waived=True)
        self.event.attendees.add(other_attendee)
        unpaid_row = self.event.speakers.create(
            name='Fr Ee', email='free@example.com', affiliation='PNU',
            is_domestic=True, type='invited', is_payment_exempt=True)

        migration.forwards(django_apps, None)

        paid_row.refresh_from_db(); unpaid_row.refresh_from_db(); other_attendee.refresh_from_db()
        self.assertFalse(paid_row.is_payment_exempt)
        self.assertFalse(self.fresh_attendee().fee_waived)
        self.assertEqual(self.fresh_attendee().payment_status, 'paid')
        self.assertTrue(unpaid_row.is_payment_exempt)
        self.assertTrue(other_attendee.fee_waived)


class SpeakerLateAbstractTests(TestCase):
    """A listed speaker may submit after the deadline, once."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Late Talks', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, accepts_abstract=True, capacity_abstract=0,
            abstract_deadline=date(2000, 1, 1),
            email_template_abstract_submission=EmailTemplate.objects.create(subject='S', body='B'),
        )
        self.user = User.objects.create_user(
            username='talk@example.com', email='talk@example.com', password='pw12345!aA')
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Ta', last_name='Lk',
            nationality=1, institute='PNU')
        self.event.attendees.add(self.attendee)
        self.client.force_login(self.user)

    def list_as(self, **roles):
        self.event.speakers.create(
            name='Ta Lk', email='Talk@Example.com', affiliation='PNU',
            is_domestic=True, type='invited', **roles)

    @patch('main.apis.send_mail')
    def submit(self, mock_send):
        import io
        import docx
        buf = io.BytesIO()
        doc = docx.Document()
        doc.add_paragraph('An abstract.')
        doc.save(buf)
        return self.client.post(
            f'/api/event/{self.event.id}/abstract',
            data=json.dumps({
                'title': 'Late but listed', 'presentation_type': 'invited',
                'file_name': 'a.docx',
                'file_content': 'data:application/octet-stream;base64,'
                                + base64.b64encode(buf.getvalue()).decode(),
            }),
            content_type='application/json')

    def test_an_ordinary_registrant_is_held_to_the_deadline(self):
        response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'deadline_passed')

    def test_a_chair_is_held_to_the_deadline(self):
        self.list_as(is_speaker=False, is_chair=True)
        self.assertEqual(self.submit().json()['code'], 'deadline_passed')

    def test_a_listed_speaker_gets_past_the_deadline(self):
        self.list_as(is_speaker=True)
        response = self.submit()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Abstract.objects.filter(attendee=self.attendee).exists())

    def test_an_event_with_no_abstract_limit_set_accepts_submissions(self):
        # Events are created with the limit empty; that must mean no limit.
        Event.objects.filter(id=self.event.id).update(capacity_abstract=None)
        self.list_as(is_speaker=True)
        self.assertEqual(self.submit().status_code, 200)

    def test_but_only_once(self):
        self.list_as(is_speaker=True)
        Abstract.objects.create(attendee=self.attendee, event=self.event,
                                title='Already', file_path='a/b.docx')
        response = self.submit()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'already_submitted')


class SpeakerAbstractStatusTests(TestCase):
    """The admin speaker list says whether each speaker has submitted."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Talks', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True, accepts_abstract=True)
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        for email, first in (('done@example.com', 'Done'), ('owes@example.com', 'Owes')):
            user = User.objects.create_user(username=email, email=email, password='pw12345!aA')
            attendee = Attendee.objects.create(user=user, event=self.event, first_name=first,
                                               last_name='X', nationality=1, institute='PNU')
            self.event.attendees.add(attendee)
            self.event.speakers.create(name=f'{first} X', email=email.upper(), affiliation='PNU',
                                       is_domestic=True, type='invited')
        Abstract.objects.create(attendee=Attendee.objects.get(user__email='done@example.com'),
                                event=self.event, title='My talk', file_path='a/b.docx')
        # Same person, another event's abstract: must not count here.
        other = Event.objects.create(name='Other', start_date=date(2026, 1, 1),
                                     end_date=date(2026, 1, 2), venue='Busan', capacity=10)
        other_att = Attendee.objects.create(user=User.objects.get(email='owes@example.com'),
                                            event=other, first_name='Owes', last_name='X',
                                            nationality=1, institute='PNU')
        Abstract.objects.create(attendee=other_att, event=other, title='Elsewhere', file_path='a/c.docx')

    def test_admin_list_reports_each_speakers_abstract(self):
        self.client.force_login(self.admin_user)
        rows = {r['email'].lower(): r for r in
                self.client.get(f'/api/event/{self.event.id}/admin/speakers').json()}
        self.assertEqual(rows['done@example.com']['abstract_title'], 'My talk')
        self.assertEqual(rows['owes@example.com']['abstract_title'], '')

    def test_the_public_list_does_not_carry_it(self):
        rows = self.client.get(f'/api/event/{self.event.id}/speakers').json()
        self.assertTrue(rows)
        self.assertNotIn('abstract_title', rows[0])


@temp_media
class AdminAddAbstractTests(TestCase):
    """An event admin adds an abstract on a registrant's behalf."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Manual', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, accepts_abstract=True, capacity_abstract=1,
            abstract_deadline=date(2000, 1, 1),   # long past
            email_template_abstract_submission=EmailTemplate.objects.create(subject='S', body='B'),
        )
        category, = add_categories(self.event, ('Regular', 200000))
        self.user = User.objects.create_user(
            username='author@example.com', email='author@example.com', password='pw12345!aA')
        # Unpaid on purpose: the admin path is the override.
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Au', last_name='Thor',
            nationality=1, institute='PNU', category=category)
        self.event.attendees.add(self.attendee)
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

    def docx(self):
        import io
        import docx
        buf = io.BytesIO()
        doc = docx.Document(); doc.add_paragraph('An abstract.'); doc.save(buf)
        return 'data:application/octet-stream;base64,' + base64.b64encode(buf.getvalue()).decode()

    def add(self, **extra):
        payload = {'attendee_id': self.attendee.id, 'title': 'Sent by email',
                   'presentation_type': 'short_talk', 'file_name': 'a.docx',
                   'file_content': self.docx()}
        payload.update(extra)
        return self.client.post(f'/api/event/{self.event.id}/admin/abstract/add',
                                data=json.dumps(payload), content_type='application/json')

    @patch('main.apis.send_mail')
    def test_an_admin_adds_one_past_the_deadline_and_the_payment_gate(self, mock_send):
        response = self.add()
        self.assertEqual(response.status_code, 200, response.content)
        abstract = Abstract.objects.get(event=self.event)
        self.assertEqual(abstract.attendee, self.attendee)
        self.assertEqual(abstract.title, 'Sent by email')
        self.assertEqual(abstract.presentation_type, 'short_talk')
        self.assertTrue(default_storage.exists(abstract.file_path))
        # No confirmation unless asked for.
        mock_send.delay_on_commit.assert_not_called()

    @patch('main.apis.send_mail')
    def test_the_limit_does_not_stop_an_admin(self, mock_send):
        other = Attendee.objects.create(event=self.event, first_name='O', last_name='T',
                                        nationality=1, institute='PNU')
        Abstract.objects.create(attendee=other, event=self.event, title='First', file_path='a/b.docx')
        self.assertEqual(self.add().status_code, 200)

    @patch('main.apis.send_mail')
    def test_a_confirmation_goes_out_when_asked(self, mock_send):
        self.assertEqual(self.add(send_confirmation=True).status_code, 200)
        self.assertEqual(mock_send.delay_on_commit.call_args.args[2], 'author@example.com')

    @patch('main.apis.send_mail')
    def test_one_abstract_per_registrant_still_holds(self, mock_send):
        self.add()
        response = self.add()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'already_submitted')

    def test_another_events_registrant_is_refused(self):
        other = Event.objects.create(name='Other', start_date=date(2026, 1, 1),
                                     end_date=date(2026, 1, 2), venue='Busan', capacity=10)
        theirs = Attendee.objects.create(event=other, first_name='X', last_name='Y',
                                         nationality=1, institute='PNU')
        response = self.add(attendee_id=theirs.id)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_attendee')

    def test_the_file_is_checked_like_a_registrants_own(self):
        response = self.add(file_content='data:application/octet-stream;base64,'
                                         + base64.b64encode(b'not a document').decode())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_file')
        self.assertFalse(Abstract.objects.filter(event=self.event).exists())

    def test_a_title_is_required(self):
        self.assertEqual(self.add(title='  ').json()['code'], 'missing_title')

    def test_a_non_admin_cannot_add(self):
        self.client.force_login(self.user)
        self.assertEqual(self.add().status_code, 403)
        self.assertFalse(Abstract.objects.filter(event=self.event).exists())


class AdminListQueryCountTests(TestCase):
    """The admin page reloads every list after each save, so a list that costs
    a query per row makes every save slower the bigger the event gets. Each
    list must cost the same number of queries for 3 rows as for 9."""

    def setUp(self):
        from allauth.socialaccount.models import SocialAccount
        self.SocialAccount = SocialAccount
        self.event = Event.objects.create(
            name='Big', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, accepts_abstract=True)
        self.category, = add_categories(self.event, ('Regular', 1000))
        self.question = CustomQuestion.objects.create(
            event=self.event, question={'type': 'text', 'question': 'Q?', 'detail': '', 'options': []})
        self.institution = Institution.objects.create(name_en='PNU', name_ko='부산대')
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA', is_staff=True)
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)
        self.n = 0

    def grow(self, count):
        for _ in range(count):
            self.n += 1
            email = f'p{self.n}@example.com'
            user = User.objects.create_user(username=email, email=email, password='pw12345!aA',
                                            institute=self.institution)
            self.SocialAccount.objects.create(user=user, provider='orcid', uid=f'0000-{self.n}')
            attendee = Attendee.objects.create(user=user, event=self.event, first_name='P', last_name=str(self.n),
                                               nationality=1, institute='PNU', category=self.category)
            self.event.attendees.add(attendee)
            self.event.reviewers.add(attendee)
            CustomAnswer.objects.create(reference=self.question, attendee=attendee, question='Q?', answer='A')
            Abstract.objects.create(attendee=attendee, event=self.event, title=f'T{self.n}', file_path='a/b.docx')
            OnSiteAttendee.objects.create(event=self.event, name=f'W{self.n}', institute='PNU', category=self.category)
            PaymentHistory.objects.create(attendee=attendee, event=self.event, amount=1000, status='completed')
            # On the speaker list too, so each row's role is read as well.
            Speaker.objects.create(event=self.event, name='P', email=email, type='invited',
                                   is_chair=self.n % 2 == 0)

    def count(self, url):
        with CaptureQueriesContext(connection) as q:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(q.captured_queries)

    def test_admin_lists_do_not_query_per_row(self):
        urls = [f'/api/event/{self.event.id}/{p}' for p in
                ('attendees?status=all&limit=200', 'attendees/export?status=all', 'abstracts?limit=200',
                 'abstracts/export', 'onsite?limit=200', 'onsite/export', 'payments?limit=200',
                 'payments/export', 'reviewers', 'admin/speakers', 'eventadmins')]
        urls.append('/api/admin/users?limit=200')
        self.grow(3)
        small = {u: self.count(u) for u in urls}
        self.grow(6)
        large = {u: self.count(u) for u in urls}
        self.assertEqual(large, small, 'a list grew its query count with its row count')

    def test_linked_accounts_still_resolve(self):
        self.grow(1)
        rows = self.client.get(f'/api/event/{self.event.id}/attendees?status=all').json()['items']
        self.assertEqual(rows[0]['user']['orcid'], '0000-1')
        self.assertEqual(rows[0]['user']['institute_ko'], '부산대')
        self.assertEqual(rows[0]['custom_answers'][0]['answer'], 'A')
        abstracts = self.client.get(f'/api/event/{self.event.id}/abstracts').json()['items']
        self.assertEqual(abstracts[0]['votes'], 0)


class ListQueryScalingTests(TestCase):
    """Every list the site serves costs the same number of queries however many
    rows it returns: the speaker table, the site admin's event and user lists,
    the public event list, a user's registration history, the reviewer pages,
    and a bulk email to the whole attendee list."""

    def setUp(self):
        from allauth.socialaccount.models import SocialAccount
        self.SocialAccount = SocialAccount
        self.event = Event.objects.create(
            name='Big', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, accepts_abstract=True, published=True)
        self.category, = add_categories(self.event, ('Regular', 1000))
        self.institution = Institution.objects.create(name_en='PNU', name_ko='부산대')
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA', is_staff=True)
        self.event.admins.add(self.admin_user)
        # Registered for every event below and reviewing this one, so the
        # personal pages have as many rows as the admin ones.
        self.member = User.objects.create_user(
            username='me@example.com', email='me@example.com', password='pw12345!aA')
        mine = Attendee.objects.create(user=self.member, event=self.event, first_name='Me',
                                       last_name='X', nationality=1, institute='PNU',
                                       category=self.category)
        self.event.attendees.add(mine)
        self.event.reviewers.add(mine)
        self.vote = AbstractVote.objects.create(reviewer=mine)
        self.n = 0

    def grow(self, count):
        for _ in range(count):
            self.n += 1
            email = f'p{self.n}@example.com'
            user = User.objects.create_user(username=email, email=email, password='pw12345!aA',
                                            institute=self.institution)
            self.SocialAccount.objects.create(user=user, provider='orcid', uid=f'0000-{self.n}')
            attendee = Attendee.objects.create(user=user, event=self.event, first_name='P',
                                               last_name=str(self.n), nationality=1,
                                               institute='PNU', category=self.category)
            self.event.attendees.add(attendee)
            abstract = Abstract.objects.create(attendee=attendee, event=self.event,
                                               title=f'T{self.n}', file_path='a/b.docx')
            self.vote.voted_abstracts.add(abstract)
            PaymentHistory.objects.create(attendee=attendee, event=self.event, amount=1000,
                                          status='completed')
            # Registered, paid and submitted: every column the table derives.
            self.event.speakers.create(name=f'S{self.n}', email=email.upper(), affiliation='PNU',
                                       is_domestic=True, type='invited')

            other = Event.objects.create(
                name=f'E{self.n}', start_date=date(2026, 2, 1), end_date=date(2026, 2, 2),
                venue='Busan', capacity=10, published=True)
            other.organizer_set.create(name='Org', affiliation='PNU')
            category, = add_categories(other, ('Regular', 500))
            for field in ('email_template_registration', 'email_template_abstract_submission',
                          'email_template_certificate', 'email_template_invitation'):
                template = EmailTemplate.objects.create(subject='S', body='B')
                EmailAttachment.objects.create(template=template, file_path='editor/x.pdf',
                                               filename='x.pdf')
                setattr(other, field, template)
            other.save()
            other.speakers.create(name='Guest', email='guest@example.com', affiliation='PNU',
                                  is_domestic=True, type='invited')
            registration = Attendee.objects.create(user=self.member, event=other, first_name='Me',
                                                   last_name='X', nationality=1, institute='PNU',
                                                   category=category)
            other.attendees.add(registration)

    def count(self, method, url, user, **kwargs):
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as q:
            response = getattr(self.client, method)(url, **kwargs)
        self.assertEqual(response.status_code, 200, (url, response.content[:300]))
        return len(q.captured_queries)

    def measure(self):
        event = self.event.id
        to = '; '.join(f'p{i}@example.com' for i in range(1, self.n + 1))
        body = json.dumps({'to': to, 'subject': 'About {{ event.name }}',
                           'body': 'Dear {{ attendee.first_name }}, {{ abstract.title }} '
                                   '{{ attendee.registration_fee }} {{ event.organizers_en }}'})
        with patch('main.apis.send_mail'):
            return {
                'admin speakers': self.count('get', f'/api/event/{event}/admin/speakers', self.admin_user),
                'admin users': self.count('get', '/api/admin/users?limit=200', self.admin_user),
                'admin events': self.count('get', '/api/admin/events?limit=200', self.admin_user),
                'public events': self.count('get', '/api/events?limit=100', self.member),
                'registration history': self.count('get', '/api/me/registration-history', self.member),
                'review abstracts': self.count('get', f'/api/event/{event}/review/abstracts', self.member),
                'reviewer votes': self.count('get', f'/api/event/{event}/reviewer/vote', self.member),
                'bulk email': self.count('post', f'/api/event/{event}/send_emails', self.admin_user,
                                         data=body, content_type='application/json'),
            }

    def test_lists_do_not_query_per_row(self):
        self.grow(3)
        small = self.measure()
        self.grow(6)
        large = self.measure()
        grew = {name: (small[name], large[name]) for name in small if large[name] != small[name]}
        self.assertEqual(grew, {}, 'these grew their query count with their row count')

    def test_rows_still_carry_what_they_derive(self):
        self.grow(2)
        self.client.force_login(self.admin_user)
        speaker = self.client.get(f'/api/event/{self.event.id}/admin/speakers').json()[0]
        self.assertTrue(speaker['is_registered'])
        self.assertTrue(speaker['has_paid'])
        self.assertEqual(speaker['abstract_title'], 'T1')
        events = {e['name']: e for e in self.client.get('/api/admin/events?limit=200').json()['items']}
        self.assertEqual(events['E1']['organizers_en'], 'Org (PNU)')
        self.assertEqual(events['E1']['email_template_certificate']['attachments'][0]['filename'], 'x.pdf')
        self.assertEqual(events['E1']['registration_categories'][0]['fee'], 500)
        users = {u['email']: u for u in self.client.get('/api/admin/users?limit=200').json()['items']}
        self.assertEqual(users['p1@example.com']['orcid'], '0000-1')
        self.assertEqual(users['p1@example.com']['institute_ko'], '부산대')

        self.client.force_login(self.member)
        history = {h['event_name']: h for h in self.client.get('/api/me/registration-history').json()}
        self.assertEqual(history['E1']['registration_fee'], 500)
        self.assertEqual(history['E1']['payment_status'], 'pending')
        self.assertEqual(history['E1']['organizers_en'], 'Org (PNU)')
        review = self.client.get(f'/api/event/{self.event.id}/review/abstracts').json()
        self.assertEqual({r['attendee']['last_name'] for r in review}, {'1', '2'})
        votes = self.client.get(f'/api/event/{self.event.id}/reviewer/vote').json()
        self.assertEqual({v['title'] for v in votes['voted_abstracts']}, {'T1', 'T2'})

    @patch('main.apis.send_mail')
    def test_bulk_email_still_fills_each_recipient(self, mock_send):
        self.grow(2)
        self.client.force_login(self.admin_user)
        body = 'Dear {{ attendee.first_name }} {{ attendee.last_name }}: {{ abstract.title }}'
        response = self.client.post(
            f'/api/event/{self.event.id}/send_emails',
            data=json.dumps({'to': 'P1@example.com; p2@example.com; stranger@example.com',
                             'subject': 'S', 'body': body}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        sent = {call.args[2]: call.args[1] for call in mock_send.delay_on_commit.call_args_list}
        self.assertEqual(sent['P1@example.com'], 'Dear P 1: T1')
        self.assertEqual(sent['p2@example.com'], 'Dear P 2: T2')
        self.assertEqual(sent['stranger@example.com'], 'Dear  : ')


class PaginatedListTests(TestCase):
    """The admin lists answer a page at a time, filtered and counted on the
    server the way the tables used to do it in the browser."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Paged', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, accepts_abstract=True)
        self.paid_cat, self.free_cat = add_categories(self.event, ('Regular', 1000), ('Student', 0))
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

    def register(self, first, last, category, email=None, **fields):
        email = email or f'{first.lower()}@example.com'
        user = User.objects.create_user(username=email, email=email, password='pw12345!aA',
                                        first_name=first, last_name=last)
        attendee = Attendee.objects.create(user=user, event=self.event, first_name=first, last_name=last,
                                           nationality=1, institute='PNU', category=category, **fields)
        self.event.attendees.add(attendee)
        return attendee

    def pay(self, attendee, status='completed', amount=1000):
        return PaymentHistory.objects.create(attendee=attendee, event=self.event, amount=amount,
                                             status=status, attendee_first_name=attendee.first_name,
                                             attendee_last_name=attendee.last_name,
                                             attendee_email=attendee.email)

    def get(self, path, **params):
        response = self.client.get(f'/api/event/{self.event.id}/{path}', params)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return response.json()

    def test_sql_payment_state_agrees_with_the_property(self):
        from main.models import with_payment_state
        cases = {
            'paid': self.register('Paid', 'A', self.paid_cat),
            'pending': self.register('Pending', 'B', self.paid_cat),
            'cancelled only': self.register('Cancelled', 'C', self.paid_cat),
            'free category': self.register('Free', 'D', self.free_cat),
            'no category': self.register('Nocat', 'E', None),
            'waived': self.register('Waived', 'F', self.paid_cat, fee_waived=True),
            'speaker': self.register('Speaker', 'G', self.paid_cat),
            'deleted account speaker': self.register('Gone', 'H', self.paid_cat),
        }
        self.pay(cases['paid'])
        self.pay(cases['cancelled only'], status='cancelled')
        self.event.speakers.create(name='S', email='  SPEAKER@example.com ', affiliation='PNU',
                                   is_domestic=True, type='invited')
        gone = cases['deleted account speaker']
        gone.user_email = gone.user.email
        gone.user.delete()
        gone.refresh_from_db()
        self.event.speakers.create(name='H', email='gone@example.com', affiliation='PNU',
                                   is_domestic=True, type='invited')

        event = Event.objects.get(id=self.event.id)
        rows = {a.id: a for a in with_payment_state(event.attendees.all(), event)}
        for label, attendee in cases.items():
            fresh = Attendee.objects.get(id=attendee.id)
            row = rows[attendee.id]
            sql = 'free' if row.is_free else ('paid' if row.has_paid else 'pending')
            self.assertEqual(sql, fresh.payment_status, label)

    def test_roster_and_unpaid_tabs_split_and_count(self):
        paid = self.register('Ann', 'Lee', self.paid_cat)
        self.pay(paid)
        self.register('Bob', 'Kim', self.paid_cat)
        self.register('Cho', 'Park', self.free_cat)
        roster = self.get('attendees', status='registered')
        self.assertEqual({r['first_name'] for r in roster['items']}, {'Ann', 'Cho'})
        self.assertEqual(roster['counts'], {'registered': 2, 'unpaid': 1})
        unpaid = self.get('attendees', status='unpaid')
        self.assertEqual([r['first_name'] for r in unpaid['items']], ['Bob'])
        self.assertEqual(unpaid['total'], 1)

    def test_pages_carry_the_total_and_stay_in_order(self):
        for i in range(25):
            self.register(f'P{i:02d}', 'X', self.free_cat)
        first = self.get('attendees', limit=10)
        last = self.get('attendees', limit=10, offset=20)
        self.assertEqual((first['total'], len(first['items']), len(last['items'])), (25, 10, 5))
        self.assertEqual(first['items'][0]['first_name'], 'P00')
        self.assertEqual(last['items'][-1]['first_name'], 'P24')
        # The page size is capped, so no one asks for the whole list this way.
        self.assertEqual(self.get('attendees', limit=100000)['limit'], 200)

    def test_search_reaches_the_same_fields_the_table_did(self):
        ann = self.register('Ann', 'Lee', self.free_cat, korean_name='이안', job_title='Prof')
        self.register('Bob', 'Kim', self.free_cat)
        def found(**params):
            return [r['id'] for r in self.get('attendees', **params)['items']]
        self.assertEqual(found(search='ann lee'), [ann.id])          # full name
        self.assertEqual(found(search='이안', field='name'), [ann.id])
        self.assertEqual(found(search='ANN@EXAMPLE', field='email'), [ann.id])
        self.assertEqual(found(search='prof', field='job_title'), [ann.id])
        self.assertEqual(found(search=str(ann.attendee_nametag_id), field='id'), [ann.id])
        self.assertEqual(found(search='lee', field='email'), [])     # only the chosen field

    def test_picker_exclusions(self):
        with_abstract = self.register('Ann', 'Lee', self.free_cat)
        speaker = self.register('Bob', 'Kim', self.paid_cat)
        paid = self.register('Cho', 'Park', self.paid_cat)
        admin_reg = self.register('Dan', 'Yoo', self.free_cat, email='ea2@example.com')
        Abstract.objects.create(attendee=with_abstract, event=self.event, title='T', file_path='a/b.docx')
        self.event.speakers.create(name='B', email='BOB@example.com', affiliation='PNU',
                                   is_domestic=True, type='invited')
        self.pay(paid)
        self.event.admins.add(admin_reg.user)
        def ids(**params):
            return {r['id'] for r in self.get('attendees', status='all', **params)['items']}
        everyone = {with_abstract.id, speaker.id, paid.id, admin_reg.id}
        self.assertEqual(ids(has_abstract='false'), everyone - {with_abstract.id})
        self.assertEqual(ids(not_speaker='true'), everyone - {speaker.id})
        self.assertEqual(ids(has_completed_payment='false'), everyone - {paid.id})
        self.assertEqual(ids(not_admin='true', has_user='true'), everyone - {admin_reg.id})
        # Without any address there is nothing to list them under.
        nameless = self.register('Eve', 'No', self.free_cat)
        nameless.user.email = ''
        nameless.user.save()
        self.assertNotIn(nameless.id, ids(not_speaker='true'))

    def test_export_takes_the_same_filters_unpaged(self):
        for i in range(3):
            self.register(f'P{i}', 'X', self.free_cat)
        chosen = Attendee.objects.filter(event=self.event).order_by('id')[:2]
        ids = ','.join(str(a.id) for a in chosen)
        rows = self.client.get(f'/api/event/{self.event.id}/attendees/export', {'ids': ids}).json()
        self.assertEqual([r['id'] for r in rows], [a.id for a in chosen])
        # A selection made on the unpaid tab is found too: ids alone mean any state.
        owing = self.register('Owes', 'Y', self.paid_cat)
        rows = self.client.get(f'/api/event/{self.event.id}/attendees/export', {'ids': str(owing.id)}).json()
        self.assertEqual([r['id'] for r in rows], [owing.id])
        self.assertEqual(len(self.client.get(f'/api/event/{self.event.id}/attendees/export').json()), 3)

    def test_payments_page_with_event_wide_summary(self):
        ann = self.register('Ann', 'Lee', self.paid_cat)
        bob = self.register('Bob', 'Kim', self.paid_cat)
        self.pay(ann, amount=1000)
        self.pay(bob, amount=3000)
        self.pay(bob, status='cancelled', amount=500)
        page = self.get('payments', search='bob kim', field='name')
        self.assertEqual(page['total'], 2)
        self.assertEqual(page['summary'], {'count_all': 3, 'count_completed': 2, 'total_completed': 4000,
                                           'count_cancelled': 1, 'total_cancelled': 500})
        self.assertEqual(len(self.client.get(f'/api/event/{self.event.id}/payments/export').json()), 3)

    def test_exact_address_lookup(self):
        exact = self.register('Ann', 'Lee', self.paid_cat, email='a@x.com')
        for i in range(25):
            self.register(f'B{i}', 'X', self.free_cat, email=f'b{i}a@x.com')
        self.pay(exact)
        rows = self.get('attendees', status='all', email=' A@X.COM ')['items']
        self.assertEqual([(r['id'], r['payment_status']) for r in rows], [(exact.id, 'paid')])

    def test_picker_totals_count_what_the_picker_lists(self):
        with_abstract = self.register('Ann', 'Lee', self.free_cat)
        self.register('Bob', 'Kim', self.free_cat)
        Abstract.objects.create(attendee=with_abstract, event=self.event, title='T', file_path='a/b.docx')
        page = self.get('attendees', status='all', has_abstract='false')
        self.assertEqual((page['total'], len(page['items'])), (1, 1))

    def test_names_are_found_with_their_middle_initial(self):
        ann = self.register('Ann', 'Lee', self.free_cat, middle_initial='Q')
        ann.user.middle_initial = 'Q'
        ann.user.save()
        self.pay(ann)
        PaymentHistory.objects.filter(attendee=ann).update(attendee_middle_initial='Q')
        Abstract.objects.create(attendee=ann, event=self.event, title='T', file_path='a/b.docx')
        self.assertEqual(self.get('attendees', search='Ann Q Lee', field='name')['total'], 1)
        self.assertEqual(self.get('attendees', search='Ann Lee', field='name')['total'], 1)
        self.assertEqual(self.get('abstracts', search='ann q lee', field='presenter')['total'], 1)
        self.assertEqual(self.get('payments', search='Ann Q Lee', field='name')['total'], 1)
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        found = self.client.get('/api/admin/users', {'search': 'ann q lee', 'field': 'name'}).json()
        self.assertEqual([u['email'] for u in found['items']], ['ann@example.com'])

    def test_addresses_are_compared_as_python_reads_them(self):
        # PostgreSQL upper-cases "ß" to itself; Python to "SS". Matching is
        # done the property's way, so the tabs agree with payment_status.
        odd = self.register('Odd', 'One', self.paid_cat, email='a@straße.de')
        self.event.speakers.create(name='O', email='A@STRAßE.DE', affiliation='PNU',
                                   is_domestic=True, type='invited')
        self.assertEqual(Attendee.objects.get(id=odd.id).payment_status, 'free')
        self.assertIn(odd.id, [r['id'] for r in self.get('attendees', status='registered')['items']])
        self.assertNotIn(odd.id, [r['id'] for r in self.get('attendees', status='all', not_speaker='true')['items']])
        speaker = self.get('admin/speakers')[0]
        self.assertTrue(speaker['is_registered'])

    def test_odd_input_is_refused_not_a_server_error(self):
        self.register('Ann', 'Lee', self.free_cat)
        for path, params in (('attendees', {'ids': '²'}), ('abstracts', {'ids': '1,²'}), ('onsite', {'ids': '²'}),
                             ('payments', {'search': '²', 'field': 'number'}),
                             ('attendees', {'offset': str(10 ** 20)}), ('payments', {'offset': str(10 ** 20)})):
            response = self.client.get(f'/api/event/{self.event.id}/{path}', params)
            self.assertEqual(response.status_code, 200, (path, params, response.content[:200]))
        response = self.client.get(f'/api/event/{self.event.id}/attendees', {'search': 'a\x00b'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get('/api/institutions', {'search': '\x00'}).status_code, 400)
        response = self.client.post(f'/api/event/{self.event.id}/send_emails',
                                    data=json.dumps({'to': 'x@example.com', 'subject': 'a\x00', 'body': ''}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    @patch('main.apis.send_mail')
    def test_unstorable_text_is_refused_wherever_it_arrives(self, mock_send):
        url = f'/api/event/{self.event.id}/send_emails'
        self.assertEqual(self.client.get('/api/invitation/a%00b').status_code, 400)
        for body, content_type in ((b'{"subject": "a\\u0000"}', 'text/plain'),
                                   ('{"subject": "a\\u0000"}'.encode('utf-16'), 'application/json'),
                                   (b'{"subject": "\\ud800"}', 'application/json')):
            response = self.client.generic('POST', url, body, content_type=content_type)
            self.assertEqual(response.status_code, 400, (body[:40], content_type))
        # Text that only mentions the escape is fine, and a body too deep to
        # read is left for the view rather than crashing here.
        response = self.client.post(url, data=json.dumps({'to': 'x@example.com', 'subject': 'see \\u0000',
                                                          'body': ''}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:200])
        # Not JSON at all: the caller's mistake, said so.
        response = self.client.post(url, data='{"subject": ', content_type='application/json')
        self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_json'))
        deep = b'[' * 100000 + b'"\\u0000"' + b']' * 100000
        self.assertNotEqual(self.client.generic('GET', '/api/events', deep, content_type='application/json').status_code, 500)

    def test_unstorable_text_is_refused_however_it_is_wrapped(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        # Declared a form, read by the view as JSON anyway.
        body = json.dumps({'first_name': 'a\x00', 'last_name': 'b'})
        self.assertEqual(self.client.generic('POST', '/api/me', body,
                                             content_type='application/x-www-form-urlencoded').status_code, 400)
        # JSON inside a JSON string, which the view decodes a second time.
        body = json.dumps({'name': 'x', 'venue': 'v', 'start_date': '2026-01-01', 'end_date': '2026-01-02',
                           'capacity': 0, 'organizers': json.dumps([{'name': 'a\x00'}])})
        self.assertEqual(self.client.post('/api/admin/event/add', data=body,
                                          content_type='application/json').status_code, 400)
        self.assertFalse(Event.objects.filter(name='x').exists())

    def test_unstorable_text_in_cookies_and_multipart_fields_is_refused(self):
        from django.test import Client
        # A NUL in the session cookie used to crash the session lookup.
        # Sent as the raw header: an octal escape that Django unquotes to NUL.
        self.assertEqual(Client().get('/api/events', HTTP_COOKIE='sessionid="\\000abc"').status_code, 400)
        # Multipart text fields, as the payment gateway's callback posts them.
        self.assertEqual(self.client.post('/nicepay/callback', data={'Moid': 'a\x00b'}).status_code, 400)
        # A small multipart request stays readable to a view that parses its body.
        body = b'--xyz\r\nContent-Disposition: form-data; name="name_en"\r\n\r\nInst\r\n--xyz--\r\n'
        response = self.client.generic('POST', '/api/institutions', body,
                                       content_type='multipart/form-data; boundary=xyz')
        self.assertNotEqual(response.status_code, 500)

    def test_any_malformed_body_is_a_400(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        url = f'/api/event/{self.event.id}/eventadmin/add'
        for body in (b'{"id":"\xff"}', b'[' * 100000, b'{"id":' + b'1' * 5000 + b'}', b'{"id": '):
            response = self.client.generic('POST', url, body, content_type='application/json')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_json'), body[:20])
        # A bare JSON string inside a field, decoded a second time by the view.
        response = self.client.post(f'/api/event/{self.event.id}/update',
                                    data=json.dumps({'main_languages': json.dumps('\x00')}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_creating_an_event_with_bad_categories_creates_nothing(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        before = (Event.objects.count(), EmailTemplate.objects.count())
        base = {'name': 'E', 'venue': 'V', 'start_date': '2027-01-02', 'end_date': '2027-01-03', 'capacity': 0}
        for categories in (json.dumps([{'name': 'a\x00'}]), 'not json', json.dumps({'name': 'x'})):
            response = self.client.post('/api/admin/event/add', data=json.dumps({**base, 'registration_categories': categories}),
                                        content_type='application/json')
            self.assertEqual(response.status_code, 400, categories)
        self.assertEqual((Event.objects.count(), EmailTemplate.objects.count()), before)
        # A body that is JSON but not an object is refused, not a crash.
        response = self.client.post('/api/admin/event/add', data='[]', content_type='application/json')
        self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_json'))

    def test_a_refused_write_leaves_nothing_behind(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        question = CustomQuestion.objects.create(event=self.event, question={'type': 'text', 'question': 'Q?'})
        # Deleting the old question comes before the new one turns out to lack
        # its text; the whole request is undone with it.
        response = self.client.post(f'/api/event/{self.event.id}/questions', data=json.dumps({'questions': [{'id': -1}]}),
                                    content_type='application/json')
        self.assertEqual((response.status_code, response.json()['code']), (400, 'missing_field'))
        self.assertTrue(CustomQuestion.objects.filter(id=question.id).exists())

    def test_odd_values_are_refused_not_a_crash(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        attendee = self.register('Ann', 'Lee', self.paid_cat)
        url = f'/api/event/{self.event.id}/attendee/{attendee.id}/update'
        # Not JSON: Python's parser takes these, JSON does not.
        for raw in ('{"category": Infinity}', '{"category": NaN}', '{"category": 1e400}'):
            response = self.client.generic('POST', url, raw, content_type='application/json')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_json'), raw)
        for value in (self.paid_cat.id + 0.5, True):
            response = self.client.post(url, data=json.dumps({'category': value}), content_type='application/json')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_category'), value)
        abstract = Abstract.objects.create(attendee=attendee, event=self.event, title='T', file_path='a/b.docx')
        for title in ('x' * 1001, None, '   '):
            response = self.client.post(f'/api/event/{self.event.id}/abstract/{abstract.id}/update',
                                        data=json.dumps({'title': title}), content_type='application/json')
            self.assertEqual((response.status_code, response.json()['code']), (400, 'missing_title'), title)
        self.assertEqual(Abstract.objects.get(id=abstract.id).title, 'T')
        # JSON null as text means "not sent" on update, as on add.
        response = self.client.post(f'/api/event/{self.event.id}/update',
                                    data=json.dumps({'registration_categories': 'null'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.registration_categories.count(), 2)

    def test_blank_category_text_keeps_the_defaults(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        body = {'name': 'Blank', 'venue': 'V', 'start_date': '2027-01-02', 'end_date': '2027-01-03', 'capacity': 0,
                'registration_categories': '   '}
        self.assertEqual(self.client.post('/api/admin/event/add', data=json.dumps(body),
                                          content_type='application/json').status_code, 200)
        self.assertEqual(Event.objects.get(name='Blank').registration_categories.count(), 3)

    def test_registrations_without_a_date_lead_the_unpaid_list(self):
        newer = self.register('New', 'One', self.paid_cat)
        legacy = self.register('Old', 'One', self.paid_cat)
        Attendee.objects.filter(id=legacy.id).update(created_at=None)
        self.assertEqual([r['id'] for r in self.get('attendees', status='unpaid')['items']], [legacy.id, newer.id])

    def test_an_empty_category_array_makes_a_free_event_too(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        body = {'name': 'Free2', 'venue': 'V', 'start_date': '2027-01-02', 'end_date': '2027-01-03', 'capacity': 0,
                'registration_categories': []}
        self.assertEqual(self.client.post('/api/admin/event/add', data=json.dumps(body),
                                          content_type='application/json').status_code, 200)
        self.assertEqual(Event.objects.get(name='Free2').registration_categories.count(), 0)

    def test_an_empty_category_list_makes_a_free_event(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        body = {'name': 'Free', 'venue': 'V', 'start_date': '2027-01-02', 'end_date': '2027-01-03', 'capacity': 0,
                'registration_categories': '[]'}
        self.assertEqual(self.client.post('/api/admin/event/add', data=json.dumps(body),
                                          content_type='application/json').status_code, 200)
        self.assertEqual(Event.objects.get(name='Free').registration_categories.count(), 0)

    def test_a_missing_field_is_named_not_a_crash(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(f'/api/event/{self.event.id}/eventadmin/add', data='{}',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'code': 'missing_field', 'message': 'Missing field: id'})

    def test_text_that_only_looks_like_json_is_stored_as_text(self):
        # No view decodes a description, so a JSON-looking escape in it is
        # just text - stored as typed, not refused.
        text = '"\\u0000"'
        response = self.client.post(f'/api/event/{self.event.id}/update', data=json.dumps({'description': text}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertEqual(Event.objects.get(id=self.event.id).description, text)

    def test_a_big_upload_sent_to_a_json_endpoint_is_a_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(f'/api/event/{self.event.id}/eventadmin/add',
                                    data={'f': SimpleUploadedFile('b.bin', b'x' * 3_000_000)})
        self.assertEqual((response.status_code, response.json()['code']), (400, 'invalid_json'))

    def test_a_stray_cookie_does_not_lock_anyone_out(self):
        from django.test import Client
        self.assertEqual(Client().get('/api/events', HTTP_COOKIE='other="\\000x"').status_code, 200)

    def test_the_public_event_list_holds_its_bounds(self):
        for params in ({'offset': -5}, {'limit': -5}, {'limit': 100000}):
            response = self.client.get('/api/events', params)
            self.assertEqual(response.status_code, 200, params)
        self.assertEqual(self.client.get('/api/events', {'limit': 100000}).json()['limit'], 200)

    def test_staff_asking_for_a_missing_event_get_a_404(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/api/event/999999/attendees').status_code, 404)

    def test_ids_too_long_to_be_ids_are_dropped(self):
        self.register('Ann', 'Lee', self.free_cat)
        response = self.client.get(f'/api/event/{self.event.id}/attendees', {'ids': '1' * 5000})
        self.assertEqual((response.status_code, response.json()['total']), (200, 0))

    def test_addresses_are_read_once_per_request(self):
        for i in range(3):
            self.register(f'P{i}', 'X', self.paid_cat)
        self.event.speakers.create(name='S', email='p0@example.com', affiliation='PNU',
                                   is_domestic=True, type='invited')
        with CaptureQueriesContext(connection) as q:
            self.get('attendees', status='all', not_speaker='true', email='p1@example.com')
        scans = [x for x in q.captured_queries if '"main_attendee"."user_email"' in x['sql']
                 and 'SELECT "main_attendee"."id", "main_user"."email"' in x['sql']]
        self.assertEqual(len(scans), 1, [x['sql'][:120] for x in scans])

    def test_payment_number_found_as_the_table_shows_it(self):
        ann = self.register('Ann', 'Lee', self.paid_cat)
        bare = self.pay(ann)                      # no order id: shown as #000123
        ordered = self.pay(ann)
        ordered.toss_order_id = 'ORD-77X'
        ordered.save()
        def found(term):
            return {p['id'] for p in self.get('payments', search=term, field='number')['items']}
        self.assertIn(bare.id, found(f'{bare.id:06d}'))
        self.assertIn(bare.id, found(f'#{bare.id:06d}'))
        self.assertEqual(found('#ord-77'), {ordered.id})
        # Only what is on screen: an ordered payment's row id is not shown.
        self.assertNotIn(ordered.id, found(f'{ordered.id:06d}'))

    def test_abstracts_filter_by_type_with_chip_counts(self):
        ann = self.register('Ann', 'Lee', self.free_cat)
        bob = self.register('Bob', 'Kim', self.free_cat)
        Abstract.objects.create(attendee=ann, event=self.event, title='Poster one', file_path='a/1.docx')
        Abstract.objects.create(attendee=bob, event=self.event, title='Talk two', file_path='a/2.docx',
                                presentation_type='short_talk')
        page = self.get('abstracts', type='short_talk')
        self.assertEqual([a['title'] for a in page['items']], ['Talk two'])
        self.assertEqual(page['counts'], {'poster': 1, 'short_talk': 1, 'all': 2})
        self.assertEqual([a['title'] for a in self.get('abstracts', search='ann', field='presenter')['items']],
                         ['Poster one'])
        self.assertEqual([a['title'] for a in self.get('abstracts', search='short talk only', field='type')['items']],
                         ['Talk two'])
        # A type named the way the admin's language shows it: the browser sends
        # the codes whose label matched.
        self.assertEqual([a['title'] for a in self.get('abstracts', search='구두', field='type',
                                                       types='short_talk')['items']], ['Talk two'])
        self.assertEqual([a['title'] for a in self.get('abstracts', search='구두', types='short_talk')['items']],
                         ['Talk two'])

    def test_onsite_page_and_search(self):
        for name in ('Walk Ann', 'Walk Bob'):
            OnSiteAttendee.objects.create(event=self.event, name=name, email=f'{name[-3:]}@x.com',
                                          institute='PNU', category=self.free_cat)
        page = self.get('onsite', search='bob')
        self.assertEqual([r['name'] for r in page['items']], ['Walk Bob'])
        self.assertEqual(page['counts'], {'all': 2})
        self.assertEqual(len(self.client.get(f'/api/event/{self.event.id}/onsite/export').json()), 2)

    def test_account_search_is_staff_only_and_excludes_on_request(self):
        self.assertEqual(self.client.get('/api/admin/users').status_code, 403)
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        registered = self.register('Ann', 'Lee', self.free_cat)
        def emails(**params):
            return {u['email'] for u in self.client.get('/api/admin/users', params).json()['items']}
        self.assertEqual(emails(search='ann lee', field='name'), {'ann@example.com'})
        self.assertNotIn('ann@example.com', emails(not_registered_for=self.event.id))
        self.assertNotIn('ea@example.com', emails(not_admin_of=self.event.id))
        self.assertIn(registered.user.email, emails())

    def test_site_admin_events_hide_archived_unless_asked(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        Event.objects.create(name='Old one', start_date=date(2020, 1, 1), end_date=date(2020, 1, 2),
                             venue='Busan', capacity=0, is_archived=True)
        names = lambda **p: {e['name'] for e in self.client.get('/api/admin/events', p).json()['items']}
        self.assertEqual(names(), {'Paged'})
        self.assertEqual(names(archived='true'), {'Paged', 'Old one'})
        self.assertEqual(names(search='busan', field='venue', archived='true'), {'Old one'})

    def test_institutions_page_past_the_first_hundred(self):
        staff = User.objects.create_user(username='st@example.com', email='st@example.com',
                                         password='pw12345!aA', is_staff=True)
        self.client.force_login(staff)
        Institution.objects.bulk_create([Institution(name_en=f'Inst {i:03d}') for i in range(120)])
        page = self.client.get('/api/admin/institutions', {'offset': 100, 'limit': 50}).json()
        self.assertEqual((page['total'], len(page['items']), page['items'][0]['name_en']), (120, 20, 'Inst 100'))
        Institution.objects.create(name_en='Pusan National University', name_ko='부산대학교')
        by_field = lambda **p: [i['name_en'] for i in self.client.get('/api/admin/institutions', p).json()['items']]
        self.assertEqual(by_field(search='부산', field='name_ko'), ['Pusan National University'])
        self.assertEqual(by_field(search='부산', field='name_en'), [])


class AbstractStatusWithoutConversionTests(TestCase):
    """Every event page labels its abstract button from /registered, so that
    must say whether one was submitted; converting the file to HTML is left to
    the pages that preview it."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Talks', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True, accepts_abstract=True)
        self.user = User.objects.create_user(
            username='au@example.com', email='au@example.com', password='pw12345!aA')
        self.attendee = Attendee.objects.create(user=self.user, event=self.event, first_name='A',
                                                last_name='U', nationality=1, institute='PNU')
        self.event.attendees.add(self.attendee)
        self.client.force_login(self.user)

    def status(self):
        return self.client.get(f'/api/event/{self.event.id}/registered').json()

    def test_registered_reports_whether_an_abstract_was_submitted(self):
        self.assertFalse(self.status()['abstract_submitted'])
        Abstract.objects.create(attendee=self.attendee, event=self.event, title='T',
                                file_path='a/b.docx')
        self.assertTrue(self.status()['abstract_submitted'])

    @patch('main.schema.docx_to_html', return_value='<p>converted</p>')
    def test_own_abstract_is_converted_only_when_the_preview_asks(self, convert):
        Abstract.objects.create(attendee=self.attendee, event=self.event, title='T',
                                file_path='a/b.docx')
        url = f'/api/event/{self.event.id}/abstract'
        plain = self.client.get(url).json()
        self.assertEqual(plain['title'], 'T')
        self.assertIsNone(plain['body'])
        convert.assert_not_called()
        self.assertEqual(self.client.get(f'{url}?include_body=true').json()['body'], '<p>converted</p>')
        convert.assert_called_once()


class AdminRegisterAccountTests(TestCase):
    """An admin registers an existing account for the event, unpaid."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Phone-in', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, registration_deadline=date(2000, 1, 1),
            email_template_registration=EmailTemplate.objects.create(subject='Registered', body='Hi'))
        self.paid, self.free = add_categories(self.event, ('Regular', 200000), ('Invited', 0))
        institution = Institution.objects.create(name_en='PNU', name_ko='부산대')
        self.person = User.objects.create_user(
            username='caller@example.com', email='caller@example.com', password='pw12345!aA',
            first_name='Cal', last_name='Ler', nationality=1, job_title='Prof', institute=institution)
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.client.force_login(self.admin_user)

    def register(self, **extra):
        payload = {'email': 'Caller@Example.com', 'category': self.paid.id}
        payload.update(extra)
        return self.client.post(f'/api/event/{self.event.id}/admin/attendee/add',
                                data=json.dumps(payload), content_type='application/json')

    @patch('main.invitations.send_mail')
    def test_registers_from_the_profile_as_unpaid_past_the_deadline(self, mock_send):
        response = self.register()
        self.assertEqual(response.status_code, 200, response.content)
        attendee = Attendee.objects.select_related('event').get(event=self.event, user=self.person)
        self.assertEqual(attendee.institute_ko, '부산대')
        self.assertEqual(attendee.category, self.paid)
        self.assertEqual(attendee.payment_status, 'pending')
        self.assertTrue(self.event.attendees.filter(id=attendee.id).exists())
        mock_send.delay_on_commit.assert_not_called()

    @patch('main.invitations.send_mail')
    def test_confirmation_only_when_asked(self, mock_send):
        self.register(send_confirmation=True)
        self.assertEqual(mock_send.delay_on_commit.call_args.args[2], 'caller@example.com')

    def test_a_free_category_is_simply_registered(self):
        self.register(category=self.free.id)
        attendee = Attendee.objects.select_related('event').get(event=self.event, user=self.person)
        self.assertEqual(attendee.payment_status, 'free')

    def test_an_unknown_address_is_refused(self):
        response = self.register(email='nobody@example.com')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['code'], 'no_account')

    def test_twice_is_refused(self):
        self.register()
        self.assertEqual(self.register().json()['code'], 'already_registered')
        self.assertEqual(Attendee.objects.filter(event=self.event, user=self.person).count(), 1)

    def test_another_events_category_is_refused(self):
        other = Event.objects.create(name='Other', start_date=date(2026, 1, 1),
                                     end_date=date(2026, 1, 2), venue='Busan', capacity=10)
        theirs, = add_categories(other, ('Theirs', 1))
        self.assertEqual(self.register(category=theirs.id).json()['code'], 'invalid_category')

    def test_capacity_still_applies(self):
        self.event.capacity = 1
        self.event.save()
        filler = Attendee.objects.create(event=self.event, first_name='F', last_name='L',
                                         nationality=1, institute='PNU')
        self.event.attendees.add(filler)
        self.assertEqual(self.register().json()['code'], 'event_full')

    def test_lookup_shows_who_and_whether_registered(self):
        url = f'/api/event/{self.event.id}/admin/user-lookup?email=caller@example.com'
        body = self.client.get(url).json()
        self.assertEqual(body['name'], 'Cal Ler')
        self.assertEqual(body['institute_ko'], '부산대')
        self.assertFalse(body['already_registered'])
        self.register()
        self.assertTrue(self.client.get(url).json()['already_registered'])

    def test_lookup_is_exact_only(self):
        url = f'/api/event/{self.event.id}/admin/user-lookup?email=caller'
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_a_non_admin_can_do_neither(self):
        self.client.force_login(self.person)
        self.assertEqual(self.register().status_code, 403)
        self.assertEqual(self.client.get(
            f'/api/event/{self.event.id}/admin/user-lookup?email=caller@example.com').status_code, 403)


class ReceiptLookupTests(TestCase):
    """The receipt link has to resolve for payments with no gateway order id."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rcp@example.com', email='rcp@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Receipted', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        category, = add_categories(self.event, ('Regular', 200000))
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Rec', last_name='Eipt',
            nationality=1, institute='PNU', category=category,
        )
        self.event.attendees.add(self.attendee)
        self.client.force_login(self.user)

    def fetch(self, number):
        return self.client.get(f'/api/me/payment/{number}')

    def test_a_zero_amount_payment_reports_zero_so_printing_can_be_disabled(self):
        payment = PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=0, status='completed',
            toss_order_id='ZERO-1',
        )
        response = self.fetch(payment.toss_order_id)
        self.assertEqual(response.status_code, 200)
        # Nothing was charged, so ReceiptButtons disables both print actions.
        self.assertEqual(response.json()['amount'], 0)

    def test_a_payment_with_no_order_id_resolves_by_row_id(self):
        # What `number` falls back to; before, this 404'd for every such record.
        payment = PaymentHistory.objects.create(
            attendee=self.attendee, event=self.event, amount=1000, status='completed',
        )
        self.assertIsNone(payment.toss_order_id)
        self.assertEqual(self.fetch(str(payment.id)).status_code, 200)

    def test_another_users_receipt_is_not_readable(self):
        other = User.objects.create_user(
            username='ohter@example.com', email='other@example.com', password='pw12345!aA')
        other_attendee = Attendee.objects.create(
            user=other, event=self.event, first_name='Ot', last_name='Her',
            nationality=1, institute='PNU',
        )
        payment = PaymentHistory.objects.create(
            attendee=other_attendee, event=self.event, amount=1000, status='completed',
        )
        self.assertEqual(self.fetch(str(payment.id)).status_code, 404)


class NicePayReceiptTests(TestCase):
    """The payment columns are named after Toss but hold NicePay's ids too."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='np@example.com', email='np@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='NicePaid', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        category, = add_categories(self.event, ('Regular', 200000))
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Nice', last_name='Pay',
            nationality=1, institute='PNU', category=category,
        )
        self.event.attendees.add(self.attendee)
        self.client.force_login(self.user)

    def make_payment(self, provider, order_id):
        payment = PaymentHistory(
            attendee=self.attendee, event=self.event, amount=200000, status='completed',
            provider=provider, payment_type='카드', toss_order_id=order_id,
            toss_payment_key='TID123',
        )
        payment.copy_attendee_info(self.attendee)
        payment.copy_event_info(self.event)
        payment.save()
        return payment

    def test_a_nicepay_card_slip_points_at_nicepay_by_tid(self):
        payment = self.make_payment('nicepay', 'MOID-SLIP')
        response = self.client.get(f'/api/payment/{payment.toss_order_id}/card-receipt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['receipt_url'],
            'https://npg.nicepay.co.kr/issue/IssueLoader.do?TID=TID123&type=0')

    def test_a_nicepay_receipt_is_readable_by_its_moid(self):
        payment = self.make_payment('nicepay', 'MOID-1')
        response = self.client.get(f'/api/me/payment/{payment.toss_order_id}')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['provider'], 'nicepay')
        self.assertEqual(body['amount'], 200000)

    def test_the_payment_history_list_reports_the_provider(self):
        self.make_payment('nicepay', 'MOID-2')
        response = self.client.get('/api/me/payment-history')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p['provider'] for p in response.json()], ['nicepay'])

    def test_the_admin_payment_list_reports_the_provider(self):
        """결제 관리 labels the gateway from this, not from payment_type."""
        self.make_payment('nicepay', 'MOID-4')
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(f'/api/event/{self.event.id}/payments')
        self.assertEqual(response.status_code, 200)
        row = response.json()['items'][0]
        self.assertEqual(row['provider'], 'nicepay')
        # Both gateways say '카드', so the type alone cannot name the gateway.
        self.assertEqual(row['payment_type'], '카드')

    @patch('main.apis.requests.get')
    def test_a_nicepay_card_slip_never_asks_toss(self, mock_get):
        """Both providers label a card payment '카드'; NicePay's slip is its own URL."""
        payment = self.make_payment('nicepay', 'MOID-3')
        response = self.client.get(f'/api/payment/{payment.toss_order_id}/card-receipt')
        self.assertEqual(response.status_code, 200)
        self.assertIn('npg.nicepay.co.kr', response.json()['receipt_url'])
        mock_get.assert_not_called()

    @override_settings(TOSS_SECRET_KEY='sk_test', TOSS_API_URL='https://api.tosspayments.com/v1')
    @patch('main.apis.requests.get')
    def test_a_toss_card_slip_still_works(self, mock_get):
        mock_get.return_value.ok = True
        mock_get.return_value.json.return_value = {'receipt': {'url': 'https://receipt.example'}}
        payment = self.make_payment('toss', 'TOSS-1')
        response = self.client.get(f'/api/payment/{payment.toss_order_id}/card-receipt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['receipt_url'], 'https://receipt.example')
        mock_get.assert_called_once()


class DuplicateSpeakerTests(TestCase):
    """One row per person: email is the identity the fee waiver matches on."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dup@example.com', email='dup@example.com', password='pw12345!aA',
            is_staff=True,
        )
        self.event = Event.objects.create(
            name='Duplicated', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10,
        )
        self.client.force_login(self.user)

    def add(self, email='spk@example.com', name='Spea Ker'):
        return self.client.post(
            f'/api/event/{self.event.id}/speaker/add',
            data={'name': name, 'email': email, 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited'},
            content_type='application/json',
        )

    def test_the_same_person_cannot_be_added_twice(self):
        self.assertEqual(self.add().status_code, 200)
        response = self.add()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'duplicate_speaker')
        self.assertEqual(self.event.speakers.count(), 1)

    def test_a_row_is_a_speaker_unless_told_otherwise(self):
        self.add()
        speaker = self.event.speakers.get()
        self.assertTrue(speaker.is_speaker)
        self.assertFalse(speaker.is_chair)

    def test_a_person_can_be_a_chair_or_both(self):
        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/add',
            data={'name': 'Cha Ir', 'email': 'chair@example.com', 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited', 'is_speaker': False, 'is_chair': True},
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        chair = self.event.speakers.get(email='chair@example.com')
        self.assertFalse(chair.is_speaker)
        self.assertTrue(chair.is_chair)

        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/{chair.id}/update',
            data={'name': 'Cha Ir', 'email': 'chair@example.com', 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited', 'is_speaker': True, 'is_chair': True},
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        chair.refresh_from_db()
        self.assertTrue(chair.is_speaker and chair.is_chair)

    def test_a_row_with_neither_role_is_refused(self):
        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/add',
            data={'name': 'No Body', 'email': 'nobody@example.com', 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited', 'is_speaker': False, 'is_chair': False},
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'missing_role')

    def test_duplicate_detection_ignores_case_and_padding(self):
        self.add()
        self.assertEqual(self.add(email='  SPK@Example.COM  ').status_code, 400)
        self.assertEqual(self.event.speakers.count(), 1)

    def test_a_different_person_is_still_accepted(self):
        self.add()
        self.assertEqual(self.add(email='other@example.com', name='Oth Er').status_code, 200)
        self.assertEqual(self.event.speakers.count(), 2)

    def test_the_same_person_may_speak_at_another_event(self):
        self.add()
        other = Event.objects.create(
            name='Other', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Busan', capacity=10,
        )
        response = self.client.post(
            f'/api/event/{other.id}/speaker/add',
            data={'name': 'Spea Ker', 'email': 'spk@example.com', 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_editing_a_speaker_onto_another_speakers_email_is_refused(self):
        self.add()
        self.add(email='other@example.com', name='Oth Er')
        second = self.event.speakers.get(email='other@example.com')
        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/{second.id}/update',
            data={'name': 'Oth Er', 'email': 'spk@example.com', 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'duplicate_speaker')

    def test_editing_a_speaker_keeping_their_own_email_is_fine(self):
        self.add()
        speaker = self.event.speakers.get()
        response = self.client.post(
            f'/api/event/{self.event.id}/speaker/{speaker.id}/update',
            data={'name': 'Renamed', 'email': 'spk@example.com', 'affiliation': 'KAIST',
                  'is_domestic': True, 'type': 'keynote'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        speaker.refresh_from_db()
        self.assertEqual(speaker.name, 'Renamed')


class CsrfTokenReuseTests(TestCase):
    """/api/csrftoken must reuse the caller's secret, not mint a new one.

    The frontend layout hands the browser whatever this returns and renders the
    same value into the page. If a fresh secret came back on every request, the
    next page load - another tab, a link prefetch - would replace the cookie and
    invalidate the token already sitting in the page the user is looking at, so
    their next POST would 403. That is what made social login fail on some
    machines and not others.
    """

    @staticmethod
    def secret_of(token):
        from django.middleware.csrf import _unmask_cipher_token
        return _unmask_cipher_token(token) if len(token) == 64 else token

    def fetch(self, client):
        return client.get('/api/csrftoken').json()['csrftoken']

    def test_the_secret_is_reused_when_the_cookie_is_sent(self):
        client = Client()
        first = self.fetch(client)
        client.cookies['csrftoken'] = first
        again = self.fetch(client)
        # Re-masked each call, so the strings differ - the secret must not.
        self.assertEqual(self.secret_of(first), self.secret_of(again))

    def test_a_token_stays_valid_across_later_loads(self):
        client = Client()
        rendered_into_the_page = self.fetch(client)
        client.cookies['csrftoken'] = rendered_into_the_page
        for _ in range(3):
            client.cookies['csrftoken'] = self.fetch(client)

        poster = Client(enforce_csrf_checks=True)
        poster.cookies['csrftoken'] = client.cookies['csrftoken'].value
        response = poster.post(
            '/api/event/1/register',
            data={}, content_type='application/json',
            HTTP_X_CSRFTOKEN=rendered_into_the_page,
        )
        self.assertNotEqual(response.status_code, 403)

    def test_an_unrelated_secret_is_still_rejected(self):
        stranger = self.fetch(Client())
        poster = Client(enforce_csrf_checks=True)
        poster.cookies['csrftoken'] = self.fetch(Client())
        response = poster.post(
            '/api/event/1/register',
            data={}, content_type='application/json',
            HTTP_X_CSRFTOKEN=stranger,
        )
        self.assertEqual(response.status_code, 403)


class AbstractUploadErrorTests(TestCase):
    """A missing file and a damaged one are different problems."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='up@example.com', email='up@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Uploads', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, capacity_abstract=10, accepts_abstract=True,
        )
        self.event.email_template_abstract_submission = EmailTemplate.objects.create(
            subject='Submitted', body='Thanks')
        self.event.save()
        attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Up', last_name='Load',
            nationality=1, institute='PNU',
        )
        self.event.attendees.add(attendee)
        self.client.force_login(self.user)

    @staticmethod
    def docx_data_url():
        import base64, io as _io, zipfile
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types/>')
            z.writestr('word/document.xml', '<?xml version="1.0"?><document/>')
        return 'data:application/octet-stream;base64,' + base64.b64encode(buf.getvalue()).decode()

    def submit(self, file_content, file_name='abstract.docx'):
        return self.client.post(
            f'/api/event/{self.event.id}/abstract',
            data={'title': 'T', 'presentation_type': 'poster',
                  'file_name': file_name, 'file_content': file_content},
            content_type='application/json',
        )

    def test_a_real_docx_is_accepted(self):
        self.assertEqual(self.submit(self.docx_data_url()).status_code, 200)

    def test_a_title_that_cannot_be_stored_is_refused_before_the_file_is(self):
        with patch('main.apis.store_abstract_file') as store:
            for title in ('', '   ', 'x' * 1001):
                response = self.client.post(
                    f'/api/event/{self.event.id}/abstract',
                    data={'title': title, 'file_name': 'a.docx', 'file_content': self.docx_data_url()},
                    content_type='application/json')
                self.assertEqual((response.status_code, response.json()['code']), (400, 'missing_title'))
            store.assert_not_called()

    def test_an_uppercase_extension_is_accepted(self):
        # The client used to refuse these before they ever got here.
        self.assertEqual(self.submit(self.docx_data_url(), 'ABSTRACT.DOCX').status_code, 200)

    def test_a_missing_file_says_so(self):
        for empty in ('', 'null', 'undefined'):
            response = self.submit(empty)
            self.assertEqual(response.status_code, 400, empty)
            self.assertEqual(response.json()['code'], 'no_file', empty)

    def test_a_truncated_upload_is_reported_as_such(self):
        url = self.docx_data_url()
        response = self.submit(url[:len(url) - 3] + 'A')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_file')


class DatabaseBackupTests(TestCase):
    """Backup and restore are superuser-only; the archive is a real gzip."""

    def setUp(self):
        self.superuser = User.objects.create_user(
            username='root@example.com', email='root@example.com',
            password='pw12345!aA', is_staff=True, is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username='staff@example.com', email='staff@example.com',
            password='pw12345!aA', is_staff=True,
        )

    def test_superuser_downloads_a_gzip_backup(self):
        self.client.force_login(self.superuser)
        response = self.client.get('/api/admin/backup')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/gzip')
        self.assertIn('ieum-backup-', response.get('Content-Disposition', ''))
        body = b''.join(response.streaming_content)
        self.assertEqual(body[:2], b'\x1f\x8b')  # gzip magic

    def test_a_backup_contains_the_sql_and_manifest(self):
        import io as _io, tarfile
        self.client.force_login(self.superuser)
        body = b''.join(self.client.get('/api/admin/backup').streaming_content)
        with tarfile.open(fileobj=_io.BytesIO(body)) as tar:
            names = tar.getnames()
        self.assertIn('database.sql', names)
        self.assertIn('manifest.json', names)

    def test_backup_requires_superuser(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/api/admin/backup').status_code, 403)

    def test_backup_requires_authentication(self):
        self.assertEqual(self.client.get('/api/admin/backup').status_code, 401)

    def test_restore_requires_superuser(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.staff)
        response = self.client.post(
            '/api/admin/restore',
            {'file': SimpleUploadedFile('b.tar.gz', b'x', content_type='application/gzip')})
        self.assertEqual(response.status_code, 403)

    def test_restore_requires_authentication(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        response = self.client.post(
            '/api/admin/restore',
            {'file': SimpleUploadedFile('b.tar.gz', b'x', content_type='application/gzip')})
        self.assertEqual(response.status_code, 401)

    def test_restore_rejects_a_file_that_is_not_a_backup(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.superuser)
        response = self.client.post(
            '/api/admin/restore',
            {'file': SimpleUploadedFile('x.tar.gz', b'not an archive',
                                        content_type='application/gzip')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'restore_failed')


class EmailTemplateSandboxTests(TestCase):
    """Event admins write the templates, so a template sees plain fields only."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Sandboxed', start_date=date(2026, 3, 4), end_date=date(2026, 3, 5),
            venue='Busan', capacity=10, published=True,
        )
        self.superuser = User.objects.create_superuser(
            username='root@example.com', email='root@example.com', password='pw12345!aA')
        self.event.admins.add(self.superuser)
        self.attendee = Attendee.objects.create(
            user=self.superuser, event=self.event, first_name='Root', last_name='User',
            nationality=1, institute='PNU')

    def render(self, template, **context):
        return render_email_template(template, {'event': self.event, 'attendee': self.attendee, **context})

    def test_a_template_cannot_reach_other_users(self):
        rendered = self.render(
            '[{% for u in event.admins.all %}{{ u.password }}{% endfor %}]'
            '[{{ attendee.user.password }}][{{ attendee.user }}][{{ event.main_admin }}]')
        self.assertEqual(rendered, '[][][][]')

    def test_a_template_cannot_rotate_an_api_key(self):
        from main.models import ApiKey
        key, _ = ApiKey.generate('mcp', self.superuser)
        rendered = self.render(
            '{% for k in attendee.user.api_keys.all %}{{ k.rotate }}{% endfor %}'
            '{% for a in event.admins.all %}{% for k in a.api_keys.all %}{{ k.rotate }}{% endfor %}{% endfor %}')
        self.assertEqual(rendered, '')
        key_hash = key.key_hash
        key.refresh_from_db()
        self.assertEqual(key.key_hash, key_hash)

    def test_whitelisted_fields_still_render(self):
        abstract = Abstract.objects.create(
            attendee=self.attendee, event=self.event, title='On Folding',
            presentation_type='short_talk', file_path='abstracts/x/a.docx')
        rendered = self.render(
            "{{ attendee.first_name }}|{{ attendee.email }}|{{ event.name }}|"
            "{{ event.start_date|date:'F d, Y' }}|{{ abstract.title }}|"
            "{{ abstract.get_presentation_type_display }}|{{ event }}",
            abstract=abstract)
        self.assertEqual(
            rendered,
            'Root|root@example.com|Sandboxed|March 04, 2026|On Folding|Short talk only|Sandboxed')

    def test_includes_and_tag_libraries_are_unavailable(self):
        from django.template import TemplateSyntaxError
        from django.template.exceptions import TemplateDoesNotExist
        with self.assertRaises(TemplateSyntaxError):
            self.render('{% load static %}')
        with self.assertRaises(TemplateDoesNotExist):
            self.render("{% include 'account/email/base_message.txt' %}")

    def test_a_model_outside_the_whitelist_is_refused(self):
        with self.assertRaises(TypeError):
            render_email_template('{{ u }}', {'u': self.superuser})


class PublicSpeakerListTests(TestCase):
    """The public speaker list hides addresses, payment state and draft events."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Talks', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True,
        )
        self.event.speakers.create(name='Speaker One', email='one@example.com', type='invited')
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.outsider = User.objects.create_user(
            username='out@example.com', email='out@example.com', password='pw12345!aA')

    def test_public_list_leaves_out_email_and_payment(self):
        response = self.client.get(f'/api/event/{self.event.id}/speakers')
        self.assertEqual(response.status_code, 200)
        row = response.json()[0]
        self.assertEqual(row['name'], 'Speaker One')
        for field in ('email', 'is_payment_exempt', 'is_registered', 'has_paid'):
            self.assertNotIn(field, row)

    def test_draft_and_archived_events_are_hidden(self):
        self.event.published = False
        self.event.save()
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/speakers').status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/speakers').status_code, 404)
        self.event.published, self.event.is_archived = True, True
        self.event.save()
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/speakers').status_code, 404)

    def test_unknown_event_is_not_found(self):
        self.assertEqual(self.client.get('/api/event/999999/speakers').status_code, 404)

    def test_admin_list_keeps_email_for_event_admins_only(self):
        url = f'/api/event/{self.event.id}/admin/speakers'
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['email'], 'one@example.com')


class EventCreatorAdminTests(TestCase):
    """Whoever creates an event is on its admin list for good."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff@example.com', email='staff@example.com', password='pw12345!aA', is_staff=True)
        self.client.force_login(self.staff)

    def create_event(self):
        response = self.client.post('/api/admin/event/add', data=json.dumps({
            'name': 'Made Here', 'venue': 'Seoul', 'start_date': '2026-05-01',
            'end_date': '2026-05-02', 'capacity': 10,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return Event.objects.get(name='Made Here')

    def test_creator_is_recorded_and_made_admin(self):
        event = self.create_event()
        self.assertEqual(event.created_by, self.staff)
        self.assertIn(self.staff, event.admins.all())

    def test_creator_cannot_be_removed(self):
        event = self.create_event()
        other = User.objects.create_user(
            username='co@example.com', email='co@example.com', password='pw12345!aA')
        event.admins.add(other)
        self.client.force_login(other)
        response = self.client.post(f'/api/event/{event.id}/eventadmin/{self.staff.id}/delete')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'creator_admin')
        self.assertIn(self.staff, event.admins.all())
        # Other admins can still be removed.
        self.client.force_login(self.staff)
        response = self.client.post(f'/api/event/{event.id}/eventadmin/{other.id}/delete')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(other, event.admins.all())


@nicepay_settings
class NicePayVirtualAccountTests(TestCase):
    """가상계좌 is not offered, and one slipped in through the window is undone."""

    setUp = NicePayCallbackTests.setUp
    callback_params = NicePayCallbackTests.callback_params
    approval_response = NicePayCallbackTests.approval_response

    def test_prepare_refuses_vbank(self):
        self.client.force_login(self.user)
        s = PaymentSettings.get_instance()
        s.domestic_provider = 'nicepay'
        s.save()
        response = self.client.post(
            '/api/payment/nicepay/prepare',
            data={'eventId': self.event.id, 'payMethod': 'VBANK'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_pay_method')

    @patch('main.nicepay.net_cancel')
    @patch('main.nicepay._post_form')
    def test_vbank_approval_is_net_cancelled_and_not_recorded(self, mock_post, mock_net_cancel):
        result = self.approval_response()
        result.update({'PayMethod': 'VBANK', 'ResultCode': '4100', 'ResultMsg': '가상계좌 발급 성공'})
        mock_post.return_value = result

        response = self.client.post('/nicepay/callback', self.callback_params(PayMethod='VBANK'))

        self.assertEqual(response.status_code, 302)
        self.assertNotIn('payment/success', response['Location'])
        self.assertTrue(mock_net_cancel.called)
        self.assertFalse(PaymentHistory.objects.filter(attendee=self.attendee).exists())


class ReviewerPrivacyTests(TestCase):
    """Reviewers see who wrote an abstract and its text, nothing more."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Private Review', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, accepts_abstract=True, published=True,
            abstract_deadline=date(2020, 1, 1),
        )
        self.reviewer_user = User.objects.create_user(
            username='rev@example.com', email='rev@example.com', password='pw12345!aA')
        self.reviewer = Attendee.objects.create(
            user=self.reviewer_user, event=self.event, first_name='Rev', last_name='Iewer',
            nationality=1, institute='PNU')
        self.event.reviewers.add(self.reviewer)
        AbstractVote.objects.create(reviewer=self.reviewer)
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.author_user = User.objects.create_user(
            username='au@example.com', email='au@example.com', password='pw12345!aA')
        author = Attendee.objects.create(
            user=self.author_user, event=self.event, first_name='Au', last_name='Thor',
            nationality=1, institute='KAIST', disability='wheelchair', dietary='vegan')
        self.abstract = Abstract.objects.create(
            event=self.event, attendee=author, title='Secret Result',
            file_path=f'abstracts/{uuid.uuid4()}/a.docx', presentation_type='short_talk_poster')

    def assert_author_is_minimal(self, row):
        self.assertEqual(row['attendee']['name'], 'Au Thor')
        self.assertEqual(row['attendee']['institute'], 'KAIST')
        for field in ('disability', 'dietary', 'user', 'user_email', 'payment_status', 'custom_answers'):
            self.assertNotIn(field, row['attendee'])
        self.assertNotIn('link', row)
        self.assertNotIn('votes', row)

    def test_review_list_and_detail_hide_the_registration(self):
        self.client.force_login(self.reviewer_user)
        rows = self.client.get(f'/api/event/{self.event.id}/review/abstracts').json()
        self.assert_author_is_minimal(rows[0])
        response = self.client.get(f'/api/event/{self.event.id}/abstract/{self.abstract.id}')
        self.assertEqual(response.status_code, 200)
        self.assert_author_is_minimal(response.json())
        self.assertIn('body', response.json())

    def test_reviewer_votes_round_trip(self):
        self.client.force_login(self.reviewer_user)
        response = self.client.post(
            f'/api/event/{self.event.id}/reviewer/vote',
            data=json.dumps({'voted_abstracts': [self.abstract.id]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f'/api/event/{self.event.id}/reviewer/vote')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('reviewer', response.json())
        self.assert_author_is_minimal(response.json()['voted_abstracts'][0])

    def test_reviewers_cannot_use_the_admin_list(self):
        self.client.force_login(self.reviewer_user)
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/abstracts').status_code, 403)

    def test_others_are_refused(self):
        self.client.force_login(self.author_user)
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/review/abstracts').status_code, 403)
        self.assertEqual(
            self.client.get(f'/api/event/{self.event.id}/abstract/{self.abstract.id}').status_code, 403)
        self.assertEqual(self.client.get(f'/api/event/{self.event.id}/reviewer/vote').status_code, 403)
        response = self.client.post(
            f'/api/event/{self.event.id}/reviewer/vote',
            data=json.dumps({'voted_abstracts': [self.abstract.id]}), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_abstract_file_goes_to_author_and_admins_only(self):
        url = '/api/media-auth/abstract'
        uri = '/' + self.abstract.file_path

        def status(user):
            self.client.logout()
            if user:
                self.client.force_login(user)
            return self.client.get(url, HTTP_X_FORWARDED_URI=uri).status_code

        staff = User.objects.create_user(
            username='st@example.com', email='st@example.com', password='pw12345!aA', is_staff=True)
        self.assertEqual(status(None), 401)
        self.assertEqual(status(self.author_user), 200)
        self.assertEqual(status(self.admin_user), 200)
        self.assertEqual(status(staff), 200)
        self.assertEqual(status(self.reviewer_user), 403)
        self.client.force_login(self.author_user)
        self.assertEqual(
            self.client.get(url, HTTP_X_FORWARDED_URI=f'/abstracts/{uuid.uuid4()}/x.docx').status_code, 404)


class PublicEventPrivacyTests(TestCase):
    """Public event data carries no addresses, and drafts stay hidden."""

    def setUp(self):
        self.event = Event.objects.create(
            name='Open Day', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, published=True,
        )
        self.event.organizer_set.create(name='Org Anizer', email='org@example.com', affiliation='PNU')
        self.event.custom_questions.create(question={'type': 'text', 'question': 'Q?'})
        self.admin_user = User.objects.create_user(
            username='ea@example.com', email='ea@example.com', password='pw12345!aA')
        self.event.admins.add(self.admin_user)
        self.outsider = User.objects.create_user(
            username='out@example.com', email='out@example.com', password='pw12345!aA')

    def test_organizer_email_is_not_public(self):
        for url in (f'/api/event/{self.event.id}', '/api/events'):
            body = self.client.get(url).content.decode()
            self.assertIn('Org Anizer', body)
            self.assertNotIn('org@example.com', body)

    def test_draft_questions_are_hidden_from_outsiders(self):
        url = f'/api/event/{self.event.id}/questions'
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.event.published = False
        self.event.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.admin_user)
        self.assertEqual(self.client.get(url).status_code, 200)
        # An archived event's own admin still manages its questions.
        self.event.published, self.event.is_archived = True, True
        self.event.save()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
