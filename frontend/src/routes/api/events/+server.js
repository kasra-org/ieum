import { get } from '$lib/fetch';
import { json } from '@sveltejs/kit';

/** @type {import('./$types').RequestHandler} */
export async function GET({ url, cookies }) {
    const offset = url.searchParams.get('offset') || '0';
    const limit = url.searchParams.get('limit') || '20';
    const year = url.searchParams.get('year');
    const search = url.searchParams.get('search');
    const showOnlyOpen = url.searchParams.get('showOnlyOpen');

    const queryParams = new URLSearchParams({ offset, limit });
    if (year && year !== 'all') queryParams.append('year', year);
    if (search) queryParams.append('search', search);
    if (showOnlyOpen === 'true') queryParams.append('showOnlyOpen', 'true');

    const response = await get(`api/events?${queryParams.toString()}`, cookies);

    if (response.ok && response.status === 200) {
        return json(response.data);
    }

    return json({ events: [], total: 0, offset: 0, limit: 20 }, { status: response.status || 500 });
}
