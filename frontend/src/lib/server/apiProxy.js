import { json, text } from '@sveltejs/kit';

/**
 * Helpers for the routes that expose Django endpoints to machine clients.
 *
 * Django is deliberately not reachable from outside — the reverse proxy sends
 * only a handful of paths to it, and everything under /api/ belongs to
 * SvelteKit. So anything an external client needs (the KASRA secretariat MCP
 * creating and updating events) has to be relayed through here rather than by
 * opening a second door to the backend.
 */

/**
 * Pass the caller's API key through to Django, which is what actually
 * authenticates it. Cookies are forwarded separately by $lib/fetch, so a
 * browser session keeps working on the same route.
 */
export function apiKeyHeaders(request) {
	const key = request.headers.get('x-api-key');
	return key ? { 'X-API-Key': key } : undefined;
}

/** Return Django's response as-is, preserving its status code. */
export function relay(response) {
	const status = response.status || (response.ok ? 200 : 502);
	if (response.data === undefined || response.data === null) {
		return json({}, { status });
	}
	if (typeof response.data === 'string') {
		return text(response.data, { status });
	}
	return json(response.data, { status });
}
