<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Modal, Button, Alert, Spinner } from '$lib/components/ui';
    import { Settings, Trash2 } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { PagedList } from '$lib/pagedList.svelte.js';
    import TablePagination from '$lib/components/TablePagination.svelte';

    let { data } = $props();

    // Searched and paged on the server. The page load used to stop at the
    // first 100; every institution is reachable now.
    const list = new PagedList('/api/admin/institutions', { pageSize: 20 });
    const institution_search_fields = [
        { value: 'name_en', name: m.search_nameEn() },
        { value: 'name_ko', name: m.search_nameKo() },
    ];
    // Add/edit/delete re-run the page load; reload this page with it.
    list.track(() => data);

    let selected_institution = $state(null);
    let institution_modal = $state(false);
    let institution_delete_modal = $state(false);
    let institution_error = $state('');

    const openInstitutionModal = (institution = null) => {
        selected_institution = institution;
        institution_modal = true;
        institution_error = '';
    };

    const deleteInstitution = (institution) => {
        selected_institution = institution;
        institution_delete_modal = true;
        institution_error = '';
    };

    const afterInstitutionAction = () => {
        return async ({ result, update }) => {
            if (result.type === "success" && result.data?.success !== false) {
                await update();
                institution_modal = false;
                institution_delete_modal = false;
                institution_error = '';
                selected_institution = null;
            } else {
                institution_error = apiMessage(result.data?.code ? result.data : result.error);
            }
        }
    };
</script>

<div class="flex justify-between items-center mb-2">
    <h2 class="text-2xl font-bold">{m.admin_manageInstitutions_title()}</h2>
    <Button color="primary" onclick={() => openInstitutionModal(null)}>{m.admin_addInstitution()}</Button>
</div>
<p class="text-gray-600 mb-6">{m.admin_manageInstitutions_description()}</p>

{#if list.error && list.items.length > 0}
    <Alert color="red" class="mb-3">{m.common_error()}</Alert>
{/if}
<TableSearch placeholder={m.admin_searchInstitutions()} bind:inputValue={list.search} bind:field={list.field} fields={institution_search_fields} hoverable={true}>
    <TableHead>
        <TableHeadCell>{m.admin_tableId()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableInstitutionNameEn()}</TableHeadCell>
        <TableHeadCell>{m.admin_tableInstitutionNameKo()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.admin_tableActions()}</TableHeadCell>
    </TableHead>
    <TableBody>
        {#each list.items as institution (institution.id)}
            <TableBodyRow>
                <TableBodyCell>{institution.id}</TableBodyCell>
                <TableBodyCell>{institution.name_en}</TableBodyCell>
                <TableBodyCell>{institution.name_ko || '-'}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <Button color="none" size="none" onclick={() => openInstitutionModal(institution)}>
                            <Settings class="w-5 h-5" />
                        </Button>
                        <Button color="none" size="none" onclick={() => deleteInstitution(institution)}>
                            <Trash2 class="w-5 h-5" />
                        </Button>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if list.items.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="4" class="text-center">
                    {#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.admin_noInstitutionsFound()}{/if}
                </TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={(p) => list.goto(p)} />

<Modal id="institution_modal" size="md" title={selected_institution ? m.admin_editInstitution() : m.admin_addInstitution()} bind:open={institution_modal} outsideclose>
    <form method="post" action={selected_institution ? '?/update_institution' : '?/create_institution'} use:enhance={afterInstitutionAction}>
        {#if selected_institution}
            <input type="hidden" name="id" value={selected_institution.id} />
        {/if}
        <div class="mb-4">
            <label for="name_en" class="block mb-2 text-sm font-medium">{m.admin_institutionNameEn()}*</label>
            <input type="text" id="name_en" name="name_en" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" value={selected_institution?.name_en || ''} required />
        </div>
        <div class="mb-6">
            <label for="name_ko" class="block mb-2 text-sm font-medium">{m.admin_institutionNameKo()}</label>
            <input type="text" id="name_ko" name="name_ko" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" value={selected_institution?.name_ko || ''} />
        </div>
        {#if institution_error}
            <Alert color="red" class="mb-6">{institution_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="primary" type="submit">{selected_institution ? m.admin_update() : m.admin_create()}</Button>
            <Button color="alternative" type="button" onclick={() => institution_modal = false}>{m.common_cancel()}</Button>
        </div>
    </form>
</Modal>

<Modal id="institution_delete_modal" size="sm" title={m.admin_removeInstitutionTitle()} bind:open={institution_delete_modal} outsideclose>
    <form method="post" action="?/delete_institution" use:enhance={afterInstitutionAction}>
        <input type="hidden" name="id" value={selected_institution?.id || ''} />
        <p class="mb-6">{m.admin_removeInstitutionConfirm()}</p>
        {#if institution_error}
            <Alert color="red" class="mb-6">{institution_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.admin_remove()}</Button>
            <Button color="dark" type="button" onclick={() => institution_delete_modal = false}>{m.common_cancel()}</Button>
        </div>
    </form>
</Modal>
