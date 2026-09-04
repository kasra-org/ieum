/**
 * Served from a route rather than static/, so the sitemap and llms.txt links
 * carry the host the request actually arrived on.
 */
export const prerender = false;

/** @type {import('./$types').RequestHandler} */
export function GET({ url }) {
    const body = [
        'User-agent: *',
        'Allow: /',
        // Nothing useful to a crawler, and the admin path is configurable.
        'Disallow: /api/',
        'Disallow: /logout',
        '',
        `# Plain-text rendering of the public events, for agents that do not run JavaScript.`,
        `# ${url.origin}/llms.txt`,
        `# ${url.origin}/llms-full.txt`,
        '',
    ].join('\n');
    return new Response(body, {
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'public, max-age=3600' },
    });
}
