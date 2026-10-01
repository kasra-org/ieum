import { post } from '$lib/fetch';
import { fail, redirect } from '@sveltejs/kit';
import { sanitizeRedirectUrl } from '$lib/utils.js';
import { TURNSTILE_FIELD, turnstileSiteKey, verifyTurnstile } from '$lib/server/turnstile.js';
import { invitationForNext } from '$lib/server/invitation.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, request }) {
    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));

    let rtn = await parent();
    if (rtn.user) {
        return redirect(303, next);
    }

    rtn.sociallogin_error = url.searchParams.get('error_process') || '';
    rtn.next = next;
    rtn.turnstile_site_key = turnstileSiteKey();
    rtn.invitation = await invitationForNext(next);

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
	login: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const next = sanitizeRedirectUrl(formdata.get('next'));
        const email = formdata.get('email');

        // Email/password login only; social login goes to the provider and
        // never reaches this action.
        const turnstileToken = formdata.get(TURNSTILE_FIELD);
        formdata.delete(TURNSTILE_FIELD);
        if (!(await verifyTurnstile(turnstileToken))) {
            return fail(400, { error: true, code: 'turnstile_failed' });
        }

        const response = await post('_allauth/browser/v1/auth/login', formdata, cookies);

		if (!response.ok || response.status !== 200) {
            if (response.status === 401) {
                // Try to generate verification key - backend will return empty key if email is verified
                const keyResponse = await post('api/generate-verification-key', { email }, cookies);
                const verificationKey = keyResponse.data?.key || '';

                // Only show verification message if we got a valid key (email is unverified)
                if (verificationKey) {
                    return fail(response.status, {
                        error: true,
                        code: 'email_not_verified',
                        email: email,
                        verificationKey: verificationKey,
                        needsVerification: true
                    });
                }
            }
            return fail(response.status, { error: true, code: 'login_failed' });
        }
        cookies.set('sessionid', response.sessionid, {
            path: '/',
            httpOnly: true,
            sameSite: 'lax',
            secure: process.env.NODE_ENV === 'production',
        });

        // Redirect to the next parameter from form data
        throw redirect(303, next);
	},
	resendVerification: async ({ cookies, request }) => {
        let formdata = await request.formData()
        const email = formdata.get('email');
        const verificationKey = formdata.get('verificationKey');

        const response = await post('api/resend-verification', { email, verification_key: verificationKey }, cookies);

        if (!response.ok || response.status !== 200) {
            return fail(response.status, {
                error: true,
                code: 'resend_failed',
                email: email,
                needsVerification: true
            });
        }

        return {
            success: true,
            email: email
        };
	},
};
