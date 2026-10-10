import { get } from '$lib/fetch';
import { error } from '@sveltejs/kit';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ parent, params, cookies }) {
    let rtn = await parent();

    const response_event = await get(`api/event/${params.slug}`, cookies);
    if (response_event.ok && response_event.status === 200) {
        let event = response_event.data;
        rtn.event = event;
    } else {
        throw error(response_event.status);
    }

    if (rtn.user) {
        const response_registered = await get(`api/event/${params.slug}/registered`, cookies); // true if registered, false if not
        // Whether they submitted an abstract comes with it: only the button
        // label needs it, so the abstract itself is not fetched on every page.
        // Only for internal abstract management.
        rtn.abstract_submitted = false;
        if (response_registered.ok && response_registered.status === 200) {
            rtn.registered = response_registered.data.registered;
            rtn.payment_status = response_registered.data.payment_status;
            rtn.abstract_submitted = Boolean(
                rtn.event.accepts_abstract && rtn.event.abstract_submission_type !== 'external'
                && response_registered.data.abstract_submitted);
        }
    }

    return rtn;
}