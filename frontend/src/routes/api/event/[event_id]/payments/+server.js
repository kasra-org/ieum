import { relayList } from '$lib/server/apiProxy';

/** Relays api/event/{id}/payments for the admin page's paginated table (see relayList). */
/** @type {import('./$types').RequestHandler} */
export function GET({ params, url, cookies }) {
	return relayList({ path: `api/event/${params.event_id}/payments`, url, cookies, eventId: params.event_id });
}
