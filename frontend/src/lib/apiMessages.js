import * as m from '$lib/paraglide/messages.js';

/**
 * The message to show for a failed request, in the visitor's language.
 *
 * The backend and the server actions answer with a `code` (and an English
 * `message` meant for logs); each code has an `api_<code>` translation. A code
 * with none falls back to `fallback` - a message function or a string already
 * translated - and then to the generic error, never to the English text.
 */
export function apiMessage(err, fallback) {
    const code = typeof err?.code === 'string' ? err.code.toLowerCase() : '';
    const translated = code && m[`api_${code}`];
    if (typeof translated === 'function') return translated();
    if (typeof fallback === 'function') return fallback();
    return fallback || m.common_error();
}

/** True when a translation exists for this code. */
export function hasApiMessage(code) {
    return typeof code === 'string' && typeof m[`api_${code.toLowerCase()}`] === 'function';
}
