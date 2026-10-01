import { get } from '$lib/fetch';

const INVITE_PATH = /^\/invite\/([A-Za-z0-9_-]+)$/;

/**
 * The invitation behind a `next` of /invite/<token>, if that is where the
 * visitor is headed: { email, event_name }, or null. The login and signup
 * pages use it to say which address the invitation went to, since only that
 * address can take it.
 */
export async function invitationForNext(next) {
    const match = (next || '').match(INVITE_PATH);
    if (!match) return null;
    const response = await get(`api/invitation/${encodeURIComponent(match[1])}`);
    if (!response.ok || response.status !== 200) return null;
    return { email: response.data.email, event_name: response.data.event_name };
}
