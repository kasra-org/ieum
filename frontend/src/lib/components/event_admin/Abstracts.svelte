<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Card } from '$lib/components/ui';
    import { Button, Modal, Label, Input, Select, Textarea, Alert } from '$lib/components/ui';
    import { Tabs, TabItem, Dropdown, DropdownItem } from '$lib/components/ui';
    import { Spinner } from '$lib/components/ui';
    import { ChevronDown, Download, Pencil, Trash2, UserMinus } from '@lucide/svelte';
    import { untrack } from 'svelte';
    import { enhance } from '$app/forms';
    import { error } from '@sveltejs/kit';
    import { browser } from '$app/environment';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { getDisplayInstitute, getDisplayName, getPresentationTypeLabel, matchesSearch } from '$lib/utils.js';
    import UserSelectionModal from '$lib/components/UserSelectionModal.svelte';
    import RemoteSearchList from '$lib/components/RemoteSearchList.svelte';
    import { PagedList } from '$lib/pagedList.svelte.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';

    let { data } = $props();

    // DOMPurify for XSS protection
    let DOMPurify = $state(null);
    $effect(() => {
        if (browser && !DOMPurify) {
            import('dompurify').then(module => {
                DOMPurify = module.default;
            });
        }
    });
    function sanitizeHtml(html) {
        if (!html) return '';
        if (browser && DOMPurify) {
            return DOMPurify.sanitize(html);
        }
        // DOMPurify is browser-only; never hand back unsanitized markup.
        return '';
    }

    // Registrations are searched on the server by the pickers (add reviewer,
    // add abstract) rather than loaded whole with the page.
    const attendeesUrl = $derived(`/api/event/${data.event.id}/attendees`);

    let searchTermReviewer = $state('');
    let selectedReviewers = $state([]);
    let reviewerCurrentPage = $state(1);
    const itemsPerPage = 10;

    let reviewerSearchField = $state('all');
    const reviewerSearchFields = [
        { value: 'name', name: m.search_name(), get: r => [r.name, r.korean_name] },
        { value: 'email', name: m.search_email(), get: r => [r.user?.email, r.user_email] },
        { value: 'institute', name: m.search_institute(), get: r => [r.institute, r.institute_ko] },
    ];

    let filteredReviewers = $derived(
        data.reviewers.filter((item) => matchesSearch(item, searchTermReviewer, reviewerSearchField, reviewerSearchFields))
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermReviewer;
        reviewerSearchField;
        reviewerCurrentPage = 1;
    });

    // The abstract table pages, searches and filters by type on the server.
    // Its search fields are the server's (title, presenter, institute, type).
    const list = new PagedList(() => `/api/event/${data.event.id}/abstracts`, { filters: { type: '', types: '' } });
    list.track(() => data);
    const abstractSearchFields = [
        { value: 'title', name: m.search_title() },
        { value: 'presenter', name: m.search_presenter() },
        { value: 'institute', name: m.search_institute() },
        { value: 'type', name: m.search_type() },
    ];
    // Presentation type filter - the abstract table only; the reviewer table
    // above keeps its own search. The chip counts come from the server and
    // cover every abstract whatever the search; a type it leaves out has none.
    const PRESENTATION_TYPES = ['poster', 'short_talk_poster', 'short_talk', 'flash_talk_poster', 'invited'];
    // The server matches type names in English only; the names on screen may
    // be Korean. Send the codes whose name, as shown, contains the search, so
    // typing a type the way it reads here finds it. Set before the debounced
    // reload fires, and carried by exportAll too.
    $effect(() => {
        const term = list.search.trim().toLowerCase();
        const byType = term && (list.field === 'all' || list.field === 'type');
        const types = byType
            ? PRESENTATION_TYPES.filter(t =>
                getPresentationTypeLabel({ presentation_type: t }, m).toLowerCase().includes(term))
            : [];
        // Only a real change: rewriting the same value would still read as a
        // new request and send the pager back to page 1.
        untrack(() => {
            const joined = types.join(',');
            if (list.filters.types !== joined) list.filters = { ...list.filters, types: joined };
        });
    });
    let abstractTypeFilter = $derived(list.filters.type || 'all');

    // Ticked abstract rows, by id across pages. Only those the current filter
    // shows are acted on, so a row ticked under another filter is never
    // emailed unseen.
    let selectedAbstracts = $state([]);
    let pageAllSelected = $derived(
        list.items.length > 0 && list.items.every(a => selectedAbstracts.includes(a.id))
    );
    const presenterEmail = (r) => r.attendee?.user?.email || r.attendee?.user_email || '';
    const uniqueEmails = (rows) => [...new Set(rows.map(presenterEmail).filter(Boolean))];

    // The email menu counts people, and the rows behind them are on the
    // server now: as the menu opens it fetches every abstract the current
    // type and search match, and the ticked ones are picked out of those -
    // so both counts, and the recipients, are exact. Null while fetching.
    let abstract_email_menu = $state(false);
    let filteredEmailRows = $state(null);
    let emailRowsError = $state(false);
    let emailRowsSequence = 0;
    async function loadEmailRows() {
        const sequence = ++emailRowsSequence;
        filteredEmailRows = null;
        emailRowsError = false;
        let rows = [];
        let failed = false;
        try {
            rows = await list.exportAll();
        } catch {
            // Leave the menu with nobody to send to rather than half a list,
            // and say why the counts are empty.
            failed = true;
        }
        if (sequence === emailRowsSequence) {
            filteredEmailRows = rows;
            emailRowsError = failed;
        }
    }
    $effect(() => {
        if (abstract_email_menu) untrack(loadEmailRows);
    });
    let selectedEmailRows = $derived(
        filteredEmailRows?.filter(a => selectedAbstracts.includes(a.id)) ?? null
    );
    // People, not rows: a row whose presenter has no address on file cannot be
    // emailed, and counting it would open the window with nobody to send to.
    let filteredPresenterCount = $derived(filteredEmailRows ? uniqueEmails(filteredEmailRows).length : null);
    let selectedPresenterCount = $derived(selectedEmailRows ? uniqueEmails(selectedEmailRows).length : null);

    let abstract_email_modal = $state(false);
    let abstract_email_scope = $state('selected');
    const showAbstractEmailModal = (scope) => {
        abstract_email_scope = scope;
        abstract_email_modal = true;
    };
    let abstractEmailRecipients = $derived(
        uniqueEmails((abstract_email_scope === 'filtered' ? filteredEmailRows : selectedEmailRows) ?? []).join('; ')
    );

    // Ready-made texts for the presenter email. Rendered per recipient on the
    // server, so one send covers every type: each person reads the paragraph
    // for their own presentation type. Double quotes only - the editor's round
    // trip is safe for them, and the template parser needs them intact.
    const SHORT = 'abstract.presentation_type == "short_talk" or abstract.presentation_type == "short_talk_poster"';
    const FLASH = 'abstract.presentation_type == "flash_talk_poster"';
    const abstractEmailPresets = [{
        label: m.abstracts_presetTalkNotice(),
        subject: `[{{ event.name }}] Your Abstract Has Been Selected for a {% if ${FLASH} %}Flash Talk{% elif ${SHORT} %}Short Talk{% else %}Presentation{% endif %}`,
        body: `Dear {{ attendee.first_name }},

{% if ${SHORT} %}We are pleased to inform you that your abstract, "{{ abstract.title }}", has been selected for a **short talk** at {{ event.name }}. Congratulations!

Each short talk is allotted **10 minutes**. Please prepare your slides so that your presentation fits within this time. **We kindly ask that you keep strictly to the 10-minute limit**, as the programme runs on a tight schedule and every speaker's time depends on the session staying on track. The session chair will keep time and may ask you to conclude once your time is up.{% elif ${FLASH} %}We are pleased to inform you that your abstract, "{{ abstract.title }}", has been selected for a **flash talk** at {{ event.name }}. Congratulations!

A flash talk is a brief introduction to your work, designed to draw participants to your poster. Each flash talk is allotted **3 minutes**, and please prepare **no more than 2 slides**. **We kindly ask that you keep strictly to both the 3-minute and the 2-slide limits**, as many flash talks are presented back to back and the session runs on a tight schedule. Presentations that exceed the limit may be cut short by the session chair.{% endif %}

If you have any questions, please do not hesitate to contact us.

We look forward to your presentation.

Yours sincerely,
The Organising Committee
{{ event.name }}`,
    }];

    let reviewerTotalPages = $derived(Math.ceil(filteredReviewers.length / itemsPerPage));
    let paginatedReviewers = $derived(
        filteredReviewers.slice((reviewerCurrentPage - 1) * itemsPerPage, reviewerCurrentPage * itemsPerPage)
    );

    function handleReviewerPageChange(page) {
        reviewerCurrentPage = page;
    }

    // Adding an abstract on a registrant's behalf - one that arrived by email
    // or on paper. Only registrants without one are offered (the server
    // leaves the others out of the picker's search): one each.
    let add_abstract_modal = $state(false);
    let newAbstractAttendeeId = $state(null);
    let newAbstractTitle = $state('');
    let newAbstractType = $state('poster');
    let newAbstractFile = $state({ name: '', content: '' });
    let newAbstractSendConfirmation = $state(false);
    let add_abstract_error = $state('');
    let adding_abstract = $state(false);
    let abstractFileInput = $state(null);
    const showAddAbstractModal = () => {
        newAbstractAttendeeId = null;
        newAbstractTitle = '';
        newAbstractType = 'poster';
        newAbstractFile = { name: '', content: '' };
        newAbstractSendConfirmation = false;
        add_abstract_error = '';
        add_abstract_modal = true;
    };
    // Same limits as a registrant's own upload; the server checks again.
    function pickAbstractFile(event) {
        const file = event.target.files?.[0];
        if (!file) return;
        const ext = (file.name.split('.').pop() || '').toLowerCase();
        if (ext !== 'docx' && ext !== 'odt') {
            add_abstract_error = m.abstractSubmission_invalidFileFormat();
            event.target.value = '';
            return;
        }
        if (file.size > 1048576) {
            add_abstract_error = m.abstractSubmission_fileSizeExceeds();
            event.target.value = '';
            return;
        }
        const reader = new FileReader();
        reader.onload = (e) => {
            add_abstract_error = '';
            newAbstractFile = { name: file.name, content: e.target.result };
        };
        reader.onerror = () => {
            newAbstractFile = { name: '', content: '' };
            add_abstract_error = m.abstractSubmission_fileReadFailed();
        };
        reader.readAsDataURL(file);
    }
    let canAddAbstract = $derived(
        !!newAbstractAttendeeId && newAbstractTitle.trim() !== '' && !!newAbstractFile.content && !adding_abstract
    );
    const afterAddAbstract = () => {
        adding_abstract = true;
        return async ({ result, update }) => {
            adding_abstract = false;
            if (result.type === 'success') {
                await update({ reset: false });
                add_abstract_modal = false;
            } else {
                add_abstract_error = apiMessage(result.error, m.abstracts_addManuallyError);
            }
        };
    };

    let reviewer_modal = $state(false);
    let delete_reviewer_modal = $state(false);
    let selected_reviewer = $state(null);

    const addReviewerModal = () => {
        selected_reviewer = null;
        reviewer_modal = true;
    };
    const deleteReviewerModal = (id) => {
        selected_reviewer = data.reviewers.find((item) => item.id === id);
        delete_reviewer_modal = true;
    };

    let add_reviwer_error = $state('');
    const afterAddReviewer = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                reviewer_modal = false;
                add_reviwer_error = '';
            } else {
                add_reviwer_error = m.userSelection_error();
            }
        }
    };

    let delete_reviewer_error = $state('');
    const afterDeleteReviewer = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                delete_reviewer_modal = false;
                delete_reviewer_error = '';
            } else {
                delete_reviewer_error = m.userSelection_error();
            }
        }
    };

    let send_email_modal = $state(false);
    const showSendEmailModal = () => {
        send_email_modal = true;
    };
    let emailRecipients = $derived(
        selectedReviewers.map(id => { const r = data.reviewers.find(a => a.id === id); return r?.user?.email || r?.user_email; }).filter(Boolean).join("; ")
    );

    let abstract_modal = $state(false);
    let abstract_delete_modal = $state(false);
    let selected_abstract = $state(null);
    let update_abstract_error = $state('');
    const showAbstractEditModal = async (id) => {
        // fetch full abstract details
        const body = new FormData();
        body.append('id', id);
        const response = await fetch(`?/get_abstract`, {
            method: 'POST',
            body
        });
        if (response.ok) {
            const result = await response.json();
            selected_abstract = JSON.parse(JSON.parse(result.data)[0]);
            abstract_modal = true;
        } else {
            update_abstract_error = m.abstracts_fetchError();
        }
    };
    const showAbstractDeleteModal = (id) => {
        selected_abstract = list.items.find((item) => item.id === id);
        abstract_delete_modal = true;
    };
    const afterUpdateAbstract = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                abstract_modal = false;
                update_abstract_error = '';
            } else {
                update_abstract_error = apiMessage(result.error);
            }
        }
    };

    let delete_abstract_error = $state('');
    const afterDeleteAbstract = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                abstract_delete_modal = false;
                delete_abstract_error = '';
            } else {
                delete_abstract_error = apiMessage(result.error);
            }
        }
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.abstracts_title()}</Heading>
<p class="font-light mb-6">{m.abstracts_description()}</p>

<Heading tag="h3" class="text-lg font-bold mb-3">{m.abstracts_reviewersTitle()}</Heading>
<div class="flex justify-end gap-2">
    <Button color="primary" size="sm" disabled={selectedReviewers.length === 0} onclick={showSendEmailModal}>{m.abstracts_sendEmailToSelected()}</Button>
    <Button color="primary" size="sm" onclick={addReviewerModal}>{m.abstracts_addReviewer()}</Button>
</div>
<TableSearch placeholder={m.abstracts_searchReviewerPlaceholder()} hoverable={true} bind:inputValue={searchTermReviewer} bind:field={reviewerSearchField} fields={reviewerSearchFields}>
    <TableHead>
        <TableHeadCell class="w-1"><Checkbox
            checked={selectedReviewers.length > 0 && selectedReviewers.length === data.reviewers.length}
            intermediate={
                selectedReviewers.length > 0 && (selectedReviewers.length < data.reviewers.length)
            }
            onclick={(e) => {
                if (e.target.checked) {
                    selectedReviewers = filteredReviewers.map(a => a.id);
                } else {
                    selectedReviewers = [];
                }
            }}
        /></TableHeadCell>
        <TableHeadCell>{m.abstracts_name()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_email()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_institute()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.abstracts_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedReviewers as row}
            <TableBodyRow>
                <TableBodyCell><Checkbox checked={selectedReviewers.includes(row.id)} onclick={(e) => {
                    if (e.target.checked) {
                        selectedReviewers = [...selectedReviewers, row.id];
                    } else {
                        selectedReviewers = selectedReviewers.filter(a => a !== row.id);
                    }
                }} /></TableBodyCell>
                <TableBodyCell>{getDisplayName(row)}</TableBodyCell>
                <TableBodyCell>{row.user?.email || row.user_email || ''}</TableBodyCell>
                <TableBodyCell>{getDisplayInstitute(row)}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.abstracts_removeReviewer()}>
                            <Button color="none" size="none" onclick={() => deleteReviewerModal(row.id)}>
                                <UserMinus class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filteredReviewers.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="5" class="text-center">{m.abstracts_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={reviewerCurrentPage} totalPages={reviewerTotalPages} onPageChange={handleReviewerPageChange} />

<Heading tag="h3" class="text-lg font-bold mt-12 mb-3">{m.abstracts_abstractsTitle()}</Heading>
<div class="flex flex-wrap items-center justify-between gap-3 mb-2">
    <div class="flex flex-wrap items-center gap-2" role="group" aria-label={m.abstracts_filterType()}>
        <Button size="xs" color={abstractTypeFilter === 'all' ? 'primary' : 'light'} onclick={() => list.setFilter('type', '')}>
            {m.search_all()} ({list.loaded ? (list.counts.all ?? 0) : (list.error && !list.loading ? '–' : '…')})
        </Button>
        {#each PRESENTATION_TYPES as t}
            <Button size="xs" color={abstractTypeFilter === t ? 'primary' : 'light'} onclick={() => list.setFilter('type', t)}>
                {getPresentationTypeLabel({ presentation_type: t }, m)} ({list.loaded ? (list.counts[t] ?? 0) : (list.error && !list.loading ? '–' : '…')})
            </Button>
        {/each}
    </div>
    <div class="flex items-center gap-2">
        <Button color="primary" size="sm" onclick={showAddAbstractModal}>{m.abstracts_addManually()}</Button>
        <Button color="primary" size="sm">{m.abstracts_emailActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
        <Dropdown class="w-auto list-none p-1" bind:open={abstract_email_menu}>
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showAbstractEmailModal('filtered')} disabled={!filteredPresenterCount}>
                {m.abstracts_emailFiltered({ count: filteredPresenterCount ?? '…' })}
            </DropdownItem>
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showAbstractEmailModal('selected')} disabled={!selectedPresenterCount}>
                {m.abstracts_emailSelected({ count: selectedPresenterCount ?? '…' })}
            </DropdownItem>
        </Dropdown>
    </div>
</div>
{#if emailRowsError}
    <Alert color="red" class="mb-3">{m.common_error()}</Alert>
{/if}
{#if list.loaded}<p class="text-sm text-gray-600 mb-1">{m.abstracts_resultCount({ count: list.total })}</p>{/if}
{#if list.error && list.items.length > 0}
    <Alert color="red" class="mb-3">{m.common_error()}</Alert>
{/if}
<TableSearch placeholder={m.abstracts_searchAbstractPlaceholder()} hoverable={true} bind:inputValue={list.search} bind:field={list.field} fields={abstractSearchFields}>
    <TableHead>
        <!-- The rows on this page: the others are not loaded to tick. -->
        <TableHeadCell class="w-1"><Checkbox
            checked={pageAllSelected}
            onclick={(e) => {
                const pageIds = list.items.map(a => a.id);
                selectedAbstracts = e.target.checked
                    ? [...new Set([...selectedAbstracts, ...pageIds])]
                    : selectedAbstracts.filter(id => !pageIds.includes(id));
            }}
        /></TableHeadCell>
        <TableHeadCell>{m.abstracts_title()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_presenter()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_type()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_votes()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.abstracts_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each list.items as row (row.id)}
            <TableBodyRow>
                <TableBodyCell><Checkbox checked={selectedAbstracts.includes(row.id)} onclick={(e) => {
                    selectedAbstracts = e.target.checked
                        ? [...selectedAbstracts, row.id]
                        : selectedAbstracts.filter(id => id !== row.id);
                }} /></TableBodyCell>
                <TableBodyCell>{(row.title.length > 10)?row.title.slice(0, 10)+'...':row.title}</TableBodyCell>
                <TableBodyCell>{getDisplayName(row.attendee)}</TableBodyCell>
                <TableBodyCell>{getPresentationTypeLabel(row, m)}</TableBodyCell>
                <TableBodyCell>
                    {#if row.is_reviewable}
                        {row.votes}
                    {:else}
                        <!-- 0 votes here would read as "nobody voted" rather than
                             "not up for review", so say so explicitly. -->
                        <span class="text-xs text-gray-500">{m.abstracts_notReviewed()}</span>
                    {/if}
                </TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.abstracts_download()}>
                            <Button color="none" size="none" href={row.link}>
                                <Download class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.abstracts_editAbstract()}>
                            <Button color="none" size="none" onclick={() => showAbstractEditModal(row.id)}>
                                <Pencil class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.abstracts_removeAbstract()}>
                            <Button color="none" size="none" onclick={() => showAbstractDeleteModal(row.id)}>
                                <Trash2 class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if list.items.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="6" class="text-center">
                    {#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.abstracts_noRecords()}{/if}
                </TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={(p) => list.goto(p)} />

<UserSelectionModal
    bind:open={reviewer_modal}
    title={m.abstracts_addReviewer()}
    url={attendeesUrl}
    params={{ status: 'all' }}
    action="?/add_reviewer"
    submitLabel={m.abstracts_add()}
    bind:error={add_reviwer_error}
    onSubmit={afterAddReviewer}
/>

<Modal bind:open={delete_reviewer_modal} title={m.abstracts_removeReviewer()} size="sm">
    <form method="POST" action="?/delete_reviewer" use:enhance={afterDeleteReviewer}>
        <input type="hidden" name="id" value={selected_reviewer?selected_reviewer.id:''} />
        <p class="mb-6">{m.abstracts_removeReviewerConfirm()}</p>
        {#if delete_reviewer_error}
            <Alert color="red" class="mb-6">{delete_reviewer_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.abstracts_remove()}</Button>
            <Button color="dark" type="button" onclick={() => delete_reviewer_modal = false}>{m.abstracts_cancel()}</Button>
        </div>
    </form>
</Modal>

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />
<Modal id="add_abstract_modal" size="lg" title={m.abstracts_addManually()} bind:open={add_abstract_modal}>
    <form method="post" action="?/add_abstract" use:enhance={afterAddAbstract}>
        <p class="text-sm text-gray-600 mb-6">{m.abstracts_addManuallyHelp()}</p>
        <input type="hidden" name="attendee_id" value={newAbstractAttendeeId ?? ''} />
        <input type="hidden" name="file_name" value={newAbstractFile.name} />
        <input type="hidden" name="file_content" value={newAbstractFile.content} />
        <input type="hidden" name="send_confirmation" value={newAbstractSendConfirmation ? 'true' : 'false'} />

        <div class="mb-6">
            <Label class="block mb-2">{m.abstracts_registrant()} <span class="text-red-500">*</span></Label>
            <RemoteSearchList
                url={attendeesUrl}
                params={{ status: 'all', has_abstract: false }}
                bind:selectedId={newAbstractAttendeeId}
                maxHeight="max-h-60"
                showChangeButton={true}
                getItemName={getDisplayName}
                getItemInstitute={getDisplayInstitute}
                getItemEmail={(a) => a.email || a.user?.email || a.user_email || ''}
            />
        </div>
        <div class="mb-6">
            <Label for="new_abstract_title" class="block mb-2">{m.abstracts_titleField()} <span class="text-red-500">*</span></Label>
            <Input id="new_abstract_title" name="title" type="text" bind:value={newAbstractTitle} />
        </div>
        <div class="mb-6">
            <Label for="new_abstract_type" class="block mb-2">{m.abstracts_type()}</Label>
            <Select id="new_abstract_type" name="presentation_type" bind:value={newAbstractType} items={PRESENTATION_TYPES.map(t => ({ value: t, name: getPresentationTypeLabel({ presentation_type: t }, m) }))} />
        </div>
        <div class="mb-6">
            <Label for="new_abstract_file" class="block mb-2">{m.abstracts_file()} <span class="text-red-500">*</span></Label>
            <input id="new_abstract_file" type="file" accept=".docx,.odt" bind:this={abstractFileInput} onchange={pickAbstractFile}
                class="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50" />
            {#if newAbstractFile.name}<p class="mt-1 text-xs text-gray-500">{newAbstractFile.name}</p>{/if}
        </div>
        <div class="mb-6">
            <Checkbox bind:checked={newAbstractSendConfirmation}>{m.abstracts_sendConfirmation()}</Checkbox>
        </div>
        {#if add_abstract_error}
            <Alert color="red" class="mb-6">{add_abstract_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="alternative" type="button" onclick={() => add_abstract_modal = false}>{m.common_cancel()}</Button>
            <Button color="primary" type="submit" disabled={!canAddAbstract}>{m.abstracts_add()}</Button>
        </div>
    </form>
</Modal>

<SendEmailModal bind:open={abstract_email_modal} recipients={abstractEmailRecipients} eventadmins={data.eventadmins} presets={abstractEmailPresets} />

<Modal id="abstract_modal" size="lg" title={m.abstracts_detailsTitle()} bind:open={abstract_modal} outsideclose>
    <form method="post" action="?/update_abstract" use:enhance={afterUpdateAbstract}>
        <input type="hidden" name="id" value={selected_abstract?selected_abstract.id:''} />
        <div class="flex flex-row justify-stretch gap-6 mb-6">
            <div class="w-full">
                <Label for="votes" class="block mb-2">{m.abstracts_votes()}</Label>
                <Input id="votes" type="number" value={selected_abstract?selected_abstract.votes:''} readonly />
            </div>
            <div class="w-full">
                <Label for="presentation_type" class="block mb-2">{m.abstracts_type()}</Label>
                <Select id="presentation_type" name="presentation_type" items={[
                    { value: 'poster', name: m.presentationType_poster() },
                    { value: 'short_talk_poster', name: m.presentationType_shortTalkPoster() },
                    { value: 'short_talk', name: m.presentationType_shortTalk() },
                    { value: 'flash_talk_poster', name: m.presentationType_flashTalkPoster() },
                    { value: 'invited', name: m.presentationType_invited() }
                ]} value={selected_abstract?selected_abstract.presentation_type:''} />
            </div>
        </div>
        <div class="mb-6">
            <Label for="presenter" class="block mb-2">{m.abstracts_presenter()}</Label>
            <Input id="presenter" type="text" value={selected_abstract?getDisplayName(selected_abstract.attendee):''} readonly />
        </div>
        <div class="mb-6">
            <Label for="title" class="block mb-2">{m.abstracts_titleField()}</Label>
            <Input id="title" name="title" type="text" value={selected_abstract?selected_abstract.title:''} />
        </div>
        <div class="mb-6">
            <Label for="abstract" class="block mb-2">{m.abstracts_preview()}</Label>
            <Card size="xl">
                {@html sanitizeHtml(selected_abstract?.body)}
            </Card>
        </div>
        {#if update_abstract_error}
            <Alert color="red" class="mb-6">{update_abstract_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="primary" type="submit">{m.abstracts_update()}</Button>
        </div>
    </form>
</Modal>

<Modal id="abstract_delete_modal" size="sm" title={m.abstracts_removeAbstract()} bind:open={abstract_delete_modal} outsideclose>
    <form method="post" action="?/delete_abstract" use:enhance={afterDeleteAbstract}>
        <input type="hidden" name="id" value={selected_abstract?selected_abstract.id:''} />
        <p class="mb-6">{m.abstracts_removeAbstractConfirm()}</p>
        {#if delete_abstract_error}
            <Alert color="red" class="mb-6">{delete_abstract_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.abstracts_remove()}</Button>
            <Button color="dark" type="button" onclick={() => abstract_delete_modal = false}>{m.abstracts_cancel()}</Button>
        </div>
    </form>
</Modal>
