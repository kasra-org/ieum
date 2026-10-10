<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell } from '$lib/components/ui';
    import { Button, Modal, Alert, Checkbox, Dropdown, DropdownItem, Label, Select, Input, Spinner } from '$lib/components/ui';
    import { ChevronDown, UserMinus, UserPen } from '@lucide/svelte';
    import { enhance, deserialize } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { getDisplayInstitute, getDisplayName, getCategoryLabel, downloadTsv } from '$lib/utils.js';
    import { PagedList } from '$lib/pagedList.svelte.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';
    import RegistrationForm from '$lib/components/RegistrationForm.svelte';
    import RemoteSearchList from '$lib/components/RemoteSearchList.svelte';

    let { data } = $props();

    // Registrations still awaiting payment. Waiving one settles it at 0 KRW, so
    // it leaves this tab for the roster at once; undoing a waiver is just
    // removing that registration from there. Free events never produce these,
    // so the tab has nothing to show for them. The server pages, searches and
    // orders them (oldest registration first); `track` reloads the page after
    // every save, since each one re-runs the page load.
    const list = new PagedList(() => `/api/event/${data.event.id}/attendees`, { filters: { status: 'unpaid' } });
    list.track(() => data);

    const toRow = (a) => ({
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
        custom_answers: a.custom_answers ?? [],
    });
    let paginated = $derived(list.items.map(toRow));

    const searchFields = [
        { value: 'name', name: m.search_name() },
        { value: 'email', name: m.search_email() },
        { value: 'institute', name: m.search_institute() },
        { value: 'category', name: m.search_category() },
        { value: 'id', name: m.search_id() },
    ];

    // Ids, so a selection survives paging and searching. Rows that stop owing
    // money meanwhile (paid online, waived, deregistered) are dropped when the
    // selection is fetched, by asking only for unpaid ones.
    let selected = $state([]);

    const allOnPageSelected = $derived(
        paginated.length > 0 && paginated.every(a => selected.includes(a.id))
    );

    function toggleAllOnPage() {
        const ids = paginated.map(a => a.id);
        selected = allOnPageSelected
            ? selected.filter(id => !ids.includes(id))
            : [...new Set([...selected, ...ids])];
    }

    // The unpaid rows whatever the search box says: "email all" always meant
    // everyone still owing, and a selection is by id. Asked of /export
    // directly because list.exportAll would carry the search along. A
    // selection goes through list.fetchByIds, which batches long id lists.
    async function fetchUnpaid(extra = {}) {
        const response = await fetch(`${list.url}/export?${new URLSearchParams({ status: 'unpaid', ...extra })}`, {
            headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error(`${response.status}`);
        return (await response.json()).map(toRow);
    }

    // Everyone still owing, whatever the search box says - as "email all"
    // reads it - with the same columns as the roster's export: names and
    // institutes in both languages whatever the page is shown in, then the
    // answers to the event's questions.
    let csv_exporting = $state(false);
    let csv_error = $state(false);
    async function exportUnpaidAsCSV() {
        if (csv_exporting) return;
        csv_exporting = true;
        csv_error = false;
        let rows;
        try {
            rows = await fetchUnpaid();
        } catch (e) {
            csv_error = true;
            return;
        } finally {
            csv_exporting = false;
        }
        // Every question the event asks, then any older ones only some
        // answers still carry.
        const questions = [...new Set([
            ...data.questions.map(q => q.question.question),
            ...rows.flatMap(row => row.custom_answers.map(a => a.question)),
        ])];
        const headers = [
            m.unpaidAttendees_id(),
            m.attendees_nameEn(), m.attendees_nameKo(),
            m.unpaidAttendees_email(),
            m.attendees_nationality(),
            m.attendees_instituteEn(), m.attendees_instituteKo(),
            m.attendees_department(),
            m.attendees_jobTitle(),
            m.attendees_disability(),
            m.attendees_dietary(),
            m.attendees_tier(),
            m.unpaidAttendees_registeredAt(),
            m.unpaidAttendees_amountDue(),
            ...questions.map(q => q.replace(/\n/, ' ').replace(/\s+/g, ' ')),
        ];
        const dataRows = rows.map(row => [
            row.nametag_id,
            [row.first_name, row.middle_initial, row.last_name].map(part => (part ?? '').trim()).filter(Boolean).join(' '),
            row.korean_name,
            row.email,
            nationalityLabel(row.nationality),
            row.institute_en, row.institute_ko,
            row.department,
            row.job_title,
            row.disability,
            row.dietary,
            getCategoryLabel(row, languageTag()),
            formatDate(row.registered_at),
            formatFee(row.registration_fee),
            ...questions.map(q => {
                const answer = row.custom_answers.find(a => a.question === q)?.answer ?? '';
                return answer.replace(/^- /, '').replace(/\n- /g, '; ');
            }),
        ]);
        downloadTsv([headers, ...dataRows], 'unpaid_registrations');
    }

    const nationalityLabel = (value) =>
        value === '1' ? m.nationality_korean() : value === '2' ? m.nationality_nonKorean() : m.nationality_notSpecified();

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

    // Recipients are gathered when the modal opens: the rows may be on other
    // pages, so they are fetched rather than read off the table.
    let send_email_modal = $state(false);
    let emailRecipients = $state('');
    let email_error = $state('');
    // Busy while the recipients are fetched: a second click would only fetch
    // them again.
    let email_preparing = $state(false);
    const showEmailModal = async (toAll) => {
        if (email_preparing) return;
        email_preparing = true;
        email_error = '';
        try {
            const asked = [...selected];
            const rows = toAll
                ? await fetchUnpaid()
                : (await list.fetchByIds(asked, { status: 'unpaid' })).map(toRow);
            if (!toAll) {
                // Whoever paid since being ticked has left this tab; drop them
                // from the selection (only those asked about - a row ticked
                // meanwhile stays).
                const still = new Set(rows.map(a => a.id));
                selected = selected.filter(id => !asked.includes(id) || still.has(id));
            }
            // Nobody left to write to - everyone paid or left since the tab
            // loaded: say so rather than open an empty email.
            if (rows.length === 0) {
                email_error = m.unpaidAttendees_noRecords();
                return;
            }
            emailRecipients = rows.map(a => a.email).filter(Boolean).join('; ');
            send_email_modal = true;
        } catch {
            email_error = m.common_error();
        } finally {
            email_preparing = false;
        }
    };

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
    // Staff pick from every account not yet registered here, searched on the
    // server, as in the other people pickers. The account list is staff-only
    // (the relay answers 403 to anyone else), so a non-staff event admin
    // finds the account by its exact address instead.
    const canBrowseAccounts = $derived(!!data.user?.is_staff);
    let register_user_id = $state(null);    // picked from the list (staff)
    let register_user = $state(null);       // ...and its row, for the address
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
        register_user = null;
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
        ? (register_user_id !== null ? register_user : null)
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
                selected = selected.filter(id => id !== deregister_target?.id);
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
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showEmailModal(true)} disabled={!list.counts.unpaid || email_preparing}>
                {m.unpaidAttendees_emailAll()}
            </DropdownItem>
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showEmailModal(false)} disabled={selected.length === 0 || email_preparing}>
                {m.unpaidAttendees_emailSelected()}
            </DropdownItem>
        </Dropdown>
        <Button color="primary" size="sm" onclick={exportUnpaidAsCSV} disabled={csv_exporting || !list.counts.unpaid}>
            {csv_exporting ? '...' : m.unpaidAttendees_exportCSV()}
        </Button>
    </div>
    {#if email_error}
        <Alert color="red" class="mb-4">{email_error}</Alert>
    {/if}
    {#if csv_error}
        <Alert color="red" class="mb-4">{m.common_error()}</Alert>
    {/if}

    {#if list.error && list.items.length > 0}
        <Alert color="red" class="mb-3">{m.common_error()}</Alert>
    {/if}
    <!-- Everyone still owing, whatever the search; blank until the first page arrives. -->
    <p class="mt-5 mb-3 text-sm text-right">
        {#if list.counts.unpaid !== undefined}{m.unpaidAttendees_count({ count: list.counts.unpaid })}{:else if list.error && !list.loading}–{:else}<Spinner size="4" />{/if}
    </p>
    <TableSearch placeholder={m.unpaidAttendees_searchPlaceholder()} hoverable={true} bind:inputValue={list.search} bind:field={list.field} fields={searchFields}>
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
            {#if paginated.length === 0}
                <TableBodyRow>
                    <TableBodyCell colspan="10" class="text-center">
                        {#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.unpaidAttendees_noRecords()}{/if}
                    </TableBodyCell>
                </TableBodyRow>
            {/if}
        </TableBody>
    </TableSearch>

    <TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={(p) => list.goto(p)} />
{/if}

<Modal id="register_attendee_modal" size="md" title={m.unpaidAttendees_register()} bind:open={register_modal}>
    <form method="post" action="?/register_attendee" use:enhance={afterRegister}>
        <p class="text-sm text-gray-600 mb-6">{m.unpaidAttendees_registerHelp()}</p>
        <input type="hidden" name="email" value={registerTarget?.email ?? ''} />
        {#if canBrowseAccounts}
            <div class="mb-6">
                <RemoteSearchList
                    url="/api/admin/users"
                    params={{ not_registered_for: data.event.id }}
                    bind:selectedId={register_user_id}
                    bind:selectedItem={register_user}
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
        if (result.type === 'success') {
            // A waived registration leaves this tab, so it leaves the selection too.
            if (toggling_attendee?.fee_waived) selected = selected.filter(id => id !== toggling_attendee.id);
            await update({ reset: false });
        }
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
