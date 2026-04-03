<script>
    import { Button, Card, Heading } from 'flowbite-svelte';
    import {
        MapPinAltSolid,
        FacebookSolid,
        XSolid,
        LinkedinSolid,
        EnvelopeSolid,
        UsersSolid,
        CalendarMonthSolid,
        ClockSolid,
        FileLinesSolid,
        GlobeSolid,
        CreditCardSolid
    } from 'flowbite-svelte-icons';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { getDisplayVenue, getDisplayVenueAddress, getDisplayOrganizers, formatDate, formatDateRange } from '$lib/utils.js';
    import { marked } from 'marked';
    import { browser } from '$app/environment';
    import VenueMapWidget from '$lib/components/VenueMapWidget.svelte';

    let DOMPurify;

    // Configure marked options for consistent rendering
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    marked.use({
        hooks: {
            postprocess(html) {
                return html.replace(/<table>/g, '<div class="overflow-x-auto"><table>').replace(/<\/table>/g, '</table></div>');
            }
        }
    });

    let { data } = $props();
    let event = $derived(data.event);
    let user = $derived(data.user);
    let registered = $derived(data.registered);
    let payment_status = $derived(data.payment_status);
    let is_event_admin = $derived(data.is_event_admin);
    let abstract_submitted = $derived(data.abstract_submitted);

    // Check if user needs to pay (registered for paid event but hasn't paid)
    let needsPayment = $derived(
        registered &&
        event.registration_fee &&
        event.registration_fee > 0 &&
        payment_status === 'pending'
    );

    // Import DOMPurify only in browser
    $effect(() => {
        if (browser && !DOMPurify) {
            import('dompurify').then(module => {
                DOMPurify = module.default;
            });
        }
    });

    // Parse and sanitize markdown description
    let descriptionHtml = $derived.by(() => {
        if (!event.description) return '';
        const html = marked.parse(event.description);
        // Only sanitize in browser, marked already escapes dangerous content
        if (browser && DOMPurify) {
            return DOMPurify.sanitize(html);
        }
        return html;
    });

    // Check if registration is closed
    let isRegistrationClosed = $derived.by(() => {
        if (!event.registration_deadline) return false;
        const deadline = new Date(event.registration_deadline);
        deadline.setHours(23, 59, 59, 999);
        const now = new Date();
        return deadline < now;
    });

    // Format registration fee based on language
    let formattedRegistrationFee = $derived.by(() => {
        const fee = event.registration_fee || 0;
        if (fee === 0) {
            return m.eventDetail_registrationFeeFree();
        }
        const formattedAmount = fee.toLocaleString('ko-KR', {maximumFractionDigits: 0});
        return languageTag() === 'ko' ? `${formattedAmount} 원` : `KRW ${formattedAmount}`;
    });

    // Get current page URL for sharing
    let pageUrl = $state('');
    $effect(() => {
        if (typeof window !== 'undefined') {
            pageUrl = window.location.href;
        }
    });

    // Share text
    const shareText = `${event.name} - ${formatDateRange(event.start_date, event.end_date)} at ${getDisplayVenue(event)}`;
    const shareTitle = event.name;

    // Share functions
    function shareOnFacebook() {
        const url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(pageUrl)}`;
        window.open(url, '_blank', 'width=600,height=400');
    }

    function shareOnX() {
        const url = `https://x.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(pageUrl)}`;
        window.open(url, '_blank', 'width=600,height=400');
    }

    function shareOnLinkedIn() {
        const url = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(pageUrl)}`;
        window.open(url, '_blank', 'width=600,height=400');
    }

    function shareViaEmail() {
        const subject = encodeURIComponent(shareTitle);
        const body = encodeURIComponent(`${shareText}\n\nLearn more: ${pageUrl}`);
        window.location.href = `mailto:?subject=${subject}&body=${body}`;
    }
</script>

<svelte:head>
    <title>{event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
    <meta property="og:title" content="{event.name} | {data.site_settings?.site_name ?? 'IEUM'}" />
    <meta property="twitter:title" content="{event.name} | {data.site_settings?.site_name ?? 'IEUM'}" />
</svelte:head>

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{event.name}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/" class="hover:underline">{m.eventDetail_breadcrumbEvents()}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">{event.name}</span>
            </p>
        </div>
    </div>

    <!-- Main Content -->
    <div class="grid grid-cols-1 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
        <!-- Left Column - Main Content (appears second on mobile) -->
        <div class="lg:col-span-2 2xl:col-span-3 space-y-6 order-2 lg:order-1">
            <!-- Event Details -->
            <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <!-- Dates -->
                    <div class="flex items-start gap-3">
                        <CalendarMonthSolid class="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                        <div class="flex-1">
                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{m.eventDetail_eventDates()}</p>
                            <p class="text-sm text-gray-900 font-medium">{formatDateRange(event.start_date, event.end_date)}</p>
                            {#if event.registration_deadline}
                                <p class="text-xs text-gray-600 mt-1.5">
                                    <span class="font-medium">{m.eventDetail_registrationDeadline()}:</span> {formatDate(event.registration_deadline)}
                                </p>
                            {/if}
                            {#if event.abstract_deadline && event.accepts_abstract && event.abstract_submission_type === 'internal'}
                                <p class="text-xs text-gray-600 mt-1.5">
                                    <span class="font-medium">{m.eventDetail_abstractDeadline()}:</span> {formatDate(event.abstract_deadline)}
                                </p>
                            {/if}
                        </div>
                    </div>

                    <!-- Venue -->
                    <div class="flex items-start gap-3">
                        <MapPinAltSolid class="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
                        <div class="flex-1">
                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{m.eventDetail_venue()}</p>
                            <p class="text-sm text-gray-900 font-medium">{getDisplayVenue(event)}</p>
                            {#if getDisplayVenueAddress(event)}
                                <p class="text-xs text-gray-600 mt-1">{getDisplayVenueAddress(event)}</p>
                            {/if}
                        </div>
                    </div>

                    <!-- Organizer -->
                    <div class="flex items-start gap-3">
                        <UsersSolid class="w-5 h-5 text-purple-500 mt-0.5 flex-shrink-0" />
                        <div class="flex-1">
                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{m.eventDetail_organizer()}</p>
                            <p class="text-sm text-gray-900 font-medium">{getDisplayOrganizers(event)}</p>
                        </div>
                    </div>

                    <!-- Main Languages -->
                    {#if event.main_languages && event.main_languages.length > 0}
                    <div class="flex items-start gap-3">
                        <GlobeSolid class="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                        <div class="flex-1">
                            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{m.eventDetail_mainLanguages()}</p>
                            <p class="text-sm text-gray-900 font-medium">
                                {event.main_languages.map(lang => lang === 'ko' ? m.language_korean() : m.language_english()).join(', ')}
                            </p>
                        </div>
                    </div>
                    {/if}
                </div>

                {#if descriptionHtml}
                    <div class="prose prose-gray max-w-none mt-6 pt-6 border-t border-gray-200">
                        {@html descriptionHtml}
                    </div>
                {/if}
            </div>
        </div>

        <!-- Right Column - Sidebar (appears first on mobile) -->
        <div class="space-y-6 order-1 lg:order-2">
            <!-- Registration Information -->
            <div class="bg-gray-50 border border-gray-200 rounded-lg shadow-sm p-6">
                {#if user && registered}
                    <div class="space-y-4">
                        {#if needsPayment}
                            <div class="bg-orange-100 border border-orange-400 text-orange-700 px-4 py-3 rounded">
                                <p class="font-semibold">{m.eventDetail_paymentPending()}</p>
                                <p class="text-sm mt-1">{m.eventDetail_paymentPendingDescription()}</p>
                            </div>
                            <div class="flex justify-between items-center">
                                <span class="text-base font-medium text-gray-700">{m.eventDetail_registrationFee()}</span>
                                <span class="{languageTag() === 'ko' ? 'text-xl' : 'text-lg'} font-bold text-gray-900">{formattedRegistrationFee}</span>
                            </div>
                            <Button href="/event/{event.id}/register" color="primary" class="w-full">
                                {m.eventRegister_payNow()}
                            </Button>
                        {:else}
                            <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
                                <p class="font-semibold">{m.eventDetail_registered()}</p>
                                <p class="text-sm mt-1">{m.eventDetail_registeredThankYou()}</p>
                            </div>
                            {#if event.accepts_abstract}
                                {#if event.abstract_submission_type === 'external' && event.external_abstract_url}
                                    <Button href={event.external_abstract_url} target="_blank" rel="noopener noreferrer" color="primary" class="w-full">
                                        {m.eventDetail_submitAbstract()}
                                    </Button>
                                {:else}
                                    <Button href="/event/{event.id}/abstract" color="primary" class="w-full">
                                        {abstract_submitted ? m.eventDetail_viewAbstract() : m.eventDetail_submitAbstract()}
                                    </Button>
                                {/if}
                            {/if}
                        {/if}
                        <Button href="/event/{event.id}/registration" color="alternative" class="w-full">
                            {m.eventDetail_viewRegistration()}
                        </Button>
                        {#if is_event_admin}
                            <hr class="mt-2 mb-6 border-gray-200" />
                            <Button href="/event/{event.id}/admin" color="primary" class="w-full">
                                {m.eventDetail_manageEvent()}
                            </Button>
                        {/if}
                    </div>
                {:else}
                    <div class="space-y-4">
                        {#if isRegistrationClosed}
                            <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                                <p class="font-semibold">{m.eventRegister_closed()}</p>
                            </div>
                        {:else if user}
                            <div class="flex justify-between items-center">
                                <span class="text-base font-medium text-gray-700">{m.eventDetail_registrationFee()}</span>
                                <span class="{languageTag() === 'ko' ? 'text-xl' : 'text-lg'} font-bold text-gray-900">{formattedRegistrationFee}</span>
                            </div>
                            <Button href="/event/{event.id}/register" color="primary" class="w-full">
                                {m.eventDetail_registerNow()}
                            </Button>
                        {:else}
                            <div class="flex justify-between items-center">
                                <span class="text-base font-medium text-gray-700">{m.eventDetail_registrationFee()}</span>
                                <span class="{languageTag() === 'ko' ? 'text-xl' : 'text-lg'} font-bold text-gray-900">{formattedRegistrationFee}</span>
                            </div>
                            <Button href="/login?next={encodeURIComponent(`/event/${event.id}`)}" color="primary" class="w-full">
                                {m.eventDetail_loginToRegister()}
                            </Button>
                            <p class="text-xs text-center text-gray-600">
                                {m.eventDetail_noAccount()}
                                <a href="/registration?next={encodeURIComponent(`/event/${event.id}`)}" class="text-blue-600 hover:underline">{m.eventDetail_signUpHere()}</a>
                            </p>
                        {/if}

                        {#if is_event_admin}
                            <Button href="/event/{event.id}/admin" color="primary" class="w-full">
                                {m.eventDetail_manageEvent()}
                            </Button>
                        {/if}
                    </div>
                {/if}
                <hr class="my-6 border-gray-200" />
                <div class="flex gap-3">
                    <button onclick={shareOnFacebook} class="p-2 rounded-full bg-blue-600 text-white hover:bg-blue-700" aria-label={m.eventDetail_shareOnFacebook()}>
                        <FacebookSolid class="w-5 h-5" />
                    </button>
                    <button onclick={shareOnX} class="p-2 rounded-full bg-black text-white hover:bg-gray-800" aria-label={m.eventDetail_shareOnX()}>
                        <XSolid class="w-5 h-5" />
                    </button>
                    <button onclick={shareOnLinkedIn} class="p-2 rounded-full bg-blue-700 text-white hover:bg-blue-800" aria-label={m.eventDetail_shareOnLinkedIn()}>
                        <LinkedinSolid class="w-5 h-5" />
                    </button>
                    <button onclick={shareViaEmail} class="p-2 rounded-full bg-gray-600 text-white hover:bg-gray-700" aria-label={m.eventDetail_shareViaEmail()}>
                        <EnvelopeSolid class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Location Map (hidden on mobile, only shown if coordinates are provided) -->
            {#if event.venue_latitude && event.venue_longitude}
            <div class="hidden lg:block">
            <VenueMapWidget
                venueName={getDisplayVenue(event)}
                venueAddress={getDisplayVenueAddress(event)}
                venueLatitude={event.venue_latitude}
                venueLongitude={event.venue_longitude}
            />
            </div>
            {/if}
        </div>
    </div>
</div>
