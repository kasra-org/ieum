<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Input, Card } from 'flowbite-svelte';
    import { Button, Modal, Label, Alert } from 'flowbite-svelte';
    import { UserEditSolid, UserRemoveSolid, ChevronUpOutline, ChevronDownOutline } from 'flowbite-svelte-icons';
    import { enhance, deserialize } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import SearchableUserList from '$lib/components/SearchableUserList.svelte';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';

    let { data } = $props();

    let searchTermOrganizer = $state('');
    let currentPage = $state(1);
    const itemsPerPage = 10;

    let filteredOrganizers = $derived(
        data.organizers.filter((item) => {
            const searchLower = searchTermOrganizer.toLowerCase();
            return item.name.toLowerCase().includes(searchLower) ||
                   (item.korean_name && item.korean_name.toLowerCase().includes(searchLower));
        })
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermOrganizer;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filteredOrganizers.length / itemsPerPage));
    let paginatedOrganizers = $derived(
        filteredOrganizers.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }

    let organizer_modal = $state(false);
    let delete_organizer_modal = $state(false);
    let selected_organizer = $state(null);
    let reordering = $state(false);

    // Form field state for organizer modal
    let organizerName = $state('');
    let organizerKoreanName = $state('');
    let organizerEmail = $state('');
    let organizerAffiliation = $state('');
    let organizerAffiliationKo = $state('');

    // Custom getters for SearchableUserList
    function getAttendeeEmail(attendee) {
        return attendee.user?.email || attendee.user_email || '';
    }

    function getAttendeeSecondaryName(attendee) {
        const lang = languageTag();
        if (lang === 'ko') {
            return attendee.name || '';
        }
        return attendee.korean_name || '';
    }

    function selectAttendeeForOrganizer(attendee) {
        organizerName = attendee.name || '';
        organizerKoreanName = attendee.korean_name || '';
        organizerEmail = attendee.user?.email || attendee.user_email || '';
        organizerAffiliation = attendee.institute || '';
        organizerAffiliationKo = attendee.institute_ko || '';
    }

    const addOrganizerModal = () => {
        selected_organizer = null;
        organizerName = '';
        organizerKoreanName = '';
        organizerEmail = '';
        organizerAffiliation = '';
        organizerAffiliationKo = '';
        organizer_modal = true;
    };
    const modifyOrganizerModal = (id) => {
        selected_organizer = data.organizers.find((item) => item.id === id);
        organizerName = selected_organizer.name;
        organizerKoreanName = selected_organizer.korean_name || '';
        organizerEmail = selected_organizer.email || '';
        organizerAffiliation = selected_organizer.affiliation || '';
        organizerAffiliationKo = selected_organizer.affiliation_ko || '';
        organizer_modal = true;
    };
    const deleteOrganizerModal = (id) => {
        selected_organizer = data.organizers.find((item) => item.id === id);
        delete_organizer_modal = true;
    };

    // Reorder functions
    async function moveOrganizer(index, direction) {
        if (reordering) return;

        const newIndex = index + direction;
        if (newIndex < 0 || newIndex >= data.organizers.length) return;

        reordering = true;

        // Create new order
        const newOrder = [...data.organizers.map(o => o.id)];
        [newOrder[index], newOrder[newIndex]] = [newOrder[newIndex], newOrder[index]];

        try {
            const formData = new FormData();
            formData.append('order', JSON.stringify(newOrder));

            const response = await fetch('?/reorder_organizers', {
                method: 'POST',
                body: formData
            });

            const result = deserialize(await response.text());
            if (result.type === 'success' && result.data?.success !== false) {
                await invalidateAll();
            }
        } catch (error) {
            console.error('Failed to reorder organizers:', error);
        } finally {
            reordering = false;
        }
    }

    let update_organizer_error = $state('');
    const afterUpdateOrganizer = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                organizer_modal = false;
                update_organizer_error = '';
            } else {
                update_organizer_error = result.error.message;
            }
        }
    };

    let delete_organizer_error = $state('');
    const afterDeleteOrganizer = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                delete_organizer_modal = false;
                delete_organizer_error = '';
            } else {
                delete_organizer_error = m.userSelection_error();
            }
        }
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.organizers_title()}</Heading>
<p class="font-light mb-6">{m.organizers_description()}</p>
<div class="flex justify-end gap-2 mb-4">
    <Button color="primary" size="sm" onclick={addOrganizerModal}>{m.organizers_addOrganizer()}</Button>
</div>
<TableSearch placeholder={m.organizers_searchPlaceholder()} hoverable={true} bind:inputValue={searchTermOrganizer}>
    <TableHead>
        <TableHeadCell class="w-1">{m.organizers_order()}</TableHeadCell>
        <TableHeadCell>{m.organizers_name()}</TableHeadCell>
        <TableHeadCell>{m.organizers_email()}</TableHeadCell>
        <TableHeadCell>{m.organizers_institute()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.organizers_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedOrganizers as row, localIndex}
            {@const globalIndex = (currentPage - 1) * itemsPerPage + localIndex}
            <TableBodyRow>
                <TableBodyCell>
                    <div class="flex flex-col gap-0.5">
                        <button
                            onclick={() => moveOrganizer(globalIndex, -1)}
                            disabled={globalIndex === 0 || reordering || searchTermOrganizer}
                            class="p-0.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            <ChevronUpOutline class="w-4 h-4" />
                        </button>
                        <button
                            onclick={() => moveOrganizer(globalIndex, 1)}
                            disabled={globalIndex === data.organizers.length - 1 || reordering || searchTermOrganizer}
                            class="p-0.5 rounded hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                            <ChevronDownOutline class="w-4 h-4" />
                        </button>
                    </div>
                </TableBodyCell>
                <TableBodyCell>{languageTag() === 'ko' ? (row.korean_name || row.name) : row.name}</TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>{languageTag() === 'ko' ? (row.affiliation_ko || row.affiliation) : row.affiliation}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.organizers_updateOrganizer()}>
                            <Button color="none" size="none" onclick={() => modifyOrganizerModal(row.id)}>
                                <UserEditSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.organizers_deleteOrganizer()}>
                            <Button color="none" size="none" onclick={() => deleteOrganizerModal(row.id)}>
                                <UserRemoveSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filteredOrganizers.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="5" class="text-center">{m.organizers_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />

<Modal bind:open={organizer_modal} title={selected_organizer ? m.organizers_updateOrganizer() : m.organizers_addOrganizerTitle()} size="lg">
    <form method="POST" action={selected_organizer?"?/update_organizer":"?/add_organizer"} use:enhance={afterUpdateOrganizer}>
        {#if selected_organizer}
            <input type="hidden" name="id" value={selected_organizer.id} />
        {:else}
            <div class="mb-6">
                <Label class="block mb-2">{m.organizers_selectAttendee()}</Label>
                <SearchableUserList
                    items={data.attendees}
                    maxHeight="max-h-60"
                    showChangeButton={false}
                    getItemSecondaryName={getAttendeeSecondaryName}
                    getItemEmail={getAttendeeEmail}
                    onSelect={selectAttendeeForOrganizer}
                />
            </div>
            <hr class="mb-6 border-gray-200" />
        {/if}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
                <Label for="name" class="block mb-2">{m.organizers_name()} ({m.language_english()}) <span class="text-red-500">*</span></Label>
                <Input id="name" name="name" type="text" bind:value={organizerName} required />
            </div>
            <div>
                <Label for="korean_name" class="block mb-2">{m.organizers_name()} ({m.language_korean()})</Label>
                <Input id="korean_name" name="korean_name" type="text" bind:value={organizerKoreanName} />
            </div>
        </div>
        <div class="mb-6">
            <Label for="email" class="block mb-2">{m.organizers_email()}</Label>
            <Input id="email" name="email" type="email" bind:value={organizerEmail} />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
                <Label for="affiliation" class="block mb-2">{m.organizers_affiliation()} ({m.language_english()})</Label>
                <Input id="affiliation" name="affiliation" type="text" bind:value={organizerAffiliation} />
            </div>
            <div>
                <Label for="affiliation_ko" class="block mb-2">{m.organizers_affiliation()} ({m.language_korean()})</Label>
                <Input id="affiliation_ko" name="affiliation_ko" type="text" bind:value={organizerAffiliationKo} />
            </div>
        </div>
        {#if update_organizer_error}
            <Alert color="red" class="mb-6">{update_organizer_error}</Alert>
        {/if}
        <div class="flex justify-center">
            <Button color="primary" type="submit">{selected_organizer ? m.organizers_update() : m.organizers_add()}</Button>
        </div>
    </form>
</Modal>

<Modal bind:open={delete_organizer_modal} title={m.organizers_deleteOrganizer()} size="sm">
    <form method="POST" action="?/delete_organizer" use:enhance={afterDeleteOrganizer}>
        <input type="hidden" name="id" value={selected_organizer?selected_organizer.id:''} />
        <p class="mb-6">{m.organizers_deleteConfirm()}</p>
        {#if delete_organizer_error}
            <Alert color="red" class="mb-6">{delete_organizer_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.organizers_delete()}</Button>
            <Button color="dark" type="button" onclick={() => delete_organizer_modal = false}>{m.organizers_cancel()}</Button>
        </div>
    </form>
</Modal>
