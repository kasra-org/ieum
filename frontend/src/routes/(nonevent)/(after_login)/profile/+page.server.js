import { get, post } from '$lib/fetch';
import { error } from '@sveltejs/kit';
import { sanitizeRedirectUrl } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, request, cookies }) {
    const data = await parent();

    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));
    data.next = next;

    // Pass social account linking error from allauth redirect
    const socialError = url.searchParams.get('error');
    if (socialError) {
        data.social_error = socialError;
    }

    // Resolve user's current institution by ID
    if (data.user.institute) {
        const institutionResponse = await get(`api/institutions/${data.user.institute}`, cookies);
        if (institutionResponse.ok) {
            data.user.institution_resolved = institutionResponse.data;
        }
    }

    // Load user's email addresses from allauth
    const emailResponse = await get('_allauth/browser/v1/account/email', cookies);
    if (emailResponse.ok && emailResponse.data?.data) {
        data.emails = emailResponse.data.data;
    } else {
        data.emails = [];
    }

    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
    update: async ({ cookies, request }) => {
        let formdata = await request.formData()

        // Convert FormData to JSON object
        const data = {};
        for (const [key, value] of formdata.entries()) {
            data[key] = value;
        }

        const response = await post('api/me', data, cookies);

        if (!response.ok || response.status !== 200) {
            throw error(response.status, { code: 'server_error' });
        }
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
    },
    reset_password: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const email = formdata.get('email');

        const response = await post('_allauth/browser/v1/auth/password/request', { email }, cookies);

        if (!response.ok || response.status !== 200) {
            throw error(response.status, { code: 'server_error' });
        }

        return { success: true };
    },
    delete_account: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const password = formdata.get('password');

        const response = await post('api/me/delete', { password }, cookies);

        if (!response.ok || response.status !== 200) {
            // Return the error message from the API
            return { success: false, code: response.data?.error?.code || 'server_error' };
        }

        // Clear session cookie after account deletion
        cookies.delete('sessionid', {
            path: '/',
            httpOnly: true,
            sameSite: 'lax',
            secure: process.env.NODE_ENV === 'production'
        });

        return { success: true };
    }
};