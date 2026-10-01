import { get, post } from '$lib/fetch';
import { redirect } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    let rtn = await parent();

    // If user is not registered, redirect to event detail page
    if (!rtn.registered) {
        throw redirect(303, `/event/${params.slug}`);
    }

    // Fetch current user's registration
    const response_attendee = await get(`api/event/${params.slug}/registration`, cookies);
    if (response_attendee.ok && response_attendee.status === 200) {
        rtn.attendee = response_attendee.data;
    }

    // Fetch abstract if user has submitted one (only for internal abstract management)
    if (rtn.event.accepts_abstract && rtn.event.abstract_submission_type !== 'external') {
        try {
            const response_abstract = await get(`api/event/${params.slug}/abstract`, cookies);
            if (response_abstract.ok && response_abstract.status === 200) {
                rtn.my_abstract = response_abstract.data;
            }
        } catch (e) {
            // Abstract might not exist, which is fine
            rtn.my_abstract = null;
        }
    }

    // Fetch payment info for the registration
    try {
        const response_payment = await get(`api/event/${params.slug}/registration/payment`, cookies);
        if (response_payment.ok && response_payment.status === 200) {
            rtn.payment = response_payment.data;
        }
    } catch (e) {
        // Payment might not exist
        rtn.payment = null;
    }

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    changeRequest: async ({ params, cookies, request }) => {
        const formData = await request.formData();
        const message = formData.get('message');

        const response = await post(`api/event/${params.slug}/change-request`, { message }, cookies);

        if (!response.ok) {
            return { success: false, code: response.data?.code, error: response.data?.message || 'An error occurred' };
        }

        return { success: true };
    }
};
