import { get } from '$lib/fetch';
import { redirect } from '@sveltejs/kit';
import { error } from '@sveltejs/kit';
import { post } from '$lib/fetch';
import { sanitizeRedirectUrl } from '$lib/utils.js';

function clean_orcid_cookies(cookies) {
    try {
        cookies.delete('orcid', {
            path: '/',
            httpOnly: true,
            sameSite: 'lax',
            secure: process.env.NODE_ENV === 'production'
        });
    } catch (e) { }
    try {
        cookies.delete('orcid_access_token', {
            path: '/',
            httpOnly: true,
            sameSite: 'lax',
            secure: process.env.NODE_ENV === 'production'
        });
    } catch (e) { }
}

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, cookies, request }) {
    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));

    let data = await parent();

    if (data.user) {
        return redirect(303, next);
    }

    let orcid = cookies.get('orcid');
    let orcid_access_token = cookies.get('orcid_access_token');
    if (orcid && orcid_access_token) {
        data.orcid = orcid;
        data.orcid_access_token = orcid_access_token;
        clean_orcid_cookies(cookies);
    }
    data.next = next;

    // Load privacy policy and terms of service
    const privacyPolicyResponse = await get('api/privacy-policy', cookies);
    if (privacyPolicyResponse.ok && privacyPolicyResponse.status === 200) {
        data.privacyPolicy = privacyPolicyResponse.data;
    } else {
        data.privacyPolicy = { content_en: '', content_ko: '' };
    }

    const termsOfServiceResponse = await get('api/terms-of-service', cookies);
    if (termsOfServiceResponse.ok && termsOfServiceResponse.status === 200) {
        data.termsOfService = termsOfServiceResponse.data;
    } else {
        data.termsOfService = { content_en: '', content_ko: '' };
    }

    return data;
}

/** @type {import('./$types').Actions} */
export const actions = {
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
    register: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const next = sanitizeRedirectUrl(formdata.get('next'));
        formdata.delete('next');

        // Arrived through an invitation link: the signup registers them for
        // that event as well (main.forms.CustomSignupForm on the backend).
        const invited = next.match(/^\/invite\/([A-Za-z0-9_-]+)$/);
        if (invited) {
            formdata.set('invitation_token', invited[1]);
        }

        // The verification email's link carries no `next`; remember it here so
        // that, once verified, they log in and land back where they started.
        if (next !== '/') {
            cookies.set('post_verify_next', next, {
                path: '/', httpOnly: true, sameSite: 'lax', maxAge: 60 * 60 * 24,
                secure: process.env.NODE_ENV === 'production',
            });
        }

        const response = await post('_allauth/browser/v1/auth/signup', formdata, cookies);

        if (!response.ok) {
            if (response.status === 400) {
                let rtn = {};
                for (const error of response.data.errors) {
                    if (error.code === 'username_taken') {
                        rtn.email = 'This email address is already taken.';
                    } else {
                        rtn[`${error.param}`] = error.message;
                    }
                }
                throw error(response.status, rtn);
            } else if (response.status === 401) {
                // email verification required
                throw error(response.status, {redirect: true});
            }
            throw error(response.status, { message: 'Failed due to server error. It this persists, please contact the admininistrator.' });
        }
        throw error(response.status, { message: 'Server error. It this persists, please contact the admininistrator.' }); // You can't arrive here!
    }
};