import { post } from '$lib/fetch';
import { error } from '@sveltejs/kit';
import { sanitizeRedirectUrl } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, request }) {
    let rtn = await parent();

    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));

    rtn.next = next;

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    password: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const response = await post('_allauth/browser/v1/auth/password/request', formdata, cookies);

        if (!response.ok || response.status !== 200) {
            throw error(response.status, { message: 'Server error. It this persists, please contact the admininistrator.' });
        }
    }
};