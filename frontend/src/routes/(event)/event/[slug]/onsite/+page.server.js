import { get, post } from '$lib/fetch';
import { error, fail, redirect } from '@sveltejs/kit';
import { todayInTimeZone } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, url }) {
    const data = await parent();
    const event = data.event;

    const today = todayInTimeZone(data.business_settings?.timezone);
    if (today < event.start_date || today > event.end_date) {
        throw redirect(303, `/event/${params.slug}`);
    }

    // Validate onsite code from URL query param
    const code = url.searchParams.get('code') || '';
    const response_code = await get(`api/event/${params.slug}/onsite/verify?code=${encodeURIComponent(code)}`);
    data.onsite_code_valid = response_code.ok && response_code.status === 200;
    data.onsite_code = code;

    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
    onsiteregister: async ({ cookies, params, request }) => {
        let formdata = await request.formData()
        const response = await post(`api/event/${params.slug}/onsite`, formdata, cookies);

        if (!response.ok || response.status !== 200) {
            if (response.status === 400) {
                throw error(response.status, { error: true, message: response.data.message });
            }
            throw error(response.status, { error: true, message: 'Failed due to server error. It this persists, please contact the admininistrator.' });
        }
        let rtn = await response.data;
        return redirect(303, `/event/${params.slug}/onsite/${rtn.onsiteattendee_nametag_id}`);
    },
};