import { post } from '$lib/fetch';
import { error } from '@sveltejs/kit';

export async function load({ parent, params }) {
    let rtn = await parent();

    rtn.key = params.slug;

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    password: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const response = await post('_allauth/browser/v1/auth/password/reset', formdata, cookies);

        if (!response.ok || response.status !== 200) {
            if (response.status === 400) {
                throw error(response.status, { code: response.data.errors[0].code, message: response.data.errors[0].message });
            } else if (response.status === 401) {
                // Success, but we got 401 because the user is not logged in
                return;
            }
            throw error(response.status, { code: 'server_error' });
        }
    }
};