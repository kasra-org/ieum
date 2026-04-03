<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Card } from 'flowbite-svelte';
    import { Button, Modal, Label, Input, Select, Textarea, Alert } from 'flowbite-svelte';
    import { Tabs, TabItem } from 'flowbite-svelte';
    import { UserRemoveSolid, DownloadSolid, EditSolid, TrashBinSolid } from 'flowbite-svelte-icons';
    import { enhance } from '$app/forms';
    import { error } from '@sveltejs/kit';
    import { browser } from '$app/environment';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
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
        return html;
    }

    // Normalize attendees list for UserSelectionModal
    const attendeeUserList = $derived(data.attendees.map(a => ({ id: a.id, email: a.user?.email || a.user_email || '', ...a })));

    let searchTermReviewer = $state('');
    let selectedReviewers = $state([]);
    let reviewerCurrentPage = $state(1);
    let abstractCurrentPage = $state(1);
    const itemsPerPage = 10;

    let filteredReviewers = $derived(
        data.reviewers.filter((item) => {
            const searchLower = searchTermReviewer.toLowerCase();
            return item.name.toLowerCase().includes(searchLower) ||
                   (item.korean_name && item.korean_name.toLowerCase().includes(searchLower));
        })
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermReviewer;
        reviewerCurrentPage = 1;
    });

    let reviewerTotalPages = $derived(Math.ceil(filteredReviewers.length / itemsPerPage));
    let paginatedReviewers = $derived(
        filteredReviewers.slice((reviewerCurrentPage - 1) * itemsPerPage, reviewerCurrentPage * itemsPerPage)
    );

    let abstractTotalPages = $derived(Math.ceil(data.abstracts.length / itemsPerPage));
    let paginatedAbstracts = $derived(
        data.abstracts.slice((abstractCurrentPage - 1) * itemsPerPage, abstractCurrentPage * itemsPerPage)
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
                update_abstract_error = result.error.message;
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
                delete_abstract_error = result.error.message;
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
<TableSearch placeholder={m.abstracts_searchReviewerPlaceholder()} hoverable={true} bind:inputValue={searchTermReviewer}>
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
                                <UserRemoveSolid class="w-5 h-5" />
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
<TableSearch placeholder={m.abstracts_searchAbstractPlaceholder()} hoverable={true}>
    <TableHead>
        <TableHeadCell>{m.abstracts_title()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_presenter()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_type()}</TableHeadCell>
        <TableHeadCell>{m.abstracts_votes()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.abstracts_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedAbstracts as row}
            <TableBodyRow>
                <TableBodyCell>{(row.title.length > 10)?row.title.slice(0, 10)+'...':row.title}</TableBodyCell>
                <TableBodyCell>{getDisplayName(row.attendee)}</TableBodyCell>
                <TableBodyCell>
                    {row.type === 'speaker' ? m.abstractType_speaker() : m.abstractType_poster()}
                    {#if row.type === 'poster' && row.wants_short_talk}
                        <span class="text-xs text-gray-500 ml-1">({m.myRegistration_shortTalkNomination()})</span>
                    {/if}
                </TableBodyCell>
                <TableBodyCell>{row.votes}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.abstracts_download()}>
                            <Button color="none" size="none" href={row.link}>
                                <DownloadSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.abstracts_editAbstract()}>
                            <Button color="none" size="none" onclick={() => showAbstractEditModal(row.id)}>
                                <EditSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.abstracts_removeAbstract()}>
                            <Button color="none" size="none" onclick={() => showAbstractDeleteModal(row.id)}>
                                <TrashBinSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if data.abstracts.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="5" class="text-center">{m.abstracts_noRecords()}</TableBodyCell>
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

<Modal id="abstract_modal" size="lg" title={m.abstracts_detailsTitle()} bind:open={abstract_modal} outsideclose>
    <form method="post" action="?/update_abstract" use:enhance={afterUpdateAbstract}>
        <input type="hidden" name="id" value={selected_abstract?selected_abstract.id:''} />
        <div class="flex flex-row justify-stretch gap-6 mb-6">
            <div class="w-full">
                <Label for="votes" class="block mb-2">{m.abstracts_votes()}</Label>
                <Input id="votes" type="number" value={selected_abstract?selected_abstract.votes:''} readonly />
            </div>
            <div class="w-full">
                <Label for="type" class="block mb-2">{m.abstracts_type()}</Label>
                <Select id="type" name="type" items={[
                    { value: 'speaker', name: m.abstractType_speaker() },
                    { value: 'poster', name: m.abstractType_poster() }
                ]} value={selected_abstract?selected_abstract.type:''} />
            </div>
            <div class="w-full">
                <Label for="wants_short_talk" class="block mb-2">{m.myRegistration_shortTalkNomination()}</Label>
                <Select id="wants_short_talk" name="wants_short_talk" items={[
                    { value: 'true', name: m.abstracts_yes() },
                    { value: 'false', name: m.abstracts_no() }
                ]} value={selected_abstract?selected_abstract.wants_short_talk?'true':'false':''} />
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
