import { get } from '$lib/fetch';
import { redirect, error } from '@sveltejs/kit';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    const data = await parent();

    const response = await get(`api/payment/${params.id}/card-receipt`, cookies);
    if (response.ok && response.data?.receipt_url) {
        // Redirect to Toss receipt page
        throw redirect(302, response.data.receipt_url);
    }

    // If no receipt URL, show error
    throw error(404, { code: response.data?.code || 'no_receipt' });
}
