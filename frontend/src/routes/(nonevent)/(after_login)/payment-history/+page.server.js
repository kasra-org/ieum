import { get, post } from '$lib/fetch';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, cookies }) {
    const data = await parent();

    const response = await get('api/me/payment-history', cookies);
    if (response.ok) {
        data.payments = response.data;
    } else {
        data.payments = [];
    }

    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
    changeRequest: async ({ cookies, request }) => {
        const formData = await request.formData();
        const message = formData.get('message');
        const eventId = formData.get('eventId');

        if (!eventId) {
            return { success: false, error: 'Event ID is required' };
        }

        const response = await post(`api/event/${eventId}/change-request`, { message }, cookies);

        if (!response.ok) {
            return { success: false, code: response.data?.code, error: response.data?.message || 'An error occurred' };
        }

        return { success: true };
    }
};
