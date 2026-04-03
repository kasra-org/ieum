<script>
    import { Heading, TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Card } from 'flowbite-svelte';
    import { Button, Modal, Label, Input, Select, Textarea, Alert } from 'flowbite-svelte';
    import { Tabs, TabItem } from 'flowbite-svelte';
    import { UserEditSolid, UserRemoveSolid, CheckOutline } from 'flowbite-svelte-icons';
    import { enhance } from '$app/forms';
    import { error } from '@sveltejs/kit';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import SearchableUserList from '$lib/components/SearchableUserList.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';

    let { data } = $props();

    let searchTermSpeaker = $state('');
    let selectedSpeakers = $state([]);
    let currentPage = $state(1);
    const itemsPerPage = 10;

    let filteredSpeakers = $derived(
        data.speakers.filter((item) => {
            const searchLower = searchTermSpeaker.toLowerCase();
            return item.name.toLowerCase().includes(searchLower) ||
                   (item.korean_name && item.korean_name.toLowerCase().includes(searchLower));
        })
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermSpeaker;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filteredSpeakers.length / itemsPerPage));
    let paginatedSpeakers = $derived(
        filteredSpeakers.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }

    let speaker_modal = $state(false);
    let attendee_selection_modal = $state(false);
    let remove_speaker_modal = $state(false);
    let selected_speaker = $state(null);

    // Form field state for speaker modal
    let speakerName = $state('');
    let speakerKoreanName = $state('');
    let speakerEmail = $state('');
    let speakerAffiliation = $state('');
    let speakerAffiliationKo = $state('');
    let speakerIsDomestic = $state(false);
    let speakerType = $state('invited'); // Default to 'invited' speaker type

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

    function selectAttendeeForSpeaker(attendee) {
        speakerName = attendee.name || '';
        speakerKoreanName = attendee.korean_name || '';
        speakerEmail = attendee.user?.email || attendee.user_email || '';
        speakerAffiliation = attendee.institute || '';
        speakerAffiliationKo = attendee.institute_ko || '';
    }

    const addSpeakerModal = () => {
        selected_speaker = null;
        speakerName = '';
        speakerKoreanName = '';
        speakerEmail = '';
        speakerAffiliation = '';
        speakerAffiliationKo = '';
        speakerIsDomestic = false;
        speakerType = 'invited';
        speaker_modal = true;
    };
    const modifySpeakerModal = (id) => {
        selected_speaker = data.speakers.find((item) => item.id === id);
        speakerName = selected_speaker.name;
        speakerKoreanName = selected_speaker.korean_name || '';
        speakerEmail = selected_speaker.email;
        speakerAffiliation = selected_speaker.affiliation;
        speakerAffiliationKo = selected_speaker.affiliation_ko || '';
        speakerIsDomestic = selected_speaker.is_domestic || false;
        speakerType = selected_speaker.type;
        speaker_modal = true;
    };
    const removeSpeakerModal = (id) => {
        selected_speaker = data.speakers.find((item) => item.id === id);
        remove_speaker_modal = true;
    };

    let update_speaker_error = $state('');
    const afterUpdateSpeaker = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                speaker_modal = false;
                update_speaker_error = '';
            } else {
                update_speaker_error = result.error.message;
            }
        }
    };

    let remove_speaker_error = $state('');
    const afterRemoveSpeaker = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({ reset: false });
                remove_speaker_modal = false;
                remove_speaker_error = '';
            } else {
                remove_speaker_error = result.error.message;
            }
        }
    };

    const format_type = (type) => {
        switch (type) {
            case 'keynote':
                return m.speakerType_keynote();
            case 'invited':
                return m.speakerType_invited();
            case 'contributed':
                return m.speakerType_contributed();
            case 'short':
                return m.speakerType_short();
            case 'poster':
                return m.speakerType_poster();
            default:
                return m.speakerType_unknown();
        }
    };


    let send_email_modal = $state(false);
    const showSendEmailModal = () => {
        send_email_modal = true;
    };
    let emailRecipients = $derived(
        selectedSpeakers.map(id => data.speakers.find(a => a.id === id)?.email).filter(Boolean).join("; ")
    );
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.speakers_title()}</Heading>
<p class="font-light mb-6">{m.speakers_description()}</p>
<div class="flex justify-end gap-2">
    <Button color="primary" size="sm" disabled={selectedSpeakers.length === 0} onclick={showSendEmailModal}>{m.speakers_sendEmailToSelected()}</Button>
    <Button color="primary" size="sm" onclick={addSpeakerModal}>{m.speakers_addSpeaker()}</Button>
</div>
<TableSearch placeholder={m.speakers_searchPlaceholder()} hoverable={true} bind:inputValue={searchTermSpeaker}>
    <TableHead>
        <TableHeadCell class="w-1"><Checkbox
            checked={selectedSpeakers.length > 0 && selectedSpeakers.length === data.speakers.length}
            intermediate={
                selectedSpeakers.length > 0 && (selectedSpeakers.length < data.speakers.length)
            }
            onclick={(e) => {
                if (e.target.checked) {
                    selectedSpeakers = filteredSpeakers.map(a => a.id);
                } else {
                    selectedSpeakers = [];
                }
            }}
        /></TableHeadCell>
        <TableHeadCell>{m.speakers_name()}</TableHeadCell>
        <TableHeadCell>{m.speakers_email()}</TableHeadCell>
        <TableHeadCell>{m.speakers_affiliation()}</TableHeadCell>
        <TableHeadCell>{m.speakers_domestic()}</TableHeadCell>
        <TableHeadCell>{m.speakers_type()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.speakers_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedSpeakers as row}
            <TableBodyRow>
                <TableBodyCell><Checkbox checked={selectedSpeakers.includes(row.id)} onclick={(e) => {
                    if (e.target.checked) {
                        selectedSpeakers = [...selectedSpeakers, row.id];
                    } else {
                        selectedSpeakers = selectedSpeakers.filter(a => a !== row.id);
                    }
                }} /></TableBodyCell>
                <TableBodyCell>
                    <div>{row.name}</div>
                    {#if row.korean_name}<div class="text-sm text-gray-500">{row.korean_name}</div>{/if}
                </TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>
                    <div>{row.affiliation}</div>
                    {#if row.affiliation_ko}<div class="text-sm text-gray-500">{row.affiliation_ko}</div>{/if}
                </TableBodyCell>
                <TableBodyCell>{#if row.is_domestic}<CheckOutline class="w-4 h-4 text-green-500 inline mr-2" />{/if}</TableBodyCell>
                <TableBodyCell>{format_type(row.type)}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.speakers_updateSpeaker()}>
                            <Button color="none" size="none" onclick={() => modifySpeakerModal(row.id)}>
                                <UserEditSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.speakers_removeSpeaker()}>
                            <Button color="none" size="none" onclick={() => removeSpeakerModal(row.id)}>
                                <UserRemoveSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filteredSpeakers.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="7" class="text-center">{m.speakers_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />

<Modal bind:open={speaker_modal} title={selected_speaker ? m.speakers_updateSpeaker() : m.speakers_addSpeaker()} size="lg">
    <form method="POST" action={selected_speaker?"?/update_speaker":"?/add_speaker"} use:enhance={afterUpdateSpeaker}>
        {#if selected_speaker}
            <input type="hidden" name="id" value={selected_speaker.id} />
        {:else}
            <div class="mb-6">
                <Label class="block mb-2">{m.speakers_selectAttendee()}</Label>
                <SearchableUserList
                    items={data.attendees}
                    maxHeight="max-h-60"
                    showChangeButton={false}
                    getItemSecondaryName={getAttendeeSecondaryName}
                    getItemEmail={getAttendeeEmail}
                    onSelect={selectAttendeeForSpeaker}
                />
            </div>
            <hr class="mb-6 border-gray-200" />
        {/if}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
                <Label for="name" class="block mb-2">{m.speakers_name()} ({m.language_english()}) <span class="text-red-500">*</span></Label>
                <Input id="name" name="name" type="text" bind:value={speakerName} required />
            </div>
            <div>
                <Label for="korean_name" class="block mb-2">{m.speakers_name()} ({m.language_korean()})</Label>
                <Input id="korean_name" name="korean_name" type="text" bind:value={speakerKoreanName} />
            </div>
        </div>
        <div class="mb-6">
            <Label for="email" class="block mb-2">{m.speakers_email()} <span class="text-red-500">*</span></Label>
            <Input id="email" name="email" type="email" bind:value={speakerEmail} required />
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
                <Label for="affiliation" class="block mb-2">{m.speakers_affiliation()} ({m.language_english()}) <span class="text-red-500">*</span></Label>
                <Input id="affiliation" name="affiliation" type="text" bind:value={speakerAffiliation} required />
            </div>
            <div>
                <Label for="affiliation_ko" class="block mb-2">{m.speakers_affiliation()} ({m.language_korean()})</Label>
                <Input id="affiliation_ko" name="affiliation_ko" type="text" bind:value={speakerAffiliationKo} />
            </div>
        </div>
        <div class="mb-6">
            <Checkbox bind:checked={speakerIsDomestic}>
                {m.speakers_isDomestic()}
            </Checkbox>
            <input type="hidden" name="is_domestic" value={speakerIsDomestic ? 'true' : 'false'} />
        </div>
        <div class="mb-6">
            <Label for="type" class="block mb-2">{m.speakers_type()}</Label>
            <Select id="type" name="type" items={[
                { value: 'keynote', name: m.speakerType_keynote() },
                { value: 'invited', name: m.speakerType_invited() },
                { value: 'contributed', name: m.speakerType_contributed() },
                { value: 'short', name: m.speakerType_short() },
                { value: 'poster', name: m.speakerType_poster() },
            ]} bind:value={speakerType} />
        </div>
        {#if update_speaker_error}
            <Alert color="red" class="mb-6">{update_speaker_error}</Alert>
        {/if}
        <div class="flex justify-center">
            <Button color="primary" type="submit">{selected_speaker ? m.speakers_update() : m.speakers_add()}</Button>
        </div>
    </form>
</Modal>

<Modal bind:open={remove_speaker_modal} title={m.speakers_removeSpeaker()} size="sm">
    <form method="POST" action="?/remove_speaker" use:enhance={afterRemoveSpeaker}>
        <input type="hidden" name="id" value={selected_speaker?selected_speaker.id:''} />
        <p class="mb-6">{m.speakers_removeConfirm()}</p>
        {#if remove_speaker_error}
            <Alert color="red" class="mb-6">{remove_speaker_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.speakers_remove()}</Button>
            <Button color="dark" type="button" onclick={() => remove_speaker_modal = false}>{m.speakers_cancel()}</Button>
        </div>
    </form>
</Modal>

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />
