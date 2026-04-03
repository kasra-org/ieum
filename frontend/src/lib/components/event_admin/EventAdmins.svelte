<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Card } from 'flowbite-svelte';
    import { Button, Modal, Label, Input, Select, Textarea, Alert } from 'flowbite-svelte';
    import { Tabs, TabItem } from 'flowbite-svelte';
    import { UserRemoveSolid, StarSolid, StarOutline } from 'flowbite-svelte-icons';
    import { enhance } from '$app/forms';
    import { error } from '@sveltejs/kit';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import UserSelectionModal from '$lib/components/UserSelectionModal.svelte';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';

    let { data } = $props();

    // Staff users get full user list, event admins get attendees only
    // Filter out attendees whose user has been deleted (they can't be admins without an account)
    const userList = $derived(data.users ? data.users.map(u => ({ id: u.id, ...u })) : data.attendees.filter(a => a.user).map(a => ({ ...a, id: a.user.id })));

    let searchTermEventAdmin = $state('');
    let currentPage = $state(1);
    const itemsPerPage = 10;

    let filteredEventAdmins = $derived(
        data.eventadmins.filter((item) => {
            const searchLower = searchTermEventAdmin.toLowerCase();
            return item.name.toLowerCase().includes(searchLower) ||
                   (item.korean_name && item.korean_name.toLowerCase().includes(searchLower));
        })
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermEventAdmin;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filteredEventAdmins.length / itemsPerPage));
    let paginatedEventAdmins = $derived(
        filteredEventAdmins.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }

    let eventadmin_modal = $state(false);
    let delete_eventadmin_modal = $state(false);
    let selected_eventadmin = $state(null);

    const addEventAdminModal = () => {
        selected_eventadmin = null;
        eventadmin_modal = true;
    };
    const deleteEventAdminModal = (id) => {
        selected_eventadmin = data.eventadmins.find((item) => item.id === id);
        delete_eventadmin_modal = true;
    };

    let add_eventadmin_error = $state('');
    const afterAddEventAdmin = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                eventadmin_modal = false;
                add_eventadmin_error = '';
            } else {
                add_eventadmin_error = m.userSelection_error();
            }
        }
    };

    let delete_eventadmin_error = $state('');
    const afterDeleteEventAdmin = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                delete_eventadmin_modal = false;
                delete_eventadmin_error = '';
            } else {
                delete_eventadmin_error = m.userSelection_error();
            }
        }
    };

    const afterToggleMainAdmin = () => {
        return async ({ result, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
            }
        }
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.eventAdmins_title()}</Heading>
<p class="font-light mb-6">{m.eventAdmins_description()}</p>
<div class="flex justify-end gap-2">
    <Button color="primary" size="sm" onclick={addEventAdminModal}>{m.eventAdmins_addAdmin()}</Button>
</div>
<TableSearch placeholder={m.eventAdmins_searchPlaceholder()} hoverable={true} bind:inputValue={searchTermEventAdmin}>
    <TableHead>
        <TableHeadCell>{m.eventAdmins_name()}</TableHeadCell>
        <TableHeadCell>{m.eventAdmins_email()}</TableHeadCell>
        <TableHeadCell>{m.eventAdmins_institute()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.eventAdmins_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedEventAdmins as row}
            <TableBodyRow>
                <TableBodyCell>{getDisplayName(row)}</TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>{getDisplayInstitute(row)}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.eventAdmins_toggleMainAdmin()}>
                            <form method="POST" action="?/set_main_eventadmin" use:enhance={afterToggleMainAdmin}>
                                <input type="hidden" name="id" value={row.id} />
                                <Button color="none" size="none" type="submit">
                                    {#if data.event.main_admin_id === row.id}
                                        <StarSolid class="w-5 h-5 text-yellow-400" />
                                    {:else}
                                        <StarOutline class="w-5 h-5 text-gray-400 hover:text-yellow-400" />
                                    {/if}
                                </Button>
                            </form>
                        </ActionTooltip>
                        <ActionTooltip text={m.eventAdmins_deleteAdmin()}>
                            <Button color="none" size="none" onclick={() => deleteEventAdminModal(row.id)}>
                                <UserRemoveSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filteredEventAdmins.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="4" class="text-center">{m.eventAdmins_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />

<UserSelectionModal
    bind:open={eventadmin_modal}
    title={m.eventAdmins_addAdminTitle()}
    userList={userList}
    action="?/add_eventadmin"
    submitLabel={m.eventAdmins_add()}
    bind:error={add_eventadmin_error}
    onSubmit={afterAddEventAdmin}
/>

<Modal bind:open={delete_eventadmin_modal} title={m.eventAdmins_deleteAdmin()} size="sm">
    <form method="POST" action="?/delete_eventadmin" use:enhance={afterDeleteEventAdmin}>
        <input type="hidden" name="id" value={selected_eventadmin?selected_eventadmin.id:''} />
        <p class="mb-6">{m.eventAdmins_deleteConfirm()}</p>
        {#if delete_eventadmin_error}
            <Alert color="red" class="mb-6">{delete_eventadmin_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.eventAdmins_delete()}</Button>
            <Button color="dark" type="button" onclick={() => delete_eventadmin_modal = false}>{m.eventAdmins_cancel()}</Button>
        </div>
    </form>
</Modal>
