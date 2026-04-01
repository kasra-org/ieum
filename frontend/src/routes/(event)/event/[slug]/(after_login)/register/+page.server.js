import { get, post } from '$lib/fetch';
import { error, redirect } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    let rtn = await parent();
    if (rtn.user) {
        // Check if already registered
        if (rtn.registered) {
            // If registered but payment is pending, allow access for payment
            const hasPendingPayment = rtn.event.registration_fee > 0 && rtn.payment_status === 'pending';
            if (hasPendingPayment) {
                // Set flag to start at payment step
                rtn.startAtPaymentStep = true;
                rtn.questions = [];
                return rtn;
            }
            // If fully registered, redirect to event page
            return redirect(303, `/event/${params.slug}`);
        }
        const response_questions = await get(`api/event/${params.slug}/questions`, cookies); // list of custom questions
        if (response_questions.ok && response_questions.status === 200) {
            rtn.questions = response_questions.data;
        } else {
            error(500, "Internal Server Error");
        }

        // Resolve user's current institution by ID
        if (rtn.user.institute) {
            const institutionResponse = await get(`api/institutions/${rtn.user.institute}`, cookies);
            if (institutionResponse.ok) {
                rtn.user.institution_resolved = institutionResponse.data;
            }
        }
    } else {
        return redirect(303, `/login?next=${encodeURIComponent(`/event/${params.slug}/register`)}`);
    }

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    search_institutions: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const search = formdata.get('search') || '';

        const response = await get(`api/institutions?search=${encodeURIComponent(search)}`, cookies);
        if (response.ok) {
            return { success: true, institutions: response.data };
        } else {
            return { success: false, institutions: [] };
        }
    },
    create_institution: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            name_en: formdata.get('name_en'),
            name_ko: formdata.get('name_ko') || ''
        };
        const response = await post('api/institutions', data, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, institution: response.data };
        } else {
            throw error(response.status, response.data);
        }
    },
    verify_invitation_code: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/verify_invitation_code`, {
            invitation_code: formdata.get('invitation_code') || '',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    register: async ({ cookies, params, request }) => {
        let formdata = await request.formData()
        const response = await post(`api/event/${params.slug}/register`, formdata, cookies);

        if (!response.ok || response.status !== 200) {
            if (response.status === 400) {
                throw error(response.status, { error: true, message: response.data.message });
            }
            throw error(response.status, { error: true, message: 'Failed due to server error. It this persists, please contact the admininistrator.' });
        }
        return;
    },
    paypal_create_order: async ({ cookies, params, request }) => {
        const formdata = await request.formData();
        const amount = parseInt(formdata.get('amount'), 10);
        const eventId = parseInt(params.slug, 10);

        const response = await post('api/payment/paypal/create-order', {
            eventId,
            amount,
        }, cookies);

        if (!response.ok) {
            return { success: false, error: response.data?.message || 'Failed to create PayPal order' };
        }

        return { success: true, orderId: response.data.orderId };
    },
    paypal_capture_order: async ({ cookies, params, request }) => {
        const formdata = await request.formData();
        const orderId = formdata.get('orderId');
        const eventId = parseInt(params.slug, 10);

        const response = await post('api/payment/paypal/capture-order', {
            orderId,
            eventId,
        }, cookies);

        if (!response.ok) {
            return { success: false, error: response.data?.message || 'Failed to capture PayPal payment' };
        }

        return { success: true, data: response.data };
    },
};