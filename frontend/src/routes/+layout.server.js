import { get } from '$lib/fetch';
import { renderEvent } from '$lib/server/llms.js';
import { error, redirect } from '@sveltejs/kit';
import { isProfileComplete } from '$lib/utils.js';

const ADMIN_PAGE_NAME = process.env.ADMIN_PAGE_NAME || 'admin';

// Pages that don't require a complete profile
const PROFILE_EXEMPT_PATHS = [
    '/complete-profile',
    '/login',
    '/logout',
    '/registration',
    '/verify-email',
    '/forgot-password',
];

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, url }) {
    let rtn = {};

    // Forward the cookies: without them Django has no CSRF secret to recognise
    // and mints a fresh one on every request, which this then writes over the
    // browser's. Any second request - another tab, a link prefetch, the next
    // navigation - would therefore invalidate the token already rendered into
    // the page the user is looking at, and their next POST would 403. Sent the
    // existing cookie, Django reuses that secret, so every token derived from
    // it stays valid no matter how many loads happen in between.
    const response_csrftoken = await get('api/csrftoken', cookies);
    if (!response_csrftoken.ok || response_csrftoken.status !== 200) {
        throw error(500, "Internal Server Error");
    }
    cookies.set('csrftoken', response_csrftoken.data.csrftoken, {
        path: '/',
        httpOnly: true,
        sameSite: 'lax',
        secure: process.env.NODE_ENV === 'production',
    });

    if (cookies.get('sessionid')) {
        const response_me = await get('api/me', cookies);
        if (response_me.ok && response_me.status === 200) {
            let user = response_me.data;
            rtn.user = user;

            // Only expose admin page name to staff users
            if (user.is_staff) {
                rtn.admin_page_name = ADMIN_PAGE_NAME;
            }

            // Check if profile is complete (skip for exempt paths)
            const currentPath = url.pathname;
            const isExempt = PROFILE_EXEMPT_PATHS.some(path => currentPath.startsWith(path));
            if (!isExempt && !isProfileComplete(user)) {
                const next = currentPath + url.search;
                throw redirect(303, `/complete-profile?next=${encodeURIComponent(next)}`);
            }
        } else {
            cookies.delete('sessionid', {
                path: '/',
                httpOnly: true,
                sameSite: 'lax',
                secure: process.env.NODE_ENV === 'production'
            });
        }
    }

    rtn.csrf_token = response_csrftoken.data.csrftoken;

    // On an event page, load just enough about the event to describe it in the
    // document itself. Nothing below the root layout renders on the server - it
    // is all behind the loading gate - so without this a fetcher sees only the
    // site-wide title and learns nothing about the event it asked for.
    // Fetched without cookies: an unpublished event is simply not found.
    const eventPath = url.pathname.match(/^\/event\/(\d+)(?:\/|$)/);
    if (eventPath) {
        const response = await get(`api/event/${eventPath[1]}`);
        if (response.ok && response.status === 200) {
            const event = response.data;
            rtn.event_preview = {
                id: event.id,
                name: event.name,
                start_date: event.start_date,
                end_date: event.end_date,
                venue: event.venue,
                registration_deadline: event.registration_deadline,
            };
            // The full event as text, embedded in the page below so a single
            // fetch of this URL is readable without JavaScript and without a
            // second request.
            rtn.event_text = renderEvent(event, url.origin);
        }
    }

    // Load site settings (public endpoint)
    const siteSettingsResponse = await get('api/site-settings');
    if (siteSettingsResponse.ok && siteSettingsResponse.status === 200) {
        rtn.site_settings = siteSettingsResponse.data;
    } else {
        rtn.site_settings = {
            site_name: 'IEUM',
            site_description: '',
            site_keywords: ''
        };
    }

    // Load business settings (public endpoint). Card issuers require the
    // business details to be shown as text in the site footer, so these are
    // needed on every page.
    const businessSettingsResponse = await get('api/business-settings');
    rtn.business_settings = (businessSettingsResponse.ok && businessSettingsResponse.status === 200)
        ? businessSettingsResponse.data
        : null;

    return rtn;
}