<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Button, Modal, Alert, Checkbox, Dropdown, DropdownItem, Label, Select, Input } from '$lib/components/ui';
    import { ChevronDown, UserMinus, UserPen } from '@lucide/svelte';
    import { enhance, deserialize } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { getDisplayInstitute, getDisplayName, getCategoryLabel, matchesSearch } from '$lib/utils.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';
    import RegistrationForm from '$lib/components/RegistrationForm.svelte';
    import SearchableUserList from '$lib/components/SearchableUserList.svelte';

    let { data } = $props();

    // Registrations still awaiting payment. Waiving one settles it at 0 KRW, so
    // it leaves this tab for the roster at once; undoing a waiver is just
    // removing that registration from there. Free events never produce these,
    // so the tab has nothing to show for them.
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
                category: a.category,
                registration_fee: a.registration_fee,
                fee_waived: a.fee_waived,
                category_name: a.category_name,
                category_name_ko: a.category_name_ko,
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

    let searchField = $state('all');
    const searchFields = [
        { value: 'name', name: m.search_name(), get: r => [r.name, r.korean_name] },
        { value: 'email', name: m.search_email(), get: r => r.email },
        { value: 'institute', name: m.search_institute(), get: r => [r.institute_en, r.institute_ko] },
        { value: 'category', name: m.search_category(), get: r => [r.category_name, r.category_name_ko] },
        { value: 'id', name: m.search_id(), get: r => r.nametag_id },
    ];

    let filtered = $derived(unpaid.filter(a => matchesSearch(a, searchTerm, searchField, searchFields)));

    $effect(() => {
        searchTerm;
        searchField;
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

    // event.registration_fee is the cheapest category, so it says nothing about
    // whether the event charges: a free category alongside paid ones would have
    // hidden every unpaid attendee behind the "free event" notice.
    const eventCharges = $derived(
        (data.event.registration_categories ?? []).some(c => (c.fee || 0) > 0)
    );

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

    // Posting the row unchanged except for the waiver, the way the speaker list
    // toggles its exemption.
    let exemption_form = $state(null);
    let toggling_attendee = $state(null);
    const toggleExemption = (row) => {
        toggling_attendee = { ...row, fee_waived: !row.fee_waived };
        // Wait for the hidden inputs to take the new values before submitting.
        queueMicrotask(() => exemption_form?.requestSubmit());
    };

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
    // Everything on offer, plus the row's own category if it has since been
    // retired, so the select does not silently move the person elsewhere.
    let edit_category_options = $derived.by(() => {
        const lang = languageTag();
        const items = (data.event.registration_categories ?? []).map(c => ({ value: c.id, name: getCategoryLabel(c, lang) }));
        if (edit_target?.category && !items.some(i => i.value === edit_target.category)) {
            items.unshift({ value: edit_target.category, name: getCategoryLabel(edit_target, lang) });
        }
        if (!edit_target?.category) items.unshift({ value: '', name: '—' });
        return items;
    });
    let edit_institution_resolved = $derived(edit_target
        ? { name_en: edit_target.institute_en, name_ko: edit_target.institute_ko }
        : null);
    const afterEdit = () => {
        return async ({ result, update }) => {
            if (result.type === 'success') {
                await update({ reset: false });
                edit_modal = false;
            } else {
                edit_message = { type: 'error', message: apiMessage(result.error) };
            }
        };
    };

    // Registering an existing account by hand - someone who signed up on the
    // site but registered by phone or email; they then pay online.
    //
    // Staff pick from every account, as in the other people pickers here,
    // which likewise get the site's account list only for staff. A non-staff
    // event admin never sees that list anywhere on this page, so for them the
    // account is found by its exact address instead.
    const canBrowseAccounts = $derived(Array.isArray(data.users));
    const registeredUserIds = $derived(new Set((data.attendees ?? []).map(a => a.user?.id).filter(Boolean)));
    const registerableAccounts = $derived(
        canBrowseAccounts ? data.users.filter(u => !registeredUserIds.has(u.id)) : []
    );
    let register_user_id = $state(null);    // picked from the list (staff)
    let register_modal = $state(false);
    let register_email = $state('');
    let register_found = $state(null);      // the account the address belongs to (non-staff)
    let register_category = $state('');
    let register_send_confirmation = $state(false);
    let register_error = $state('');
    let register_busy = $state(false);
    const registerCategories = $derived(data.event.registration_categories ?? []);
    const chosenCategory = $derived(registerCategories.find(c => String(c.id) === String(register_category)));
    const showRegisterModal = () => {
        register_user_id = null;
        register_email = '';
        register_found = null;
        register_category = String(registerCategories.find(c => (c.fee || 0) > 0)?.id ?? registerCategories[0]?.id ?? '');
        register_send_confirmation = false;
        register_error = '';
        register_modal = true;
    };
    async function lookupAccount() {
        register_error = '';
        register_found = null;
        const email = register_email.trim();
        if (!email) return;
        register_busy = true;
        try {
            const body = new FormData();
            body.append('email', email);
            const result = deserialize(await (await fetch('?/lookup_user', { method: 'POST', body })).text());
            if (result.type === 'success' && result.data?.found) {
                register_found = result.data.user;
                if (register_found.already_registered) register_error = m.unpaidAttendees_registerAlready();
            } else if (result.type === 'success') {
                register_error = m.unpaidAttendees_registerNoAccount();
            } else {
                register_error = apiMessage(result.error, m.unpaidAttendees_registerError);
            }
        } finally {
            register_busy = false;
        }
    }
    // A different address means a different person: drop the old result.
    $effect(() => {
        register_email;
        register_found = null;
    });
    // Whichever way the account was found, the server registers it by address.
    const registerTarget = $derived(canBrowseAccounts
        ? registerableAccounts.find(u => u.id === register_user_id) ?? null
        : (register_found && !register_found.already_registered ? register_found : null));
    const canRegister = $derived(!!registerTarget && !!register_category && !register_busy);
    const afterRegister = () => {
        register_busy = true;
        return async ({ result, update }) => {
            register_busy = false;
            if (result.type === 'success') {
                await update({ reset: false });
                register_modal = false;
            } else {
                register_error = apiMessage(result.error, m.unpaidAttendees_registerError);
            }
        };
    };
    function formatCategory(c) {
        const label = getCategoryLabel(c, languageTag());
        return (c.fee || 0) > 0 ? `${label} (${formatFee(c.fee)})` : `${label} (${m.unpaidAttendees_registerFree()})`;
    }

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
                deregister_error = apiMessage(result.error);
            }
        };
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.unpaidAttendees_title()}</Heading>
<p class="font-light mb-6">{m.unpaidAttendees_description()}</p>

{#if !eventCharges}
    <Alert color="blue">{m.unpaidAttendees_freeEvent()}</Alert>
{:else}
    <div class="flex flex-wrap justify-end gap-2 mb-4">
        <Button color="primary" size="sm" onclick={showRegisterModal}>{m.unpaidAttendees_register()}</Button>
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

    <TableSearch placeholder={m.unpaidAttendees_searchPlaceholder()} hoverable={true} bind:inputValue={searchTerm} bind:field={searchField} fields={searchFields}>
        <TableHead>
            <TableHeadCell class="w-1">
                <input type="checkbox" checked={allOnPageSelected} onchange={toggleAllOnPage}
                    class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
            </TableHeadCell>
            <TableHeadCell class="w-1">{m.unpaidAttendees_id()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_name()}</TableHeadCell>
            <TableHeadCell>{m.attendees_tier()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_email()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_institute()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_registeredAt()}</TableHeadCell>
            <TableHeadCell>{m.unpaidAttendees_amountDue()}</TableHeadCell>
            <TableHeadCell class="w-1">{m.unpaidAttendees_feeExempt()}</TableHeadCell>
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
                    <TableBodyCell>{getCategoryLabel(row, languageTag())}</TableBodyCell>
                    <TableBodyCell>{row.email}</TableBodyCell>
                    <TableBodyCell>{row.institute}</TableBodyCell>
                    <TableBodyCell>{formatDate(row.registered_at)}</TableBodyCell>
                    <TableBodyCell>{formatFee(row.registration_fee)}</TableBodyCell>
                    <TableBodyCell>
                        <ActionTooltip text={m.unpaidAttendees_feeExemptHelp()}>
                            <Checkbox checked={row.fee_waived}
                                onclick={(e) => { e.preventDefault(); toggleExemption(row); }} />
                        </ActionTooltip>
                    </TableBodyCell>
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
                    <TableBodyCell colspan="10" class="text-center">{m.unpaidAttendees_noRecords()}</TableBodyCell>
                </TableBodyRow>
            {/if}
        </TableBody>
    </TableSearch>

    <TablePagination {currentPage} {totalPages} onPageChange={(p) => currentPage = p} />
    <p class="mt-5 mb-3 text-sm text-right">{m.unpaidAttendees_count({ count: unpaid.length })}</p>
{/if}

<Modal id="register_attendee_modal" size="md" title={m.unpaidAttendees_register()} bind:open={register_modal}>
    <form method="post" action="?/register_attendee" use:enhance={afterRegister}>
        <p class="text-sm text-gray-600 mb-6">{m.unpaidAttendees_registerHelp()}</p>
        <input type="hidden" name="email" value={registerTarget?.email ?? ''} />
        {#if canBrowseAccounts}
            <div class="mb-6">
                <SearchableUserList
                    items={registerableAccounts}
                    bind:selectedId={register_user_id}
                    maxHeight="max-h-72"
                    showChangeButton={true}
                />
            </div>
        {:else}
            <div class="mb-4">
                <Label for="register_email" class="block mb-2">{m.unpaidAttendees_registerEmail()}</Label>
                <div class="flex gap-2">
                    <Input id="register_email" type="email" bind:value={register_email}
                        onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); lookupAccount(); } }} />
                    <Button type="button" color="light" class="shrink-0 whitespace-nowrap" onclick={lookupAccount} disabled={!register_email.trim() || register_busy}>{m.unpaidAttendees_registerFind()}</Button>
                </div>
            </div>
            {#if register_found}
                <div class="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
                    <div class="font-medium">{languageTag() === 'ko' && register_found.korean_name ? register_found.korean_name : register_found.name}</div>
                    <div class="text-gray-600">{languageTag() === 'ko' && register_found.institute_ko ? register_found.institute_ko : register_found.institute}</div>
                    <div class="text-gray-500">{register_found.email}</div>
                </div>
            {/if}
        {/if}
        {#if registerTarget}
            <div class="mb-4">
                <Label for="register_category" class="block mb-2">{m.attendees_tier()}</Label>
                <Select id="register_category" name="category" bind:value={register_category}
                    items={registerCategories.map(c => ({ value: String(c.id), name: formatCategory(c) }))} />
                {#if chosenCategory && !((chosenCategory.fee || 0) > 0)}
                    <p class="mt-1 text-xs text-gray-500">{m.unpaidAttendees_registerFreeHint()}</p>
                {/if}
            </div>
            <div class="mb-6">
                <input type="hidden" name="send_confirmation" value={register_send_confirmation ? 'true' : 'false'} />
                <Checkbox bind:checked={register_send_confirmation}>{m.unpaidAttendees_registerSendConfirmation()}</Checkbox>
            </div>
        {/if}
        {#if register_error}
            <Alert color="red" class="mb-6">{register_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="alternative" type="button" onclick={() => register_modal = false}>{m.unpaidAttendees_cancel()}</Button>
            <Button color="primary" type="submit" disabled={!canRegister}>{m.unpaidAttendees_registerSubmit()}</Button>
        </div>
    </form>
</Modal>

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />

<!-- The exemption tick posts through here rather than opening the edit modal. -->
<form method="POST" action="?/toggle_fee_exemption" bind:this={exemption_form} class="hidden"
    use:enhance={() => async ({ result, update }) => {
        if (result.type === 'success') await update({ reset: false });
        toggling_attendee = null;
    }}>
    <input type="hidden" name="id" value={toggling_attendee?.id ?? ''} />
    <input type="hidden" name="fee_waived" value={toggling_attendee?.fee_waived ? 'true' : 'false'} />
</form>

<Modal id="unpaid_edit_modal" size="xl" title={m.unpaidAttendees_edit()} bind:open={edit_modal} outsideclose>
    {#if edit_target}
        <form method="post" action="?/update_attendee" use:enhance={afterEdit}>
            <input type="hidden" name="id" value={edit_target.id} />
            <div class="mb-6">
                <Label for="unpaid_category" class="block mb-2">{m.attendees_tier()}</Label>
                <Select id="unpaid_category" name="category" value={edit_target.category ?? ''} items={edit_category_options} />
            </div>
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
