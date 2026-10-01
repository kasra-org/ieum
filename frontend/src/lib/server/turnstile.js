import { env } from '$env/dynamic/private';

const SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

// The form field Cloudflare's widget fills in.
export const TURNSTILE_FIELD = 'cf-turnstile-response';

/**
 * Turnstile is on when a secret key is configured. Left unset (a development
 * checkout, say), the login form shows no widget and nothing is checked.
 */
export function turnstileSiteKey() {
    return env.TURNSTILE_SECRET_KEY ? (env.TURNSTILE_SITE_KEY || '') : '';
}

/**
 * Check a widget token with Cloudflare. True when Turnstile is off, or when
 * Cloudflare accepts the token; false for a missing, used or forged one, and
 * when Cloudflare cannot be reached - a login is refused rather than let
 * through unchecked.
 */
export async function verifyTurnstile(token) {
    if (!env.TURNSTILE_SECRET_KEY) return true;
    if (!token || typeof token !== 'string') return false;

    try {
        const response = await fetch(SITEVERIFY_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ secret: env.TURNSTILE_SECRET_KEY, response: token }),
            signal: AbortSignal.timeout(10000),
        });
        const result = await response.json();
        if (!result.success) {
            console.warn('Turnstile rejected a token:', result['error-codes']);
        }
        return result.success === true;
    } catch (error) {
        console.error('Turnstile verification failed:', error);
        return false;
    }
}
