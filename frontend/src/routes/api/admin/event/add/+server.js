import { post } from '$lib/fetch';
import { apiKeyHeaders, relay } from '$lib/server/apiProxy';

/** @type {import('./$types').RequestHandler} */
export async function POST({ request, cookies }) {
	const body = await request.json();
	return relay(await post('api/admin/event/add', body, cookies, apiKeyHeaders(request)));
}
