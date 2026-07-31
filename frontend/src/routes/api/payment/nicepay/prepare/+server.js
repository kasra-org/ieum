import { post } from '$lib/fetch';
import { json } from '@sveltejs/kit';

/**
 * Proxy the NicePay prepare call to the backend, forwarding the session cookie.
 * @type {import('./$types').RequestHandler}
 */
export async function POST({ request, cookies }) {
    const body = await request.json().catch(() => ({}));

    const response = await post('api/payment/nicepay/prepare', {
        eventId: body.eventId,
        payMethod: body.payMethod || 'CARD',
    }, cookies);

    if (!response.ok) {
        return json(
            { message: response.data?.message || 'Could not start the payment' },
            { status: response.status || 500 },
        );
    }

    return json(response.data);
}
