import { get, post } from '$lib/fetch';
import { error, redirect } from '@sveltejs/kit';
import { sanitizeRedirectUrl, isProfileComplete } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, request, cookies }) {
    const data = await parent();
    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));
    data.next = next;

    // If profile is already complete, redirect to next
    if (isProfileComplete(data.user)) {
        return redirect(303, next);
    }

    // Resolve user's current institution by ID
    if (data.user.institute) {
        const institutionResponse = await get(`api/institutions/${data.user.institute}`, cookies);
        if (institutionResponse.ok) {
            data.user.institution_resolved = institutionResponse.data;
        }
    }

    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
    update: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const next = sanitizeRedirectUrl(formdata.get('next'));

        // Convert FormData to JSON object
        const data = {};
        for (const [key, value] of formdata.entries()) {
            if (key !== 'next') {
                data[key] = value;
            }
        }

        // Ensure username matches email (social signups may have wrong username)
        if (data.email) {
            data.username = data.email;
        }

        const response = await post('api/me', data, cookies);

        if (!response.ok || response.status !== 200) {
            throw error(response.status, { code: 'server_error' });
        }

        // Redirect to next after successful update
        throw redirect(303, next);
    },
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
    }
};
