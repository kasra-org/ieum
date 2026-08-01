<script>
    import { Input, Label, Button, Checkbox, Spinner, Tooltip } from '$lib/components/ui';
    import { Calendar, Check, CircleUser, CircleX, Clock, Globe, MapPin, Search } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayVenue, getDisplayOrganizers } from '$lib/utils.js';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import { onMount } from 'svelte';
    import { browser } from '$app/environment';
    import YearSelector from '$lib/components/YearSelector.svelte';

    let { data } = $props();

    // Events state - accumulate results for infinite scroll
    let allEvents = $state([]);
    let total = $state(0);
    let currentOffset = $state(0);
    let hasMore = $derived(allEvents.length < total);
    let navigating = $state(false);

    // Initialize filter state from URL
    let searchKeyword = $state($page.url.searchParams.get('search') || '');
    let showOnlyOpen = $state($page.url.searchParams.get('showOnlyOpen') === 'true');
    let selectedYear = $state($page.url.searchParams.get('year') || 'all');

    // Debounce timer for search
    let searchTimer;

    // Update events when data changes (from server load)
    $effect(() => {
        if (data.eventsData) {
            const newOffset = parseInt($page.url.searchParams.get('offset') || '0');

            if (newOffset === 0) {
                // Reset - new search/filter
                allEvents = data.eventsData.events || [];
            } else {
                // Append - load more
                const existingIds = new Set(allEvents.map(e => e.id));
                const newEvents = (data.eventsData.events || []).filter(e => !existingIds.has(e.id));
                allEvents = [...allEvents, ...newEvents];
            }

            total = data.eventsData.total || 0;
            currentOffset = newOffset + (data.eventsData.events?.length || 0);
        }
    });

    // Update URL with current filters
    function updateURL(reset = false) {
        const params = new URLSearchParams();

        if (reset) {
            params.set('offset', '0');
        } else {
            params.set('offset', currentOffset.toString());
        }

        if (selectedYear !== 'all') params.set('year', selectedYear);
        if (searchKeyword.trim()) params.set('search', searchKeyword.trim());
        if (showOnlyOpen) params.set('showOnlyOpen', 'true');

        navigating = true;
        goto(`?${params.toString()}`, {
            keepFocus: true,
            noScroll: !reset,
            replaceState: !reset
        }).finally(() => {
            navigating = false;
        });
    }

    function handleYearChange(year) {
        updateURL(true);
    }

    // Handle search with debounce
    function handleSearchChange() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => {
            updateURL(true);
        }, 500);
    }

    // Handle checkbox change
    function handleCheckboxChange() {
        updateURL(true);
    }

    // Clear all filters
    function clearFilters() {
        searchKeyword = '';
        showOnlyOpen = false;
        selectedYear = 'all';
        updateURL(true);
    }

    // Load more events
    function loadMore() {
        if (navigating || !hasMore) return;
        updateURL(false);
    }

    // Infinite scroll handler
    onMount(() => {
        if (browser) {
            window.addEventListener('scroll', () => {
                if (navigating || !hasMore) return;

                const scrollHeight = document.documentElement.scrollHeight;
                const scrollTop = window.scrollY;
                const clientHeight = window.innerHeight;
                const scrollPercentage = (scrollTop + clientHeight) / scrollHeight;

                // Load more when scrolled to 80%
                if (scrollPercentage > 0.8) {
                    loadMore();
                }
            });
        }

        return () => {
            clearTimeout(searchTimer);
        };
    });

    function isEventOpen(event) {
        if (!event.registration_deadline) return true;
        const today = new Date().toISOString().split('T')[0];
        return event.registration_deadline >= today;
    }

    function isClosingSoon(event) {
        if (!event.registration_deadline) return false;
        const today = new Date();
        const deadline = new Date(event.registration_deadline);
        const daysUntilDeadline = Math.ceil((deadline - today) / (1000 * 60 * 60 * 24));
        return daysUntilDeadline > 0 && daysUntilDeadline <= 7;
    }

    function getStatusColor(event) {
        if (!isEventOpen(event)) return 'text-gray-500';
        if (isClosingSoon(event)) return 'text-orange-600';
        return 'text-green-600';
    }

    function getStatusText(event) {
        if (!isEventOpen(event)) return m.events_registrationClosed();
        if (isClosingSoon(event)) return m.events_registrationClosingSoon();
        return m.events_registrationOpen();
    }

    // Get border color based on event status
    function getBorderColor(event) {
        if (!isEventOpen(event)) return 'bg-gray-400';
        if (isClosingSoon(event)) return 'bg-orange-500';
        return 'bg-green-600';
    }

    // Get category badge color
    function getCategoryColor(category) {
        switch (category) {
            case 'hackathon': return 'text-green-700 bg-green-100';
            case 'symposium': return 'text-blue-700 bg-blue-100';
            case 'workshop': return 'text-purple-700 bg-purple-100';
            case 'meeting': return 'text-gray-700 bg-gray-100';
            case 'conference': return 'text-indigo-700 bg-indigo-100';
            default: return 'text-blue-700 bg-blue-100';
        }
    }

    // Format date as MM.DD
    function formatShortDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${month}.${day}`;
    }

    // Get year from date
    function getYear(dateStr) {
        if (!dateStr) return '';
        return new Date(dateStr).getFullYear();
    }

    // Highlight matched text in search results
    const escapeHtml = (value) =>
        String(value ?? '').replace(/[&<>"']/g, (c) =>
            ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
        );

    // The result is rendered with {@html}, so everything drawn from event data
    // has to be escaped first — previously an event name containing markup was
    // executed for every visitor, and with an empty keyword it was returned
    // completely raw.
    function highlightText(text, keyword) {
        const safe = escapeHtml(text);
        const trimmed = keyword?.trim();
        if (!trimmed) return safe;

        // Escape for HTML before escaping for the regex, so the pattern matches
        // the already-escaped haystack.
        const needle = escapeHtml(trimmed).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return safe.replace(new RegExp(`(${needle})`, 'gi'), '<mark class="bg-yellow-200">$1</mark>');
    }
</script>

<svelte:head>
    <title>{m.events_browse()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="container mx-auto my-10 px-3 sm:px-7">
        <!-- Page Header Card -->
        <div class="relative rounded-lg shadow-sm py-16 px-8 mb-4 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
            <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
            <div class="relative z-10">
                <h1 class="text-3xl font-bold text-white">{m.events_browse()}</h1>
                <p class="text-slate-200 mt-2">{m.events_discover()}</p>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <!-- Left Sidebar - Filters -->
        <div class="lg:col-span-1">
            <div class="sticky top-8">
                <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8 space-y-6">
                    <!-- Keyword Search -->
                    <div>
                        <Label class="mb-2 text-sm font-semibold text-gray-700">{m.events_search()}</Label>
                        <div class="relative">
                            <Input
                                type="text"
                                bind:value={searchKeyword}
                                oninput={handleSearchChange}
                                placeholder={m.events_searchPlaceholder()}
                                class="pl-10"
                            />
                            <Search class="w-4 h-4 absolute left-3 top-3 text-gray-400" />
                        </div>
                    </div>

                    <!-- Year Selector -->
                    <YearSelector bind:selectedYear onYearChange={handleYearChange} />

                    <!-- Status Filter -->
                    <div>
                        <Label class="mb-2 text-sm font-semibold text-gray-700">{m.events_status()}</Label>
                        <Checkbox bind:checked={showOnlyOpen} onchange={handleCheckboxChange}>{m.events_showOnlyOpen()}</Checkbox>
                    </div>

                    <!-- Clear Filters -->
                    {#if searchKeyword || showOnlyOpen || selectedYear !== 'all'}
                        <Button
                            color="light"
                            class="w-full"
                            onclick={clearFilters}
                        >
                            {m.events_clearFilters()}
                        </Button>
                    {/if}
                </div>
            </div>
        </div>

        <!-- Right Content - Events List -->
        <div class="lg:col-span-2 xl:col-span-3">
            <div class="bg-white border border-gray-200 rounded-lg shadow-sm px-4 sm:px-6">
                {#if navigating && allEvents.length === 0}
                    <div class="text-center py-16">
                        <Spinner size="12" />
                        <p class="text-gray-600 mt-4">Loading events...</p>
                    </div>
                {:else if allEvents.length === 0}
                    <div class="text-center py-16">
                        <Calendar class="w-16 h-16 mx-auto text-gray-400 mb-4" />
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">{m.events_noResults()}</h3>
                        <p class="text-gray-600">{m.events_noResultsDesc()}</p>
                    </div>
                {:else}
                    <div class="divide-y divide-gray-200">
                        {#each allEvents as event}
                            <a href="/event/{event.id}" class={`flex items-stretch gap-4 sm:gap-6 py-6 -mx-4 sm:-mx-6 px-4 sm:px-6 hover:bg-gray-50 transition-colors cursor-pointer ${!isEventOpen(event) ? 'opacity-50' : ''}`}>
                                <!-- Left Color Bar + Date (hidden below 2xl) -->
                                <div class="hidden 2xl:flex items-center flex-shrink-0">
                                    <div class={`w-1 self-stretch rounded-full ${getBorderColor(event)}`}></div>
                                    <div class="w-48 pl-4 pr-5 flex flex-col justify-center">
                                        <span class="text-sm text-gray-400">{getYear(event.start_date)}</span>
                                        <div class="flex items-baseline gap-1.5 text-xl font-bold text-gray-800">
                                            <span>{formatShortDate(event.start_date)}</span>
                                            <span class="text-gray-400 font-normal text-sm">~</span>
                                            <span>{formatShortDate(event.end_date)}</span>
                                        </div>
                                        {#if event.registration_deadline}
                                            <span class="text-xs text-gray-400 mt-0.5">{m.events_registrationDeadline()}: {formatShortDate(event.registration_deadline)}</span>
                                        {/if}
                                    </div>
                                </div>

                                <!-- Left Color Bar only (shown below 2xl) -->
                                <div class="flex 2xl:hidden items-center flex-shrink-0">
                                    <div class={`w-1 self-stretch rounded-full ${getBorderColor(event)}`}></div>
                                </div>

                                <!-- Main Content -->
                                <div class="flex-1 min-w-0">
                                    <!-- Event Title -->
                                    <span class="text-lg sm:text-xl font-bold text-gray-900">
                                        {@html highlightText(event.name, searchKeyword)}
                                    </span>

                                    <!-- Badges -->
                                    <div class="mt-1.5 flex items-center gap-1.5 flex-wrap">
                                        {#if event.category}
                                            <span class={`inline-block text-xs font-medium px-2 py-0.5 rounded ${getCategoryColor(event.category)}`}>
                                                {#if event.category === 'workshop'}
                                                    {m.eventCategory_workshop()}
                                                {:else if event.category === 'hackathon'}
                                                    {m.eventCategory_hackathon()}
                                                {:else if event.category === 'symposium'}
                                                    {m.eventCategory_symposium()}
                                                {:else if event.category === 'meeting'}
                                                    {m.eventCategory_meeting()}
                                                {:else if event.category === 'conference'}
                                                    {m.eventCategory_conference()}
                                                {/if}
                                            </span>
                                        {/if}
                                        {#if event.is_invitation_only}
                                            <span id="invitation-badge-{event.id}" class="inline-block text-xs font-medium text-orange-700 bg-orange-100 px-2 py-0.5 rounded">
                                                {m.eventStatus_invitationOnly()}
                                            </span>
                                            <Tooltip triggeredBy="#invitation-badge-{event.id}" placement="right">
                                                {m.eventStatus_invitationOnlyTooltip()}
                                            </Tooltip>
                                        {/if}
                                        {#if !event.published}
                                            <span id="draft-badge-{event.id}" class="inline-block text-xs font-medium text-gray-600 bg-gray-200 px-2 py-0.5 rounded">
                                                {m.eventStatus_draft()}
                                            </span>
                                            <Tooltip triggeredBy="#draft-badge-{event.id}" placement="right">
                                                {m.eventStatus_draftTooltip()}
                                            </Tooltip>
                                        {/if}
                                    </div>

                                    <!-- Date info (shown below 2xl) -->
                                    <div class="2xl:hidden mt-1.5 flex items-center gap-2 text-sm text-gray-500">
                                        <span class="font-medium">{getYear(event.start_date)} {formatShortDate(event.start_date)} ~ {formatShortDate(event.end_date)}</span>
                                        {#if event.registration_deadline}
                                            <span class="text-gray-400">|</span>
                                            <span>{m.events_registrationDeadline()}: {formatShortDate(event.registration_deadline)}</span>
                                        {/if}
                                    </div>

                                    <!-- Meta Info -->
                                    <div class="mt-2 flex items-center gap-3 text-sm text-gray-500 flex-wrap">
                                        <span class="flex items-center gap-1">
                                            <MapPin class="w-4 h-4" />
                                            <span>{@html highlightText(getDisplayVenue(event), searchKeyword)}</span>
                                        </span>
                                        <span class="flex items-center gap-1">
                                            <CircleUser class="w-4 h-4" />
                                            <span>{@html highlightText(getDisplayOrganizers(event), searchKeyword)}</span>
                                        </span>
                                        {#if event.main_languages && event.main_languages.length > 0}
                                            <span class="flex items-center gap-1">
                                                <Globe class="w-4 h-4" />
                                                <span>{event.main_languages.map(lang => lang === 'ko' ? m.language_korean() : m.language_english()).join(', ')}</span>
                                            </span>
                                        {/if}
                                    </div>
                                </div>

                                <!-- Right: Registration Status -->
                                <div
                                    class={`hidden sm:flex flex-shrink-0 items-center gap-1.5 pl-4 text-sm font-medium whitespace-nowrap ${
                                        !isEventOpen(event)
                                            ? 'text-gray-400'
                                            : isClosingSoon(event)
                                                ? 'text-orange-500'
                                                : 'text-green-600'
                                    }`}
                                >
                                    {#if !isEventOpen(event)}
                                        <CircleX class="w-5 h-5" />
                                    {:else if isClosingSoon(event)}
                                        <Clock class="w-5 h-5" />
                                    {:else}
                                        <Check class="w-5 h-5" />
                                    {/if}
                                    {getStatusText(event)}
                                </div>
                            </a>
                        {/each}

                        <!-- Load More Indicator -->
                        {#if navigating}
                            <div class="text-center py-8">
                                <Spinner size="8" />
                                <p class="text-gray-600 mt-2 text-sm">Loading more events...</p>
                            </div>
                        {:else if hasMore}
                            <div class="text-center py-8">
                                <p class="text-gray-500 text-sm">Scroll down to load more events</p>
                            </div>
                        {/if}
                    </div>
                {/if}
            </div>
        </div>
    </div>
</div>
