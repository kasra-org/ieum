<script>
    let { data: page_data } = $props();
    import { TableSearch, TableBody, TableBodyCell, TableBodyRow, TableHead, TableHeadCell, Button } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ChangeRequestModal from '$lib/components/ChangeRequestModal.svelte';
    import { getDisplayVenue, getDisplayOrganizers, formatDate, formatDateRange } from '$lib/utils.js';
    import ReceiptButtons from '$lib/components/ReceiptButtons.svelte';
    import SortableHeadCell from '$lib/components/SortableHeadCell.svelte';
    import { sortRows } from '$lib/tableSort.js';

    function formatAmount(amount) {
        const formattedAmount = amount.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
        return languageTag() === 'ko' ? `${formattedAmount}원` : `KRW ${formattedAmount}`;
    }

    function getStatusText(status) {
        switch (status) {
            case 'completed':
                return m.paymentHistory_statusCompleted();
            case 'cancelled':
                return m.paymentHistory_statusCancelled();
            case 'pending':
                return m.paymentHistory_statusPending();
            default:
                return status;
        }
    }

    let payments = $derived(page_data.payments || []);

    // Search and pagination state
    let searchTerm = $state('');
    let currentPage = $state(1);
    const itemsPerPage = 5;

    // Change request modal state
    let showChangeRequestModal = $state(false);
    let selectedEventId = $state(null);

    function openChangeRequestModal(eventId) {
        selectedEventId = eventId;
        showChangeRequestModal = true;
    }

    // Filter payments based on search term
    let filteredPayments = $derived(
        payments.filter((item) =>
            item.event_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            item.organizers_en.toLowerCase().includes(searchTerm.toLowerCase()) ||
            item.organizers_ko.toLowerCase().includes(searchTerm.toLowerCase()) ||
            item.number.toString().includes(searchTerm)
        )
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTerm;
        currentPage = 1;
    });

    // Column sorting (see $lib/tableSort.js), by what each column shows.
    const paymentsColumn = {
        date: r => r.checkout_date,
        event: r => r.event_name,
        organizers: r => getDisplayOrganizers(r),
        status: r => getStatusText(r.status),
    };
    let sortPayments = $state([]);
    const sortPaymentsBy = (sort) => { sortPayments = sort; currentPage = 1; };
    let sortedPayments = $derived(sortRows(filteredPayments, sortPayments, (r, key) => paymentsColumn[key](r)));

    let totalPages = $derived(Math.ceil(filteredPayments.length / itemsPerPage));
    let paginatedPayments = $derived(
        sortedPayments.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }
</script>

<svelte:head>
    <title>{m.paymentHistory_title()} | {page_data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.paymentHistory_title()}</h1>
        <p class="text-slate-200 mt-2">{m.paymentHistory_description()}</p>
    </div>
</div>

<!-- Table Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <TableSearch placeholder={m.paymentHistory_searchPlaceholder()} hoverable={true} striped={true} bind:inputValue={searchTerm}>
        <TableHead>
<SortableHeadCell key="date" sort={sortPayments} onsort={sortPaymentsBy}>{m.paymentHistory_checkoutDate()}</SortableHeadCell>
            <SortableHeadCell key="event" sort={sortPayments} onsort={sortPaymentsBy}>{m.paymentHistory_eventName()}</SortableHeadCell>
            <SortableHeadCell key="organizers" sort={sortPayments} onsort={sortPaymentsBy}>{m.paymentHistory_organizers()}</SortableHeadCell>
            <SortableHeadCell key="status" sort={sortPayments} onsort={sortPaymentsBy}>{m.paymentHistory_status()}</SortableHeadCell>
        </TableHead>
        <TableBody>
            {#if filteredPayments.length === 0}
                <TableBodyRow>
                    <TableBodyCell colspan="4" class="text-center text-gray-500 py-8">
                        {m.paymentHistory_noRecords()}
                    </TableBodyCell>
                </TableBodyRow>
            {:else}
                {#each paginatedPayments as payment}
                    <TableBodyRow>
                        <TableBodyCell class="align-top">
                            <div class="font-medium">{formatDate(payment.checkout_date)}</div>
                            <div class="text-sm text-gray-500">{payment.number}</div>
                            <hr class="my-2 border-gray-200" />
                            <div class="text-sm">{m.paymentHistory_amount()}: {formatAmount(payment.amount)}</div>
                            <div class="mt-2 flex flex-col gap-1">
                                <ReceiptButtons {payment} />
                            </div>
                        </TableBodyCell>
                        <TableBodyCell class="align-top">
                            <a href="/event/{payment.event_id}" class="font-medium text-gray-900 underline">{payment.event_name}</a>
                            <div class="text-sm text-gray-500 mt-1">{formatDateRange(payment.start_date, payment.end_date)}</div>
                            <div class="text-sm text-gray-500">{getDisplayVenue(payment)}</div>
                        </TableBodyCell>
                        <TableBodyCell class="align-top">
                            {getDisplayOrganizers(payment)}
                        </TableBodyCell>
                        <TableBodyCell class="align-top">
                            <span class="font-bold text-orange-500">{getStatusText(payment.status)}</span>
                            <div class="mt-2 flex flex-col gap-1">
                                <Button size="xs" color="primary" disabled={payment.status === 'cancelled'} href={payment.status !== 'cancelled' ? `/event/${payment.event_id}/registration#payment_info` : undefined}>{m.common_viewDetails()}</Button>
                                <Button size="xs" color="light" disabled={payment.status === 'cancelled'} onclick={() => openChangeRequestModal(payment.event_id)}>{m.paymentHistory_requestCancellation()}</Button>
                            </div>
                        </TableBodyCell>
                    </TableBodyRow>
                {/each}
            {/if}
        </TableBody>
    </TableSearch>
    <TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />
</div>

<ChangeRequestModal bind:open={showChangeRequestModal} eventId={selectedEventId} />
