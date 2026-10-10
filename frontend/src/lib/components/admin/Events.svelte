<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Toggle } from '$lib/components/ui';
    import { Modal, Button, Alert, Spinner } from '$lib/components/ui';
    import { Archive, CircleCheck, Settings } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { getDisplayVenue, getDisplayVenueAddress } from '$lib/utils.js';
    import { PagedList } from '$lib/pagedList.svelte.js';

    import TablePagination from '$lib/components/TablePagination.svelte';
    import EventAdminForm from '$lib/components/event_admin/EventAdminForm.svelte';
    import MultiUserSelector from '$lib/components/MultiUserSelector.svelte';

    let { data } = $props();

    let selected_event = $state(null);
    let archive_error = $state('');
    let archive_modal = $state(false);

    // Searched and paged on the server; the field names are the backend's
    // (EVENT_SEARCH_FIELDS).
    const search_fields = [
        { value: 'name', name: m.search_name() },
        { value: 'venue', name: m.search_venue() },
        { value: 'id', name: m.search_id() },
    ];
    let show_archived = $state(false);

    const list = new PagedList('/api/admin/events', { pageSize: 10 });
    // Reloads after archive/create, whose update() re-runs the page load.
    list.track(() => data);

    // Archived events are left out by the server unless asked for. Read the
    // box itself: the change handler may run before bind:checked updates.
    const toggleArchived = (e) => list.setFilter('archived', e.currentTarget.checked ? true : '');

    const afterArchive = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update();
                archive_modal = false;
                archive_error = '';
            } else {
                archive_error = apiMessage(result.error);
            }
        }
    };
    const archiveEvent = (event) => {
        selected_event = event;
        archive_modal = true;
    };

    let create_modal = $state(false);
    let create_error = $state('');
    let newEventData = $state({
        name: '',
        description: '',
        category: 'conference',
        venue: '',
        venue_ko: '',
        venue_address: '',
        venue_address_ko: '',
        venue_latitude: null,
        venue_longitude: null,
        main_languages: ['en'],
        start_date: '',
        end_date: '',
        registration_deadline: '',
        capacity: 0,
        accepts_abstract: false,
        abstract_submission_type: 'internal',
        external_abstract_url: '',
        abstract_deadline: '',
        capacity_abstract: 0,
        max_votes: 2,
    });

    // Organizers selection
    let selectedOrganizerIds = $state([]);
    // The picked accounts themselves, kept here rather than in the picker:
    // the modal unmounts it on close, and a selection kept for reopening
    // must still show who is in it.
    let pickedOrganizers = $state({});

    const afterCreate = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update();
                create_modal = false;
                create_error = '';
                newEventData = {
                    name: '',
                    description: '',
                    category: 'conference',
                    venue: '',
                    venue_ko: '',
                    venue_address: '',
                    venue_address_ko: '',
                    venue_latitude: null,
                    venue_longitude: null,
                    main_languages: ['en'],
                    start_date: '',
                    end_date: '',
                    registration_deadline: '',
                    capacity: 0,
                    accepts_abstract: false,
                    abstract_submission_type: 'internal',
                    external_abstract_url: '',
                    abstract_deadline: '',
                    capacity_abstract: 0,
                    max_votes: 2,
                };
                selectedOrganizerIds = [];
            } else {
                create_error = apiMessage(result.error);
            }
        }
    };

    function handleCreateSubmit(event) {
        if (!newEventData.main_languages || newEventData.main_languages.length === 0) {
            event.preventDefault();
            create_error = m.eventForm_mainLanguagesRequired();
            const errorElement = document.querySelector('#create_modal .text-red-600');
            if (errorElement) {
                errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return false;
        }
        if (selectedOrganizerIds.length === 0) {
            event.preventDefault();
            create_error = m.organizers_required();
            return false;
        }
        create_error = '';
    }
</script>

<h2 class="text-2xl font-bold mb-6">{m.admin_manageEvents_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_manageEvents_description()}</p>

<div class="flex justify-between items-center mb-6">
    <Toggle bind:checked={show_archived} onchange={toggleArchived}>{m.admin_showArchived()}</Toggle>
    <Button color="primary" onclick={() => create_modal = true}>{m.admin_createEvent()}</Button>
</div>

{#if list.error && list.items.length > 0}
    <Alert color="red" class="mb-3">{m.common_error()}</Alert>
{/if}
<TableSearch placeholder={m.admin_searchEvents()} bind:inputValue={list.search} bind:field={list.field} fields={search_fields} hoverable={true}>
    <TableHead>
        <TableHeadCell>{m.admin_tableId()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableName()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableVenue()}</TableHeadCell>
        <TableHeadCell class="text-center">{m.admin_tableArchived()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.admin_tableActions()}</TableHeadCell>
    </TableHead>
    <TableBody>
        {#each list.items as event (event.id)}
            <TableBodyRow class={event.is_archived ? 'bg-gray-100' : ''}>
                <TableBodyCell>{event.id}</TableBodyCell>
                <TableBodyCell>
                    <a href={`/event/${event.id}`} class={event.is_archived ? 'text-gray-500' : ''}>{event.name}</a>
                </TableBodyCell>
                <TableBodyCell>
                    <div class={event.is_archived ? 'text-gray-500' : ''}>
                        <div class="font-medium">{getDisplayVenue(event)}</div>
                        {#if getDisplayVenueAddress(event)}
                            <div class="text-sm text-gray-600">{getDisplayVenueAddress(event)}</div>
                        {/if}
                    </div>
                </TableBodyCell>
                <TableBodyCell class="text-center">
                    {#if event.is_archived}
                        <CircleCheck class="w-5 h-5 text-gray-500 inline-block" />
                    {/if}
                </TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <Button color="none" size="none" href={`/event/${event.id}/admin`}>
                            <Settings class="w-5 h-5" />
                        </Button>
                        <Button color="none" size="none" onclick={() => archiveEvent(event)}>
                            <Archive class="w-5 h-5" />
                        </Button>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if list.items.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="5" class="text-center">
                    {#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.admin_noEventsFound()}{/if}
                </TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={(p) => list.goto(p)} />

<Modal id="archive_modal" size="sm" title={selected_event?.is_archived ? m.admin_unarchiveEventTitle() : m.admin_archiveEventTitle()} bind:open={archive_modal} outsideclose>
    <form method="post" action="?/archive_event" use:enhance={afterArchive}>
        <input type="hidden" name="id" value={selected_event?selected_event.id:''} />
        <p class="mb-6">{selected_event?.is_archived ? m.admin_unarchiveEventConfirm() : m.admin_archiveEventConfirm()}</p>
        {#if archive_error}
            <Alert color="red" class="mb-6">{archive_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color={selected_event?.is_archived ? 'green' : 'yellow'} type="submit">
                {selected_event?.is_archived ? m.admin_unarchive() : m.admin_archive()}
            </Button>
            <Button color="dark" type="button" onclick={() => archive_modal = false}>{m.common_cancel()}</Button>
        </div>
    </form>
</Modal>

<Modal id="create_modal" size="xl" title={m.admin_createEventTitle()} bind:open={create_modal} outsideclose>
    <form method="post" action="?/create_event" use:enhance={afterCreate} onsubmit={handleCreateSubmit}>
        <EventAdminForm bind:data={newEventData} />

        <!-- Organizers Selection -->
        <MultiUserSelector
            url="/api/admin/users"
            bind:selectedIds={selectedOrganizerIds}
            bind:pickedUsers={pickedOrganizers}
            label={m.organizers_title()}
            description={m.organizers_description()}
            required={true}
        />

        <input type="hidden" name="organizer_ids" value={JSON.stringify(selectedOrganizerIds)} />

        {#if create_error}
            <Alert color="red" class="mb-6">{create_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="primary" type="submit">{m.admin_create()}</Button>
            <Button color="alternative" type="button" onclick={() => create_modal = false}>{m.common_cancel()}</Button>
        </div>
    </form>
</Modal>
