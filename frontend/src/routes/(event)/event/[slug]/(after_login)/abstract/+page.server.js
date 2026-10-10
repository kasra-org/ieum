import { get, post } from '$lib/fetch';
import { error, fail, redirect } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    let rtn = await parent();

    if (rtn.user) {
        rtn.abstract_submitted = false;
        // The preview below the title shows the converted file, so ask for it.
        const response_abstract = await get(`api/event/${params.slug}/abstract?include_body=true`, cookies);
        if (response_abstract.ok && response_abstract.status === 200) {
            rtn.abstract_submitted = true;
            rtn.abstract = response_abstract.data;
        }
    } else {
        return redirect(303, `/login?next=${encodeURIComponent(`/event/${params.slug}/abstract`)}`);
    }

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    abstract: async ({ cookies, params, request }) => {
        let formdata = await request.formData()
        const response = await post(`api/event/${params.slug}/abstract`, formdata, cookies);
        if (!response.ok || response.status !== 200) {
            if (response.status === 400) {
                throw error(response.status, { error: true, code: response.data?.code, message: response.data?.message });
            }
            throw error(response.status, { error: true, code: 'submission_failed' });
        }
        return;
    },
};