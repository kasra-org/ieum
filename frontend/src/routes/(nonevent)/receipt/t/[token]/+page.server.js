import { get, post } from '$lib/fetch';
import { fail } from '@sveltejs/kit';

/**
 * A walk-in's receipt, by the link emailed to them when their desk payment
 * was recorded. Outside (after_login): they have no account, and the secret
 * in the link is what opens it. An admin of the event opening it from the
 * admin page also gets `payment_id` and `send_to`, to send it from here.
 * @type {import('./$types').PageServerLoad}
 */
export async function load({ params, cookies }) {
    const response = await get(`api/receipt/${encodeURIComponent(params.token)}`, cookies);
    return { payment: response.ok ? response.data : null };
}

/** @type {import('./$types').Actions} */
export const actions = {
    // The API checks the sender is an admin of the event.
    send: async ({ cookies, request }) => {
        const formdata = await request.formData();
        const eventId = parseInt(formdata.get('event_id'));
        const paymentId = parseInt(formdata.get('payment_id'));
        if (isNaN(eventId) || isNaN(paymentId)) return fail(400, { code: 'payment_not_found' });
        const response = await post(`api/event/${eventId}/payment/${paymentId}/receipt/send`, {}, cookies);
        if (response.ok && response.status === 200) return response.data;
        return fail(response.status, response.data);
    },
};
