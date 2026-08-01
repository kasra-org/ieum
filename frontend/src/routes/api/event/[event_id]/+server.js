import { get } from '$lib/fetch';
import { apiKeyHeaders, relay } from '$lib/server/apiProxy';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, request, cookies }) {
	return relay(await get(`api/event/${params.event_id}`, cookies, apiKeyHeaders(request)));
}
