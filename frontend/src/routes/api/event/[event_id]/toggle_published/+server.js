import { post } from '$lib/fetch';
import { apiKeyHeaders, relay } from '$lib/server/apiProxy';

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies }) {
	const body = await request.json().catch(() => ({}));
	return relay(await post(`api/event/${params.event_id}/toggle_published`, body, cookies, apiKeyHeaders(request)));
}
