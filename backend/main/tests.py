from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from main import nicepay
from main.utils import render_email_template
from main.models import Abstract, AbstractVote, Attendee, Institution, EmailTemplate, Event, NicePayTransaction, PaymentHistory, PaymentSettings

User = get_user_model()

# Merchant key and signature vector published in the NicePay manual
# (https://developers.nicepay.co.kr/manual-auth.php).
TEST_MID = 'nicepay00m'
TEST_MERCHANT_KEY = 'EYzu8jGGMfqaDEp76gSckuvnaHHu+bC4opsSN6lHv3b2lurNYkVXrZ7Z1AoqQnXI3eLuaUFyoRNC6FkrzVjceg=='

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
            venue='Seoul', capacity=100, registration_fee=1004,
        )
        self.attendee = Attendee.objects.create(
            user=self.user, event=self.event, first_name='Test', last_name='Payer',
            nationality=410, institute='KASRA',
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
        result = nicepay.cancel(tid='TID1', cancel_amount=1004, reason='관리자 취소')
        self.assertEqual(result['ResultCode'], '2001')

        payload = mock_post.call_args[0][1]
        self.assertEqual(payload['PartialCancelCode'], '0')
        self.assertEqual(payload['CancelAmt'], '1004')
        self.assertEqual(
            payload['SignData'], nicepay.cancel_sign_data('1004', payload['EdiDate'])
        )

    @patch('main.nicepay._post_form')
    def test_cancel_rejection_raises(self, mock_post):
        mock_post.return_value = {'ResultCode': '4000', 'ResultMsg': '취소 불가'}
        with self.assertRaises(nicepay.NicePayError) as ctx:
            nicepay.cancel(tid='TID1', cancel_amount=1004)
        self.assertEqual(ctx.exception.code, '4000')


@nicepay_settings
class PaymentProviderSelectionTests(TestCase):
    """One provider per category, enforced server-side rather than in the UI."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@example.com', password='pw12345!'
        )
        self.event = Event.objects.create(
            name='Paid Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100, registration_fee=1004,
        )
        Attendee.objects.create(
            user=self.user, event=self.event, first_name='Buy', last_name='Er',
            nationality=410, institute='KASRA',
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
class TieredRegistrationFeeTests(TestCase):
    """Per-tier pricing. The server must price from the stored tier, never the client."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='stud@example.com', email='stud@example.com', password='pw12345!aA',
        )
        self.event = Event.objects.create(
            name='Tiered Event', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=100,
            registration_fee=200000,
            undergraduate_enabled=True, registration_fee_undergraduate=50000,
            graduate_enabled=True, registration_fee_graduate=100000,
        )
        # Registration sends a confirmation mail, so the template must exist.
        self.event.email_template_registration = EmailTemplate.objects.create(
            subject='Registered', body='Thanks',
        )
        self.event.save()
        self.client.force_login(self.user)

    def test_fee_per_tier(self):
        self.assertEqual(self.event.fee_for('undergraduate'), 50000)
        self.assertEqual(self.event.fee_for('graduate'), 100000)
        self.assertEqual(self.event.fee_for('pi_non_academic'), 200000)

    def test_unknown_tier_falls_back_to_standard_not_free(self):
        self.assertEqual(self.event.fee_for('nonsense'), 200000)

    def test_disabled_tier_is_charged_the_standard_fee(self):
        self.event.undergraduate_enabled = False
        self.event.save()
        self.assertEqual(self.event.fee_for('undergraduate'), 200000)

    def test_event_without_tiers_charges_everyone_the_same(self):
        plain = Event.objects.create(
            name='Flat', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Seoul', capacity=10, registration_fee=30000,
        )
        self.assertFalse(plain.has_tiered_fees)
        for tier in ('undergraduate', 'graduate', 'pi_non_academic'):
            self.assertEqual(plain.fee_for(tier), 30000)

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

    def test_registering_records_the_reported_tier(self):
        self.register(student_status='graduate')
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.student_status, 'graduate')
        self.assertEqual(self.event.fee_for(attendee.student_status), 100000)

    def test_tier_the_event_does_not_offer_is_refused(self):
        self.event.undergraduate_enabled = False
        self.event.save()
        # Claiming a tier that is switched off must not buy the lower price.
        self.register(student_status='undergraduate')
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.student_status, 'pi_non_academic')
        self.assertEqual(self.event.fee_for(attendee.student_status), 200000)

    @patch('main.apis.requests.post')
    def test_payment_below_the_tier_price_is_rejected(self, mock_post):
        self.register(student_status='graduate')
        response = self.client.post(
            '/api/payment/confirm',
            data={'paymentKey': 'k', 'orderId': 'o', 'amount': 50000, 'eventId': self.event.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'amount_mismatch')
        mock_post.assert_not_called()

    @patch('main.apis.requests.post')
    def test_payment_matching_the_tier_price_is_accepted(self, mock_post):
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {'method': '카드'}
        self.register(student_status='graduate')
        response = self.client.post(
            '/api/payment/confirm',
            data={'paymentKey': 'k', 'orderId': 'o', 'amount': 100000, 'eventId': self.event.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payment = PaymentHistory.objects.get(event=self.event)
        self.assertEqual(payment.amount, 100000)


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
        response = self.client.get(f'/api/event/{self.event.id}/abstracts')
        self.assertEqual(response.status_code, 200)
        titles = [a['title'] for a in response.json()]
        self.assertIn('Competing', titles)
        self.assertNotIn('Invited', titles)

    def test_admin_still_sees_every_abstract(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(f'/api/event/{self.event.id}/abstracts')
        titles = [a['title'] for a in response.json()]
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
