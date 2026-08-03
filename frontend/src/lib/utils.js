import { languageTag } from '$lib/paraglide/runtime.js';

/**
 * Get the display name for an institution based on the current UI language
 * Works with both User objects (institute_en/institute_ko) and Attendee objects (institute/institute_ko)
 * @param {Object} obj - User or Attendee object
 * @returns {string} - Institution name in the appropriate language
 */
export function getDisplayInstitute(obj) {
    const currentLang = languageTag();
    if (currentLang === 'ko' && obj.institute_ko) {
        return obj.institute_ko;
    }
    // For User objects, use institute_en; for Attendee objects, use institute
    return obj.institute_en || obj.institute || '';
}

/**
 * Get the display name for a person based on the current UI language
 * Works with both User and Attendee objects
 * @param {Object} obj - User or Attendee object
 * @returns {string} - Person's name in the appropriate language
 */
export function getDisplayName(obj) {
    const currentLang = languageTag();
    if (currentLang === 'ko' && obj.korean_name) {
        return obj.korean_name;
    }
    return obj.name || '';
}

/**
 * Get the display venue for an event based on the current UI language
 * @param {Object} event - Event object
 * @returns {string} - Venue name in the appropriate language
 */
export function getDisplayVenue(event) {
    const currentLang = languageTag();
    if (currentLang === 'ko' && event.venue_ko) {
        return event.venue_ko;
    }
    return event.venue || '';
}

/**
 * Get the display venue address for an event based on the current UI language
 * @param {Object} event - Event object
 * @returns {string} - Venue address in the appropriate language
 */
export function getDisplayVenueAddress(event) {
    const currentLang = languageTag();
    if (currentLang === 'ko' && event.venue_address_ko) {
        return event.venue_address_ko;
    }
    return event.venue_address || '';
}

/**
 * Get the display organizers for an event based on the current UI language
 * @param {Object} event - Event object
 * @returns {string} - Formatted organizers string in the appropriate language
 * Format: "Name (Institution), Name (Institution)"
 */
export function getDisplayOrganizers(event) {
    const currentLang = languageTag();
    if (currentLang === 'ko' && event.organizers_ko) {
        return event.organizers_ko;
    }
    return event.organizers_en || '';
}

/**
 * Format a date string based on the current UI language
 * @param {string} dateString - Date string in YYYY-MM-DD format
 * @returns {string} - Formatted date
 * Korean: 2026.04.22
 * English: Apr 22, 2026
 */
export function formatDate(dateString) {
    if (!dateString) return '';

    const currentLang = languageTag();
    const date = new Date(dateString + 'T00:00:00'); // Add time to avoid timezone issues

    if (currentLang === 'ko') {
        // Korean format: 2026.04.22
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}.${month}.${day}`;
    } else {
        // English format: Apr 22, 2026
        const options = { year: 'numeric', month: 'short', day: 'numeric' };
        return date.toLocaleDateString('en-US', options);
    }
}

/**
 * Format a date range based on the current UI language
 * @param {string} startDate - Start date in YYYY-MM-DD format
 * @param {string} endDate - End date in YYYY-MM-DD format
 * @returns {string} - Formatted date range
 * Korean: 2026.04.22 ~ 2026.04.30
 * English: Apr 22, 2026 - Apr 30, 2026
 */
export function formatDateRange(startDate, endDate) {
    if (!startDate || !endDate) return '';

    const currentLang = languageTag();
    const separator = currentLang === 'ko' ? ' ~ ' : ' - ';

    return formatDate(startDate) + separator + formatDate(endDate);
}

/**
 * Validate that name fields contain only Latin/European characters
 * Includes: a-z, A-Z, accented letters (À-ÿ), and Latin Extended (Ā-ɏ)
 * @param {string} value - String to validate
 * @returns {boolean} - True if valid or empty, false otherwise
 */
const latinOnlyRegex = /^[a-zA-Z\u00C0-\u024F\s\-'.]+$/u;
export function onlyLatinChars(value) {
    if (!value) return true;
    return latinOnlyRegex.test(value);
}

/**
 * Sanitize redirect URL to prevent open redirect attacks.
 * Only allows relative URLs starting with '/'.
 * @param {string} url - URL to sanitize
 * @returns {string} - Safe redirect URL or '/' if invalid
 */
export function sanitizeRedirectUrl(url) {
    if (!url || typeof url !== 'string') {
        return '/';
    }
    // Only allow relative URLs starting with /
    // Reject URLs starting with // (protocol-relative) or containing ://
    // Backslashes and control characters are rejected too: browsers normalise
    // `/\evil.com` to `//evil.com`, which would otherwise slip through.
    if (!url.startsWith('/') || url.startsWith('//') || url.includes('://')) {
        return '/';
    }
    if (url.includes('\\') || /[\x00-\x1f\x7f]/.test(url)) {
        return '/';
    }
    return url;
}

/**
 * Check if a user profile is complete with all required fields.
 * Required fields depend on nationality:
 * - For all: nationality, job_title, institute, username must match email, first_name, last_name
 * - For Korean (1): additionally requires korean_name
 * - For non-Korean (2, 3): korean_name is optional
 * @param {Object} user - User object from API
 * @returns {boolean} - True if profile is complete
 */
export function isProfileComplete(user) {
    if (!user) return false;

    // Check that username matches email (social signups may have wrong username)
    if (user.username !== user.email) {
        return false;
    }

    // Check common required fields
    if (!user.nationality || !user.job_title || !user.institute) {
        return false;
    }

    // English name is always required for all users
    if (!user.first_name || user.first_name.trim() === '' ||
        !user.last_name || user.last_name.trim() === '') {
        return false;
    }

    // Korean nationals must also provide korean_name
    if (user.nationality === 1) {
        if (!user.korean_name || user.korean_name.trim() === '') {
            return false;
        }
    }

    return true;
}

/**
 * Open a receipt window for a payment
 * @param {string} paymentNumber - The order ID / payment number
 */
export function openReceiptWindow(paymentNumber) {
    window.open(
        `/receipt/${paymentNumber}`,
        '_blank',
        'width=800,height=900,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes'
    );
}

/**
 * Open a card receipt window for a card payment
 * @param {string} paymentNumber - The order ID / payment number
 */
export function openCardReceiptWindow(paymentNumber) {
    window.open(
        `/card-receipt/${paymentNumber}`,
        '_blank',
        'width=800,height=900,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes'
    );
}

/**
 * Check if a payment is a card payment
 * @param {Object} payment - Payment object with payment_type field
 * @returns {boolean} - True if payment type is card (카드)
 */
export function isCardPayment(payment) {
    return payment && payment.payment_type === '카드';
}

/**
 * Generate a unique order ID for payments
 * Format: {HHMMSS}{random} - 6 digit timestamp + random alphanumeric
 * @returns {string} Unique order ID
 */
export function generateOrderId() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const timestamp = `${hours}${minutes}${seconds}`;
    const random = Math.random().toString(36).substring(2, 10);
    return `${timestamp}${random}`;
}

/**
 * Human label for an abstract's requested presentation format.
 * Falls back to the legacy type/wants_short_talk pair for records that predate
 * presentation_type.
 */
export function getPresentationTypeLabel(abstract, m) {
    const type = abstract?.presentation_type
        ?? (abstract?.type === 'speaker'
            ? 'short_talk'
            : (abstract?.wants_short_talk ? 'short_talk_poster' : 'poster'));
    switch (type) {
        case 'short_talk_poster': return m.presentationType_shortTalkPoster();
        case 'short_talk': return m.presentationType_shortTalk();
        case 'flash_talk_poster': return m.presentationType_flashTalkPoster();
        case 'invited': return m.presentationType_invited();
        default: return m.presentationType_poster();
    }
}

/**
 * Today's date (YYYY-MM-DD) in the given IANA time zone.
 *
 * The backend decides whether on-site registration is open using the business
 * time zone, so anything gating the same window has to agree. Using UTC here
 * put the two out of step for the hours where the local date is ahead of UTC:
 * on the event's first morning in Seoul the page turned walk-ins away even
 * though the API would have accepted them.
 */
export function todayInTimeZone(timeZone = 'Asia/Seoul') {
    const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).formatToParts(new Date());
    const part = (type) => parts.find((p) => p.type === type)?.value;
    return `${part('year')}-${part('month')}-${part('day')}`;
}

/** Human label for an attendee's registration category. */
export function getStudentStatusLabel(status, m) {
    switch (status) {
        case 'undergraduate': return m.eventRegister_tierUndergraduate();
        case 'graduate': return m.eventRegister_tierGraduate();
        default: return m.eventRegister_tierPiNonAcademic();
    }
}
