import { post } from '$lib/fetch';
import { apiKeyHeaders, relay } from '$lib/server/apiProxy';

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, request, cookies }) {
	const body = await request.json();
	return relay(await post(`api/event/${params.event_id}/update`, body, cookies, apiKeyHeaders(request)));
}
