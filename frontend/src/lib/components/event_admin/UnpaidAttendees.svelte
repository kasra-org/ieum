<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Button, Modal, Alert, Dropdown, DropdownItem } from '$lib/components/ui';
    import { ChevronDown, UserMinus, UserPen } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';
    import RegistrationForm from '$lib/components/RegistrationForm.svelte';

    let { data } = $props();

    // Registrations still awaiting payment. Free events never produce these, so
    // the tab has nothing to show for them.
    let unpaid = $derived(
        (data.attendees ?? [])
            .filter(a => a.payment_status === 'pending')
            .map(a => ({
                id: a.id,
                nametag_id: a.attendee_nametag_id,
                name: getDisplayName(a),
                email: a.user?.email || a.user_email || '',
                institute: getDisplayInstitute(a),
                registered_at: a.registered_at,
                // Fields the edit form binds to
                first_name: a.first_name,
                middle_initial: a.middle_initial,
                last_name: a.last_name,
                korean_name: a.korean_name,
                nationality: a.nationality?.toString() ?? '1',
                institute_en: a.institute,
                institute_ko: a.institute_ko,
                department: a.department,
                job_title: a.job_title,
                disability: a.disability,
                dietary: a.dietary,
            }))
            .sort((x, y) => (x.registered_at || '').localeCompare(y.registered_at || ''))
    );

    let searchTerm = $state('');
    let currentPage = $state(1);
    const itemsPerPage = 10;

    let filtered = $derived(
        unpaid.filter(a => {
            const q = searchTerm.toLowerCase();
            return a.name.toLowerCase().includes(q) || a.email.toLowerCase().includes(q);
        })
    );

    $effect(() => {
        searchTerm;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filtered.length / itemsPerPage));
    let paginated = $derived(filtered.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage));

    let selected = $state([]);
    // Ignore selections that are no longer unpaid rather than pruning `selected`
    // in an effect: writing to the same state the effect reads re-triggers it,
    // which overflowed the update depth.
    let activeSelection = $derived(selected.filter(id => unpaid.some(a => a.id === id)));

    const allOnPageSelected = $derived(
        paginated.length > 0 && paginated.every(a => selected.includes(a.id))
    );

    function toggleAllOnPage() {
        const ids = paginated.map(a => a.id);
        selected = allOnPageSelected
            ? selected.filter(id => !ids.includes(id))
            : [...new Set([...selected, ...ids])];
    }

    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return d.toLocaleDateString(languageTag() === 'ko' ? 'ko-KR' : 'en-US');
    }

    function formatFee(fee) {
        if (!fee) return '';
        const amount = fee.toLocaleString('ko-KR');
        return languageTag() === 'ko' ? `${amount} 원` : `KRW ${amount}`;
    }

    let send_email_modal = $state(false);
    let send_email_to_all = $state(false);
    const showEmailModal = (toAll) => {
        send_email_to_all = toAll;
        send_email_modal = true;
    };
    let emailRecipients = $derived(
        (send_email_to_all ? unpaid : unpaid.filter(a => activeSelection.includes(a.id)))
            .map(a => a.email).filter(Boolean).join('; ')
    );

    // Editing reuses the same form and action as the attendee roster, so a
    // registration can be corrected before payment without leaving this tab.
    const form_config = { hide_login_info: true, show_english_name: true, show_korean_name: true };
    let edit_modal = $state(false);
    let edit_target = $state(null);
    let edit_message = $state({ type: '', message: '' });
    const showEditModal = (row) => {
        edit_target = row;
        edit_message = { type: '', message: '' };
        edit_modal = true;
    };
    let edit_institution_resolved = $derived(edit_target
        ? { name_en: edit_target.institute_en, name_ko: edit_target.institute_ko }
        : null);
    const afterEdit = () => {
        return async ({ result, update }) => {
            if (result.type === 'success') {
                await update({ reset: false });
                edit_modal = false;
            } else {
                edit_message = { type: 'error', message: result.error?.message || 'An error occurred' };
            }
        };
    };

    let deregister_modal = $state(false);
    let deregister_target = $state(null);
    let deregister_error = $state('');
    const showDeregisterModal = (row) => {
        deregister_target = row;
        deregister_error = '';
        deregister_modal = true;
    };
    const afterDeregister = () => {
        return async ({ result, update }) => {
            if (result.type === 'success') {
                await update({ reset: false });
                deregister_modal = false;
                deregister_error = '';
            } else {
                deregister_error = result.error?.message || 'An error occurred';
            }
        };
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.unpaidAttendees_title()}</Heading>
<p class="font-light mb-6">{m.unpaidAttendees_description()}</p>

{#if !data.event.registration_fee || data.event.registration_fee <= 0}
    <Alert color="blue">{m.unpaidAttendees_freeEvent()}</Alert>
{:else}
    <div class="flex flex-wrap justify-end gap-2 mb-4">
        <Button color="primary" size="sm">{m.unpaidAttendees_emailActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
        <Dropdown class="w-auto list-none p-1">
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showEmailModal(true)} disabled={unpaid.length === 0}>
                {m.unpaidAttendees_emailAll()}
            </DropdownItem>
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showEmailModal(false)} disabled={activeSelection.length === 0}>
                {m.unpaidAttendees_emailSelected()}
            </DropdownItem>
        </Dropdown>
    </div>

    <TableSearch placeholder={m.unpaidAttendees_searchPlaceholder()} hoverable={true} bind:inputValue={searchTerm}>
        <TableHead>
            <TableHeadCell class="w-1">
                <input type="checkbox" checked={allOnPageSelected} onchange={toggleAllOnPage}
                    class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
            </TableHeadCell>
            <TableHeadCell class="w-1">{m.unpaidAttendees_id()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_name()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_email()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_institute()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_registeredAt()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_amountDue()}</TableHeadCell>
            <TableHeadCell class="w-1">{m.unpaidAttendees_actions()}</TableHeadCell>
        </TableHead>
        <TableBody tableBodyClass="divide-y">
            {#each paginated as row}
                <TableBodyRow>
                    <TableBodyCell>
                        <input
                            type="checkbox"
                            checked={selected.includes(row.id)}
                            onchange={() => selected = selected.includes(row.id)
                                ? selected.filter(i => i !== row.id)
                                : [...selected, row.id]}
                            class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                    </TableBodyCell>
                    <TableBodyCell>{row.nametag_id}</TableBodyCell>
                    <TableBodyCell>{row.name}</TableBodyCell>
                    <TableBodyCell>{row.email}</TableBodyCell>
                    <TableBodyCell>{row.institute}</TableBodyCell>
                    <TableBodyCell>{formatDate(row.registered_at)}</TableBodyCell>
                    <TableBodyCell>{formatFee(data.event.registration_fee)}</TableBodyCell>
                    <TableBodyCell>
                        <div class="flex justify-center gap-2">
                            <ActionTooltip text={m.unpaidAttendees_edit()}>
                                <Button color="none" size="none" onclick={() => showEditModal(row)}>
                                    <UserPen class="w-5 h-5" />
                                </Button>
                            </ActionTooltip>
                            <ActionTooltip text={m.unpaidAttendees_deregister()}>
                                <Button color="none" size="none" onclick={() => showDeregisterModal(row)}>
                                    <UserMinus class="w-5 h-5" />
                                </Button>
                            </ActionTooltip>
                        </div>
                    </TableBodyCell>
                </TableBodyRow>
            {/each}
            {#if filtered.length === 0}
                <TableBodyRow>
                    <TableBodyCell colspan="8" class="text-center">{m.unpaidAttendees_noRecords()}</TableBodyCell>
                </TableBodyRow>
            {/if}
        </TableBody>
    </TableSearch>

    <TablePagination {currentPage} {totalPages} onPageChange={(p) => currentPage = p} />
    <p class="mt-5 mb-3 text-sm text-right">{m.unpaidAttendees_count({ count: unpaid.length })}</p>
{/if}

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />

<Modal id="unpaid_edit_modal" size="xl" title={m.unpaidAttendees_edit()} bind:open={edit_modal} outsideclose>
    {#if edit_target}
        <form method="post" action="?/update_attendee" use:enhance={afterEdit}>
            <input type="hidden" name="id" value={edit_target.id} />
            <RegistrationForm data={edit_target} config={form_config} institution_resolved={edit_institution_resolved} />
            {#if edit_message.type === 'error'}
                <Alert color="red" class="mt-4">{edit_message.message}</Alert>
            {/if}
            <div class="flex justify-center mt-6">
                <Button color="primary" type="submit">{m.unpaidAttendees_save()}</Button>
            </div>
        </form>
    {/if}
</Modal>

<Modal bind:open={deregister_modal} title={m.unpaidAttendees_deregister()} size="sm">
    <form method="POST" action="?/deregister_attendee" use:enhance={afterDeregister}>
        <input type="hidden" name="id" value={deregister_target?.id ?? ''} />
        <p class="mb-6">{m.unpaidAttendees_deregisterConfirm({ name: deregister_target?.name ?? '' })}</p>
        {#if deregister_error}
            <Alert color="red" class="mb-6">{deregister_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.unpaidAttendees_deregister()}</Button>
            <Button color="dark" type="button" onclick={() => deregister_modal = false}>{m.unpaidAttendees_cancel()}</Button>
        </div>
    </form>
</Modal>
