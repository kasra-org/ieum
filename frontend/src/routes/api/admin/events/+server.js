import { relayList } from '$lib/server/apiProxy';

/** Relays api/admin/events for the admin page's paginated table (see relayList). */
/** @type {import('./$types').RequestHandler} */
export function GET({ params, url, cookies }) {
	return relayList({ path: `api/admin/events`, url, cookies });
}
