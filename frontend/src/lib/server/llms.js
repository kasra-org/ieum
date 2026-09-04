import { get } from '$lib/fetch';

/**
 * Plain-text rendering of the public events, for agents and crawlers.
 *
 * The event pages render their description with client-side JavaScript, so
 * anything fetching a URL without running scripts sees an empty shell. These
 * documents are the readable form of the same information.
 *
 * Everything here comes from the API called *without cookies*: anonymously it
 * returns only published, unarchived events, so a draft cannot leak into this
 * even when an administrator is the one fetching it.
 */

const PAGE_SIZE = 100;

export async function fetchPublicEvents() {
    let events = [];
    for (let offset = 0; ; offset += PAGE_SIZE) {
        const response = await get(`api/events?offset=${offset}&limit=${PAGE_SIZE}`);
        if (!response.ok || response.status !== 200) break;
        const page = response.data?.events ?? [];
        events = events.concat(page);
        if (events.length >= (response.data?.total ?? 0) || page.length === 0) break;
    }
    return events;
}

/** One event, fetched anonymously so an unpublished one is simply not found. */
export async function fetchPublicEvent(id) {
    const response = await get(`api/event/${id}`);
    return (response.ok && response.status === 200) ? response.data : null;
}

export async function fetchSiteSettings() {
    const response = await get('api/site-settings');
    return (response.ok && response.status === 200)
        ? response.data
        : { site_name: 'IEUM', site_description: '' };
}

/**
 * Make root-relative targets absolute.
 *
 * Uploaded images are embedded as /media/editor/images/..., which resolves fine
 * inside a page but not in a text file fetched on its own: whoever reads it has
 * no base to resolve against, so the image cannot be downloaded.
 */
function absoluteUrls(markdown, origin) {
    return markdown
        .replace(/(\]\()(\/[^)\s]*)/g, `$1${origin}$2`)          // [text](/path) and ![alt](/path)
        .replace(/((?:src|href)=")(\/[^"]*)/gi, `$1${origin}$2`);   // any raw HTML that slipped in
}

/** Absolute URLs of every image embedded in the description. */
function imageUrls(markdown, origin) {
    const urls = [];
    const pattern = /!\[[^\]]*\]\(([^)\s]+)/g;
    let match;
    while ((match = pattern.exec(markdown)) !== null) {
        const url = match[1];
        urls.push(url.startsWith('/') ? origin + url : url);
    }
    return urls;
}

function formatDateRange(start, end) {
    if (!start) return '';
    return start === end ? start : `${start} to ${end}`;
}

function formatFee(fee) {
    return fee > 0 ? `KRW ${Number(fee).toLocaleString('en-US')}` : 'Free';
}

/**
 * Push a description's own headings one level down, so its "## Schedule" sits
 * under the event rather than beside it. Fenced code is left alone, where a
 * leading # is a comment rather than a heading.
 */
function demoteHeadings(markdown) {
    let inFence = false;
    return markdown.split('\n').map((line) => {
        if (/^\s*(```|~~~)/.test(line)) { inFence = !inFence; return line; }
        if (inFence) return line;
        return line.replace(/^(#{1,5})(\s)/, '#$1$2');
    }).join('\n');
}

function eventSummary(event, origin) {
    const parts = [formatDateRange(event.start_date, event.end_date)];
    if (event.venue) parts.push(event.venue);
    return `- [${event.name}](${origin}/event/${event.id}): ${parts.filter(Boolean).join(', ')}`;
}

export function renderEvent(event, origin) {
    return eventSection(event, origin);
}

function eventSection(event, origin) {
    const lines = [`## ${event.name}`, ''];
    const field = (label, value) => { if (value) lines.push(`- ${label}: ${value}`); };

    field('Dates', formatDateRange(event.start_date, event.end_date));
    field('Venue', [event.venue, event.venue_address].filter(Boolean).join(' - '));
    field('Organizers', event.organizers_en);
    field('Registration deadline', event.registration_deadline);
    field('Registration page', `${origin}/event/${event.id}/register`);
    field('Event page', `${origin}/event/${event.id}`);
    if (event.link_info) field('Official website', event.link_info);
    if (event.is_invitation_only) field('Access', 'Invitation only');

    const categories = event.registration_categories ?? [];
    if (categories.length > 0) {
        lines.push('- Registration fees:');
        for (const category of categories) {
            lines.push(`    - ${category.name}: ${formatFee(category.fee)}`);
        }
    } else {
        field('Registration fee', 'Free');
    }

    if (event.accepts_abstract) {
        field('Abstract submission', event.abstract_submission_type === 'external'
            ? (event.external_abstract_url || 'External system')
            : `${origin}/event/${event.id}/abstract`);
        field('Abstract deadline', event.abstract_deadline);
    }

    if (event.description) {
        const images = imageUrls(event.description, origin);
        if (images.length > 0) {
            lines.push(`- Images in the description (downloadable):`);
            for (const url of images) lines.push(`    - ${url}`);
        }
        lines.push('', demoteHeadings(absoluteUrls(event.description.trim(), origin)));
    }
    lines.push('');
    return lines.join('\n');
}

/** The index: what exists, and where to read more. */
export function renderIndex(settings, events, origin) {
    const lines = [`# ${settings.site_name || 'IEUM'}`, ''];
    if (settings.site_description) lines.push(`> ${settings.site_description}`, '');
    lines.push(
        `This file lists the conferences and events published on this site.`,
        `For the same list with full descriptions and fees, see ${origin}/llms-full.txt.`,
        '',
        '## Events',
        '',
    );
    lines.push(events.length
        ? events.map((event) => eventSummary(event, origin)).join('\n')
        : '_No public events at the moment._');
    lines.push('');
    return lines.join('\n');
}

/** Everything, so an agent can answer questions from a single fetch. */
export function renderFull(settings, events, origin) {
    const lines = [`# ${settings.site_name || 'IEUM'}`, ''];
    if (settings.site_description) lines.push(`> ${settings.site_description}`, '');
    lines.push(`Full details of every event published on this site.`, '');
    lines.push(events.length
        ? events.map((event) => eventSection(event, origin)).join('\n')
        : '_No public events at the moment._\n');
    return lines.join('\n');
}
