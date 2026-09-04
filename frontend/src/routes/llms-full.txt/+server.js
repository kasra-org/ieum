import { fetchPublicEvents, fetchSiteSettings, renderFull } from '$lib/server/llms.js';

export const prerender = false;

/** @type {import('./$types').RequestHandler} */
export async function GET({ url }) {
    const [settings, events] = await Promise.all([fetchSiteSettings(), fetchPublicEvents()]);
    return new Response(renderFull(settings, events, url.origin), {
        headers: {
            'Content-Type': 'text/plain; charset=utf-8',
            'Cache-Control': 'public, max-age=300',
        },
    });
}
