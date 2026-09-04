import { error } from '@sveltejs/kit';
import { fetchPublicEvent, renderEvent } from '$lib/server/llms.js';

export const prerender = false;

/**
 * The plain-text form of one event page, linked from that page's head.
 *
 * Fetched without cookies, so an unpublished or archived event is not found
 * here regardless of who is asking.
 */
export async function GET({ params, url }) {
    const event = await fetchPublicEvent(params.slug);
    if (!event) throw error(404, 'Not found');

    return new Response(renderEvent(event, url.origin), {
        headers: {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'public, max-age=300',
        },
    });
}
