from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from main import nicepay
from main.utils import render_email_template
from main.models import Abstract, AbstractVote, Attendee, Institution, EmailTemplate, Event, NicePayTransaction, OnSiteAttendee, PaymentHistory, PaymentSettings, RegistrationCategory
from main.models import apply_speaker_exemption, settle_speaker_payment

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
        row = response.json()[0]
        self.assertEqual(row['category'], self.category.id)
        self.assertEqual(row['category_name_ko'], '학생')
        self.assertEqual(row['registration_fee'], 60000)


class SpeakerPaymentExemptionTests(TestCase):
    """A speaker on the list is settled at 0 KRW rather than left owing."""

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

    def test_adding_a_speaker_settles_an_existing_registration(self):
        attendee = self.make_attendee()
        self.assertEqual(attendee.payment_status, 'pending')

        self.add_speaker()
        attendee.refresh_from_db()
        payment = attendee.payments.get()
        self.assertEqual((payment.amount, payment.status), (0, 'completed'))
        self.assertEqual(attendee.payment_status, 'paid')

    def test_a_speaker_who_is_not_exempt_still_owes(self):
        attendee = self.make_attendee()
        self.add_speaker(is_payment_exempt=False)
        self.assertEqual(attendee.payment_status, 'pending')
        self.assertFalse(attendee.payments.exists())

    def test_registering_after_being_listed_is_settled(self):
        self.add_speaker()
        response = self.client.post(
            f'/api/event/{self.event.id}/register',
            data={'first_name': 'Spea', 'last_name': 'Ker', 'nationality': 1,
                  'institute': Institution.objects.create(name_en='PNU').id,
                  'job_title': 'Prof', 'category': self.category.id},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        attendee = Attendee.objects.get(event=self.event, user=self.user)
        self.assertEqual(attendee.payment_status, 'paid')
        self.assertEqual(attendee.payments.get().amount, 0)

    def test_matching_is_case_insensitive(self):
        attendee = self.make_attendee()
        self.add_speaker(email='SPK@Example.COM')
        self.assertEqual(attendee.payment_status, 'paid')

    def test_unticking_the_exemption_takes_the_waiver_back(self):
        attendee = self.make_attendee()
        self.add_speaker()
        self.assertEqual(attendee.payment_status, 'paid')

        speaker = self.event.speakers.get()
        self.client.post(
            f'/api/event/{self.event.id}/speaker/{speaker.id}/update',
            data={'name': speaker.name, 'email': speaker.email, 'affiliation': 'PNU',
                  'is_domestic': True, 'type': 'invited', 'is_payment_exempt': False},
            content_type='application/json',
        )
        self.assertEqual(attendee.payment_status, 'pending')
        self.assertFalse(attendee.payments.exists())

    def test_removing_the_speaker_takes_the_waiver_back(self):
        attendee = self.make_attendee()
        self.add_speaker()
        speaker = self.event.speakers.get()
        self.client.post(f'/api/event/{self.event.id}/speaker/{speaker.id}/delete',
                         data={}, content_type='application/json')
        self.assertEqual(attendee.payment_status, 'pending')

    def test_a_real_payment_is_never_replaced_or_removed(self):
        attendee = self.make_attendee()
        paid = PaymentHistory.objects.create(
            attendee=attendee, event=self.event, amount=200000, status='completed',
            provider='toss',
        )
        self.add_speaker()
        # No zero-amount record on top, and the real one survives a removal.
        self.assertEqual([p.id for p in attendee.payments.all()], [paid.id])
        speaker = self.event.speakers.get()
        self.client.post(f'/api/event/{self.event.id}/speaker/{speaker.id}/delete',
                         data={}, content_type='application/json')
        paid.refresh_from_db()
        self.assertEqual(attendee.payment_status, 'paid')

    def test_settling_twice_leaves_one_record(self):
        attendee = self.make_attendee()
        self.add_speaker()
        speaker = self.event.speakers.get()
        self.client.post(
            f'/api/event/{self.event.id}/speaker/{speaker.id}/update',
            data={'name': speaker.name, 'email': speaker.email, 'affiliation': 'KAIST',
                  'is_domestic': True, 'type': 'keynote', 'is_payment_exempt': True},
            content_type='application/json',
        )
        self.assertEqual(attendee.payments.count(), 1)

    def test_a_speaker_at_another_event_is_not_settled(self):
        attendee = self.make_attendee()
        other = Event.objects.create(
            name='Other', start_date=date(2026, 1, 1), end_date=date(2026, 1, 2),
            venue='Busan', capacity=10,
        )
        other.speakers.create(name='Spea Ker', email='spk@example.com',
                              affiliation='PNU', is_domestic=True, type='invited')
        apply_speaker_exemption(other.speakers.get())
        self.assertEqual(attendee.payment_status, 'pending')


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

    def test_a_waived_payment_reports_zero_so_the_ui_can_disable_printing(self):
        payment = settle_speaker_payment(self.event, self.attendee)
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
        row = response.json()[0]
        self.assertEqual(row['provider'], 'nicepay')
        # Both gateways say '카드', so the type alone cannot name the gateway.
        self.assertEqual(row['payment_type'], '카드')

    @patch('main.apis.requests.get')
    def test_a_nicepay_card_slip_never_asks_toss(self, mock_get):
        """Both providers label a card payment '카드'; only Toss can answer."""
        payment = self.make_payment('nicepay', 'MOID-3')
        response = self.client.get(f'/api/payment/{payment.toss_order_id}/card-receipt')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'not_supported')
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
