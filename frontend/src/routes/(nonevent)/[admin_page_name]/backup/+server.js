import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';

const BASE_URL = env.API_BASE_URL || 'http://backend:8080/';

/**
 * Stream the backend's database backup to the browser. The backend is only
 * reachable server-side, so this proxies the download, forwarding the admin's
 * session cookie and passing the attachment headers straight through.
 */
export async function GET({ cookies, fetch }) {
    const cookieHeader = cookies.getAll().map((c) => `${c.name}=${c.value}`).join('; ');
    const upstream = await fetch(new URL('api/admin/backup', BASE_URL), {
        headers: { Cookie: cookieHeader, Accept: 'application/gzip' },
    });
    if (!upstream.ok) {
        throw error(upstream.status, 'Backup could not be created.');
    }
    return new Response(upstream.body, {
        headers: {
            'Content-Type': upstream.headers.get('content-type') || 'application/gzip',
            'Content-Disposition':
                upstream.headers.get('content-disposition') || 'attachment; filename="ieum-backup.tar.gz"',
            'Cache-Control': 'no-store',
        },
    });
}
