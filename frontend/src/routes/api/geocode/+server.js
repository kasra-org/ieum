import { get } from '$lib/fetch';
import { json, error } from '@sveltejs/kit';

/**
 * Server-side proxy for OpenStreetMap's Nominatim geocoder.
 *
 * This exists rather than the venue selector calling Nominatim from the browser
 * because Nominatim returns an empty body to clients that do not identify
 * themselves, and a browser cannot set User-Agent. Running the call here also
 * lets us cache results and hold to the usage policy's rate limit, which a
 * component firing per-user requests cannot.
 *
 * It lives in SvelteKit rather than Django because Caddy only routes a few
 * specific paths to the backend — Django's API is deliberately reachable
 * server-to-server only, and adding a /api/* route would expose all of it.
 */

const NOMINATIM = 'https://nominatim.openstreetmap.org';

// Nominatim asks that the identifier be a real contact for the deployment.
const USER_AGENT =
	process.env.NOMINATIM_USER_AGENT ||
	'ieum-conference-system (+https://github.com/kasra-org/ieum)';

const CACHE_TTL_MS = 24 * 60 * 60 * 1000;
const MIN_INTERVAL_MS = 1100; // usage policy: at most ~1 request per second
const MAX_CACHE_ENTRIES = 500;

const cache = new Map();
let chain = Promise.resolve();
let lastCallAt = 0;

function readCache(key) {
	const hit = cache.get(key);
	if (!hit) return null;
	if (Date.now() - hit.at > CACHE_TTL_MS) {
		cache.delete(key);
		return null;
	}
	return hit.value;
}

function writeCache(key, value) {
	if (cache.size >= MAX_CACHE_ENTRIES) cache.delete(cache.keys().next().value);
	cache.set(key, { at: Date.now(), value });
}

// Serialise upstream calls and space them apart, so several admins searching at
// once cannot burst past the one-request-per-second policy.
function schedule(fn) {
	const run = chain.then(async () => {
		const wait = MIN_INTERVAL_MS - (Date.now() - lastCallAt);
		if (wait > 0) await new Promise((r) => setTimeout(r, wait));
		try {
			return await fn();
		} finally {
			lastCallAt = Date.now();
		}
	});
	chain = run.then(
		() => undefined,
		() => undefined
	);
	return run;
}

// Only the fields the venue selector uses, so the client contract stays narrow.
const slim = (r) => ({
	lat: r.lat,
	lon: r.lon,
	osm_type: r.osm_type,
	osm_id: r.osm_id,
	name: r.name,
	display_name: r.display_name
});

async function nominatim(path, params) {
	const qs = new URLSearchParams({ ...params, format: 'jsonv2' }).toString();
	const key = `${path}?${qs}`;

	const hit = readCache(key);
	if (hit) return hit;

	const value = await schedule(async () => {
		const res = await fetch(`${NOMINATIM}/${path}?${qs}`, {
			headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' }
		});
		if (!res.ok) throw new Error(`nominatim ${path} responded ${res.status}`);
		const data = await res.json();
		return Array.isArray(data) ? data.map(slim) : [];
	});

	writeCache(key, value);
	return value;
}

/** @type {import('./$types').RequestHandler} */
export async function GET({ url, cookies }) {
	// Signed-in users only: this must not become an open geocoding proxy.
	if (!cookies.get('sessionid')) throw error(401, 'Unauthorized');
	const me = await get('api/me', cookies);
	if (!me.ok || me.status !== 200) throw error(401, 'Unauthorized');

	const lang = url.searchParams.get('lang') === 'ko' ? 'ko' : 'en';
	const osmIds = url.searchParams.get('osm_ids');
	const q = (url.searchParams.get('q') || '').trim();

	try {
		if (osmIds) {
			// Node/Way/Relation ids only — never forward arbitrary text upstream.
			if (!/^[NWR]\d+(,[NWR]\d+)*$/.test(osmIds)) throw error(400, 'Invalid osm_ids');
			return json({
				results: await nominatim('lookup', { osm_ids: osmIds, 'accept-language': lang })
			});
		}

		if (q) {
			return json({
				results: await nominatim('search', {
					q,
					limit: '5',
					addressdetails: '1',
					'accept-language': lang
				})
			});
		}

		throw error(400, 'Provide either q or osm_ids');
	} catch (e) {
		if (e?.status) throw e; // a SvelteKit error() we raised above
		console.error('Geocode proxy failed:', e);
		return json({ results: [], error: 'geocode_failed' }, { status: 502 });
	}
}
