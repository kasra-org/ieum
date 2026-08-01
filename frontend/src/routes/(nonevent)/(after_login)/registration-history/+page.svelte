<script>
    let { data: page_data } = $props();
    import { TableSearch, TableBody, TableBodyCell, TableBodyRow, TableHead, TableHeadCell, Button } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import { getDisplayVenue, getDisplayOrganizers, formatDateRange } from '$lib/utils.js';
    import { generateCertificatePDF } from '$lib/pdfUtils.js';

    let registrations = page_data.registrations || [];

    // Check if event has ended (certificate can only be generated after event ends)
    function hasEventEnded(endDate) {
        return endDate ? new Date() > new Date(endDate) : false;
    }

    function getPaymentStatusText(status) {
        switch (status) {
            case 'free':
                return m.registrationHistory_statusFree();
            case 'completed':
                return m.paymentHistory_statusCompleted();
            case 'pending':
                return m.paymentHistory_statusPending();
            default:
                return status;
        }
    }

    function getPaymentStatusColor(status) {
        switch (status) {
            case 'free':
                return 'text-blue-600';
            case 'completed':
                return 'text-green-600';
            case 'pending':
                return 'text-orange-500';
            default:
                return 'text-gray-600';
        }
    }

    // Generate certificate PDF for a registration
    async function generateCertificate(registration) {
        const certAttendee = {
            name: registration.attendee_name,
            institute: registration.attendee_institute
        };

        const certEvent = {
            name: registration.event_name,
            start_date: registration.start_date,
            end_date: registration.end_date,
            venue: registration.venue,
            venue_ko: registration.venue_ko,
            organizers_en: registration.organizers_en,
            organizers_ko: registration.organizers_ko
        };

        const certMessages = {
            certIssueDate: m.attendees_certIssueDate,
            certTitle: m.attendees_certTitle,
            certName: m.attendees_certName,
            certInstitute: m.attendees_certInstitute,
            certHasAttended: m.attendees_certHasAttended,
            certOn: m.attendees_certOn,
            certHeldAt: m.attendees_certHeldAt,
            certAsParticipant: m.attendees_certAsParticipant,
            certFooter: m.attendees_certFooter
        };

        const pdfUri = await generateCertificatePDF({
            attendee: certAttendee,
            event: certEvent,
            messages: certMessages
        });

        window.open(pdfUri, '_blank');
    }

    // Search and pagination state
    let searchTerm = $state('');
    let currentPage = $state(1);
    const itemsPerPage = 10;

    // Filter registrations based on search term
    let filteredRegistrations = $derived(
        registrations.filter((item) =>
            item.event_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            item.organizers_en.toLowerCase().includes(searchTerm.toLowerCase()) ||
            item.organizers_ko.toLowerCase().includes(searchTerm.toLowerCase())
        )
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTerm;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filteredRegistrations.length / itemsPerPage));
    let paginatedRegistrations = $derived(
        filteredRegistrations.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }
</script>

<svelte:head>
    <title>{m.registrationHistory_title()} | {page_data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.registrationHistory_title()}</h1>
        <p class="text-slate-200 mt-2">{m.registrationHistory_description()}</p>
    </div>
</div>

<!-- Table Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <TableSearch placeholder={m.registrationHistory_searchPlaceholder()} hoverable={true} striped={true} bind:inputValue={searchTerm}>
        <TableHead>
            <TableHeadCell class="whitespace-nowrap">{m.registrationHistory_dates()}</TableHeadCell>
            <TableHeadCell class="w-full">{m.registrationHistory_eventName()}</TableHeadCell>
            <TableHeadCell class="whitespace-nowrap">{m.registrationHistory_venue()}</TableHeadCell>
            <TableHeadCell class="whitespace-nowrap">{m.registrationHistory_organizers()}</TableHeadCell>
            <TableHeadCell class="whitespace-nowrap">{m.registrationHistory_paymentStatus()}</TableHeadCell>
            <TableHeadCell class="whitespace-nowrap">{m.registrationHistory_actions()}</TableHeadCell>
        </TableHead>
        <TableBody>
            {#if filteredRegistrations.length === 0}
                <TableBodyRow>
                    <TableBodyCell colspan="6" class="text-center text-gray-500 py-8">
                        {m.registrationHistory_noRecords()}
                    </TableBodyCell>
                </TableBodyRow>
            {:else}
                {#each paginatedRegistrations as registration}
                    <TableBodyRow>
                        <TableBodyCell class="align-top whitespace-nowrap">
                            {formatDateRange(registration.start_date, registration.end_date)}
                        </TableBodyCell>
                        <TableBodyCell class="align-top w-full">
                            <a href="/event/{registration.event_id}" class="font-medium text-gray-900 underline">{registration.event_name}</a>
                        </TableBodyCell>
                        <TableBodyCell class="align-top whitespace-nowrap">
                            {getDisplayVenue(registration)}
                        </TableBodyCell>
                        <TableBodyCell class="align-top whitespace-nowrap">
                            {getDisplayOrganizers(registration)}
                        </TableBodyCell>
                        <TableBodyCell class="align-top whitespace-nowrap">
                            <span class="font-bold {getPaymentStatusColor(registration.payment_status)}">{getPaymentStatusText(registration.payment_status)}</span>
                        </TableBodyCell>
                        <TableBodyCell class="align-top whitespace-nowrap">
                            <div class="flex flex-row gap-1">
                                <Button size="xs" color="primary" href="/event/{registration.event_id}/registration">{m.common_viewDetails()}</Button>
                                <Button size="xs" color="light" disabled={!hasEventEnded(registration.end_date) || !registration.is_attended} onclick={() => generateCertificate(registration)}>{m.paymentHistory_printCertificate()}</Button>
                            </div>
                        </TableBodyCell>
                    </TableBodyRow>
                {/each}
            {/if}
        </TableBody>
    </TableSearch>
    <TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />
</div>
