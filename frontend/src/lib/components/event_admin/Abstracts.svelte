<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Card } from '$lib/components/ui';
    import { Button, Modal, Label, Input, Select, Textarea, Alert } from '$lib/components/ui';
    import { Tabs, TabItem, Dropdown, DropdownItem } from '$lib/components/ui';
    import { ChevronDown, Download, Pencil, Trash2, UserMinus } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import { error } from '@sveltejs/kit';
    import { browser } from '$app/environment';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { getDisplayInstitute, getDisplayName, getPresentationTypeLabel, matchesSearch } from '$lib/utils.js';
    import UserSelectionModal from '$lib/components/UserSelectionModal.svelte';
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

    // Normalize attendees list for UserSelectionModal
    const attendeeUserList = $derived(data.attendees.map(a => ({ id: a.id, email: a.user?.email || a.user_email || '', ...a })));

    let searchTermReviewer = $state('');
    let selectedReviewers = $state([]);
    let reviewerCurrentPage = $state(1);
    let abstractCurrentPage = $state(1);
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

    // The abstract list's search box used to be bound to nothing.
    let searchTermAbstract = $state('');
    let abstractSearchField = $state('all');
    const abstractSearchFields = [
        { value: 'title', name: m.search_title(), get: r => r.title },
        { value: 'presenter', name: m.search_presenter(), get: r => [getDisplayName(r.attendee), r.attendee?.name, r.attendee?.korean_name] },
        { value: 'institute', name: m.search_institute(), get: r => [r.attendee?.institute, r.attendee?.institute_ko] },
        { value: 'type', name: m.search_type(), get: r => getPresentationTypeLabel(r, m) },
    ];
    // Presentation type filter - the abstract table only; the reviewer table
    // above keeps its own search. Older rows predate presentation_type and are
    // read the same way getPresentationTypeLabel reads them.
    const PRESENTATION_TYPES = ['poster', 'short_talk_poster', 'short_talk', 'flash_talk_poster', 'invited'];
    const typeOf = (r) => r.presentation_type
        ?? (r.type === 'speaker' ? 'short_talk' : (r.wants_short_talk ? 'short_talk_poster' : 'poster'));
    let abstractTypeFilter = $state('all');
    // How many abstracts each type has, so a filter button says what it holds.
    let abstractTypeCounts = $derived(
        data.abstracts.reduce((acc, r) => { acc[typeOf(r)] = (acc[typeOf(r)] ?? 0) + 1; return acc; }, {})
    );

    let filteredAbstracts = $derived(
        data.abstracts.filter((item) =>
            (abstractTypeFilter === 'all' || typeOf(item) === abstractTypeFilter)
            && matchesSearch(item, searchTermAbstract, abstractSearchField, abstractSearchFields))
    );
    $effect(() => {
        searchTermAbstract;
        abstractSearchField;
        abstractTypeFilter;
        abstractCurrentPage = 1;
    });

    // Ticked abstract rows. Only those the current filter shows are acted on,
    // so a row ticked under another filter is never emailed unseen.
    let selectedAbstracts = $state([]);
    let activeAbstractSelection = $derived(
        selectedAbstracts.filter(id => filteredAbstracts.some(a => a.id === id))
    );
    const presenterEmail = (r) => r.attendee?.user?.email || r.attendee?.user_email || '';
    let abstract_email_modal = $state(false);
    let abstract_email_scope = $state('selected');
    const showAbstractEmailModal = (scope) => {
        abstract_email_scope = scope;
        abstract_email_modal = true;
    };
    let abstractEmailRecipients = $derived.by(() => {
        const rows = abstract_email_scope === 'filtered'
            ? filteredAbstracts
            : filteredAbstracts.filter(a => activeAbstractSelection.includes(a.id));
        return [...new Set(rows.map(presenterEmail).filter(Boolean))].join('; ');
    });
    let filteredPresenterCount = $derived(new Set(filteredAbstracts.map(presenterEmail).filter(Boolean)).size);
    // People, not rows: a row whose presenter has no address on file cannot be
    // emailed, and counting it would open the window with nobody to send to.
    let selectedPresenterCount = $derived(new Set(
        filteredAbstracts.filter(a => activeAbstractSelection.includes(a.id)).map(presenterEmail).filter(Boolean)
    ).size);

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

    let abstractTotalPages = $derived(Math.ceil(filteredAbstracts.length / itemsPerPage));
    let paginatedAbstracts = $derived(
        filteredAbstracts.slice((abstractCurrentPage - 1) * itemsPerPage, abstractCurrentPage * itemsPerPage)
    );

    function handleReviewerPageChange(page) {
        reviewerCurrentPage = page;
    }

    function handleAbstractPageChange(page) {
        abstractCurrentPage = page;
    }

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
        selected_abstract = data.abstracts.find((item) => item.id === id);
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
        <Button size="xs" color={abstractTypeFilter === 'all' ? 'primary' : 'light'} onclick={() => abstractTypeFilter = 'all'}>
            {m.search_all()} ({data.abstracts.length})
        </Button>
        {#each PRESENTATION_TYPES as t}
            <Button size="xs" color={abstractTypeFilter === t ? 'primary' : 'light'} onclick={() => abstractTypeFilter = t}>
                {getPresentationTypeLabel({ presentation_type: t }, m)} ({abstractTypeCounts[t] ?? 0})
            </Button>
        {/each}
    </div>
    <div class="flex items-center gap-2">
        <Button color="primary" size="sm">{m.abstracts_emailActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
        <Dropdown class="w-auto list-none p-1">
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showAbstractEmailModal('filtered')} disabled={filteredPresenterCount === 0}>
                {m.abstracts_emailFiltered({ count: filteredPresenterCount })}
            </DropdownItem>
            <DropdownItem class="text-sm whitespace-nowrap" onclick={() => showAbstractEmailModal('selected')} disabled={selectedPresenterCount === 0}>
                {m.abstracts_emailSelected({ count: selectedPresenterCount })}
            </DropdownItem>
        </Dropdown>
    </div>
</div>
<p class="text-sm text-gray-600 mb-1">{m.abstracts_resultCount({ count: filteredAbstracts.length })}</p>
<TableSearch placeholder={m.abstracts_searchAbstractPlaceholder()} hoverable={true} bind:inputValue={searchTermAbstract} bind:field={abstractSearchField} fields={abstractSearchFields}>
    <TableHead>
        <TableHeadCell class="w-1"><Checkbox
            checked={activeAbstractSelection.length > 0 && activeAbstractSelection.length === filteredAbstracts.length}
            onclick={(e) => {
                selectedAbstracts = e.target.checked ? filteredAbstracts.map(a => a.id) : [];
            }}
        /></TableHeadCell>
        <TableHeadCell>{m.abstracts_title()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_presenter()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_type()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_votes()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.abstracts_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedAbstracts as row}
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
        {#if filteredAbstracts.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="6" class="text-center">{m.abstracts_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={abstractCurrentPage} totalPages={abstractTotalPages} onPageChange={handleAbstractPageChange} />

<UserSelectionModal
    bind:open={reviewer_modal}
    title={m.abstracts_addReviewer()}
    userList={attendeeUserList}
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
