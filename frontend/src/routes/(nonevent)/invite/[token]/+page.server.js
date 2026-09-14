import { get, post } from '$lib/fetch';
import { error, redirect } from '@sveltejs/kit';

/**
 * The landing page for an invitation link.
 *
 * Signed out: on to the login page, carrying this URL as `next`, so that
 * logging in - or creating an account there - comes straight back here.
 * Signed in: the invitation is accepted on the spot and the page reports the
 * outcome. Accepting is idempotent on the server, so a reload or a second
 * click on the link changes nothing.
 *
 * A signed-in user whose profile is incomplete never reaches this load: the
 * root layout sends them to complete it first, then back here, so the
 * registration copies a filled-in profile.
 *
 * @type {import('./$types').PageServerLoad}
 */
export async function load({ parent, params, cookies, url }) {
    const data = await parent();

    const info = await get(`api/invitation/${params.token}`, cookies);
    if (!info.ok || info.status !== 200) {
        throw error(404, 'This invitation link is not valid.');
    }
    data.invitation = { ...info.data, token: params.token };

    if (!data.user) {
        throw redirect(303, `/login?next=${encodeURIComponent(url.pathname)}`);
    }

    const accepted = await post(`api/invitation/${params.token}/accept`, {}, cookies);
    if (accepted.ok && accepted.status === 200) {
        data.outcome = { ok: true };
    } else {
        data.outcome = {
            ok: false,
            code: accepted.data?.code || 'error',
            message: accepted.data?.message || '',
        };
    }
    return data;
}
