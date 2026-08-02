import { redirect } from '@sveltejs/kit';
import { todayInTimeZone } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params }) {
    const data = await parent();
    const event = data.event;

    const today = todayInTimeZone(data.business_settings?.timezone);
    if (today < event.start_date || today > event.end_date) {
        throw redirect(303, `/event/${params.slug}`);
    }

    return {
        onsiteid: params.onsiteid
    };
}
