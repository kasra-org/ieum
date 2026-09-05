import { env } from '$env/dynamic/private';
import { json } from '@sveltejs/kit';

const BASE_URL = env.API_BASE_URL || 'http://backend:8080/';

/**
 * Forward an uploaded backup to the backend's restore endpoint. The backend
 * enforces CSRF and superuser access; this passes the session cookie and the
 * CSRF token (the cookie is httpOnly, so only the server can read it) along
 * with the multipart body.
 */
export async function POST({ request, cookies }) {
    const cookieHeader = cookies.getAll().map((c) => `${c.name}=${c.value}`).join('; ');
    const csrf = cookies.get('csrftoken');

    // Rebuild the form so fetch sets a fresh multipart boundary for the backend.
    const form = await request.formData();

    const upstream = await fetch(new URL('api/admin/restore', BASE_URL), {
        method: 'POST',
        headers: {
            Cookie: cookieHeader,
            Accept: 'application/json',
            ...(csrf ? { 'X-CSRFToken': csrf } : {}),
        },
        body: form,
    });
    const data = await upstream.json().catch(() => ({ code: 'error', message: 'Restore failed.' }));
    return json(data, { status: upstream.status });
}
