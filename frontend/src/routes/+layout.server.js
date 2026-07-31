import { get } from '$lib/fetch';
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

    const response_csrftoken = await get('api/csrftoken');
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