import { get } from '$lib/fetch';

/**
 * A walk-in's receipt, by the link emailed to them when their desk payment
 * was recorded. Outside (after_login): they have no account, and the secret
 * in the link is what opens it.
 * @type {import('./$types').PageServerLoad}
 */
export async function load({ params, cookies }) {
    const response = await get(`api/receipt/${encodeURIComponent(params.token)}`, cookies);
    return { payment: response.ok ? response.data : null };
}
