import { error, redirect } from '@sveltejs/kit';
import { post } from '$lib/fetch';
import { sanitizeRedirectUrl } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params }) {
    const data = await parent();
    data.key = params.slug;
    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
    verify: async ({ request, cookies }) => {
        let formdata = await request.formData()
        const response = await post('_allauth/browser/v1/auth/email/verify', formdata, cookies);
        // 200: Email verified, 400: Input error, 401: Success but login required, 409: Already verified
        if (response.status === 200 || response.status === 401) {
            // Back to wherever the signup started, if this browser remembers -
            // typically an invitation link. Otherwise just the login page.
            const next = sanitizeRedirectUrl(cookies.get('post_verify_next'));
            cookies.delete('post_verify_next', { path: '/' });
            throw redirect(303, next !== '/' ? `/login?next=${encodeURIComponent(next)}` : '/login');
        } else if (response.status === 400) {
            throw error(response.status, 'Oops! It seems to be an invalid or expired verification link.');
        } else if (response.status === 409) {
            throw error(response.status, 'Oops! This email address was already verified.');
        } else {
            throw error(response.status, 'Server error. If this persists, please contact the administrator.');
        }
    }
};