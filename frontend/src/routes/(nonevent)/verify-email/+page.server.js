import { sanitizeRedirectUrl } from '$lib/utils.js';

/** @type {import('./$types').PageServerLoad} */
export async function load({ request }) {
    const url = new URL(request.url);
    const next = sanitizeRedirectUrl(url.searchParams.get('next'));
    return { next };
}
