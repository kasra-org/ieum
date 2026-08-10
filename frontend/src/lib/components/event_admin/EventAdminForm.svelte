<script>
    import { Label, Input, Select, Checkbox } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { ChevronUp, ChevronDown, Plus, Trash2 } from '@lucide/svelte';
    import MarkdownEditor from '$lib/components/MarkdownEditor.svelte';
    import VenueSelector from '$lib/components/VenueSelector.svelte';

    let { data = $bindable({
        name: '',
        description: '',
        category: 'conference',
        organizers: '',
        venue: '',
        venue_ko: '',
        venue_address: '',
        venue_address_ko: '',
        venue_latitude: null,
        venue_longitude: null,
        main_languages: [],
        start_date: '',
        end_date: '',
        deadline: '',
        capacity: 0,
        registration_categories: [],
        invitation_code: '',
        accepts_abstract: false,
        abstract_submission_type: 'internal',
        external_abstract_url: '',
        abstract_deadline: '',
        capacity_abstract: 0,
        max_votes: 2,
    }) } = $props();

    // The whole list posts as one JSON field, so adds, renames, reorders and
    // removals all arrive together and the server can tell what was dropped.
    let categories = $state(
        (data.registration_categories ?? []).map(c => ({
            id: c.id ?? null,
            name: c.name ?? '',
            name_ko: c.name_ko ?? '',
            fee: c.fee ?? 0,
            onsite_fee: c.onsite_fee ?? null,
        }))
    );
    // A brand new event has none yet; start it on the standard three. An
    // existing event that has had them all removed is free, and stays that way.
    if (categories.length === 0 && data.id === undefined) {
        categories = [
            { id: null, name: 'Undergraduate student', name_ko: '학부생', fee: 0, onsite_fee: null },
            { id: null, name: 'Graduate student / Postdoc', name_ko: '대학원생/박사후연구원', fee: 0, onsite_fee: null },
            { id: null, name: 'PI / Non-academic', name_ko: 'PI / 일반', fee: 0, onsite_fee: null },
        ];
    }

    function addCategory() {
        categories = [...categories, { id: null, name: '', name_ko: '', fee: 0, onsite_fee: null }];
    }

    function removeCategory(index) {
        categories = categories.filter((_, i) => i !== index);
    }

    function moveCategory(index, delta) {
        const target = index + delta;
        if (target < 0 || target >= categories.length) return;
        const next = [...categories];
        [next[index], next[target]] = [next[target], next[index]];
        categories = next;
    }

    // Create local reactive state for properties to enable two-way binding
    let description = $state(data.description ?? '');
    let venue = $state(data.venue ?? '');
    let venue_ko = $state(data.venue_ko ?? '');
    let venue_address = $state(data.venue_address ?? '');
    let venue_address_ko = $state(data.venue_address_ko ?? '');
    let venue_latitude = $state(data.venue_latitude ?? null);
    let venue_longitude = $state(data.venue_longitude ?? null);
    let main_languages = $state(data.main_languages || []);
    let accepts_abstract = $state(data.accepts_abstract ?? false);
    let abstract_submission_type = $state(data.abstract_submission_type ?? 'internal');
    let external_abstract_url = $state(data.external_abstract_url ?? '');
    let invitation_code = $state(data.invitation_code?.toUpperCase() || '');
    let capacity_abstract = $state(data.capacity_abstract ?? 0);
    let max_votes = $state(data.max_votes ?? 2);

    // Keep properties in sync with data object
    $effect(() => {
        data.description = description;
        data.venue = venue;
        data.venue_ko = venue_ko;
        data.venue_address = venue_address;
        data.venue_address_ko = venue_address_ko;
        data.venue_latitude = venue_latitude;
        data.venue_longitude = venue_longitude;
        data.main_languages = main_languages;
        data.accepts_abstract = accepts_abstract;
        data.abstract_submission_type = abstract_submission_type;
        data.external_abstract_url = external_abstract_url;
        data.invitation_code = invitation_code;
        data.capacity_abstract = capacity_abstract;
        data.max_votes = max_votes;
    });

    // Helper functions for language checkboxes
    function toggleLanguage(lang) {
        if (main_languages.includes(lang)) {
            main_languages = main_languages.filter(l => l !== lang);
        } else {
            main_languages = [...main_languages, lang];
        }
    }
</script>

<div class="mb-6">
    <Label for="name" class="block mb-2">{m.eventForm_eventName()} <span class="text-red-500">*</span></Label>
    <Input type="text" id="name" name="name" value={data.name} />
</div>
<div class="mb-6">
    <Label for="link_info" class="block mb-2">{m.eventForm_eventPageUrl()}</Label>
    <Input type="text" id="link_info" name="link_info" value={data.link_info} placeholder="https://example.com/event" />
    <span class="text-sm">* {m.eventForm_eventPageUrlHelp()}</span>
</div>
<div class="mb-6">
    <MarkdownEditor
        bind:value={description}
        id="description"
        name="description"
        label={m.eventForm_description()}
        placeholder={m.eventForm_descriptionPlaceholder()}
        rows={8}
    />
</div>
<div class="mb-6">
    <Label for="category" class="block mb-2">{m.eventForm_category()} <span class="text-red-500">*</span></Label>
    <Select id="category" name="category" value={data.category} items={[
        { value: 'workshop', name: m.eventCategory_workshop() },
        { value: 'hackathon', name: m.eventCategory_hackathon() },
        { value: 'symposium', name: m.eventCategory_symposium() },
        { value: 'meeting', name: m.eventCategory_meeting() },
        { value: 'conference', name: m.eventCategory_conference() }
    ]} />
</div>
<div class="mb-6">
    <Label class="block mb-2">{m.eventForm_mainLanguages()} <span class="text-red-500">*</span></Label>
    <div class="flex gap-4">
        <Checkbox
            checked={main_languages.includes('ko')}
            onchange={() => toggleLanguage('ko')}
        >
            {m.language_korean()}
        </Checkbox>
        <Checkbox
            checked={main_languages.includes('en')}
            onchange={() => toggleLanguage('en')}
        >
            {m.language_english()}
        </Checkbox>
    </div>
    {#if main_languages.length === 0}
        <p class="text-sm text-red-600 mt-2">{m.eventForm_mainLanguagesRequired()}</p>
    {/if}
    <input type="hidden" name="main_languages" value={JSON.stringify(main_languages)} />
</div>
<div class="mb-6">
    <VenueSelector
        bind:venueName={venue}
        bind:venueNameKo={venue_ko}
        bind:venueAddress={venue_address}
        bind:venueAddressKo={venue_address_ko}
        bind:venueLatitude={venue_latitude}
        bind:venueLongitude={venue_longitude}
        required={true}
    />
</div>
<div class="mb-6">
    <Label for="start_date" class="block mb-2">{m.eventForm_dates()} <span class="text-red-500">*</span></Label>
    <div class="flex flex-col md:flex-row justify-stretch gap-4">
        <div class="w-full">
            <Input type="date" id="start_date" name="start_date" value={data.start_date} />
        </div>
        <div class="flex w-3 justify-center items-center">
            <span>-</span>
        </div>
        <div class="w-full">
            <Input type="date" id="end_date" name="end_date" value={data.end_date} />
        </div>
    </div>
</div>
<div class="mb-6">
    <Label for="registration_deadline" class="block mb-2">{m.eventForm_registrationDeadline()}</Label>
    <Input type="date" id="registration_deadline" name="registration_deadline" value={data.registration_deadline} />
    <span class="text-sm">* {m.eventForm_registrationDeadlineHelp()}</span>
</div>
<div class="mb-6">
    <Label for="capacity" class="block mb-2">{m.eventForm_registrationCapacity()}</Label>
    <Input type="number" id="capacity" name="capacity" value={data.capacity} />
    <span class="text-sm">* {m.eventForm_registrationCapacityHelp()}</span>
</div>
<!-- One row per category: its names, what it costs, and what a walk-in pays.
     The whole list is submitted together as JSON. -->
<div class="mb-6 rounded-lg border border-gray-200 p-4">
    <p class="mb-1 text-sm font-medium">{m.eventForm_categories()}</p>
    <p class="mb-4 text-sm text-gray-500">{m.eventForm_categoriesHelp()}</p>

    <input type="hidden" name="registration_categories" value={JSON.stringify(categories)} />

    <div class="space-y-3">
        {#each categories as category, index (index)}
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div>
                        <Label class="mb-1 block text-xs">{m.eventForm_categoryName()}</Label>
                        <Input type="text" bind:value={category.name} placeholder="Undergraduate student" />
                    </div>
                    <div>
                        <Label class="mb-1 block text-xs">{m.eventForm_categoryNameKo()}</Label>
                        <Input type="text" bind:value={category.name_ko} placeholder="학부생" />
                    </div>
                    <div>
                        <Label class="mb-1 block text-xs">{m.eventForm_categoryFee()}</Label>
                        <Input type="number" bind:value={category.fee} step="1" min="0" placeholder="0" />
                    </div>
                    <div>
                        <Label class="mb-1 block text-xs">{m.eventForm_categoryOnsiteFee()}</Label>
                        <Input type="number" bind:value={category.onsite_fee} step="1" min="0" placeholder="0" />
                    </div>
                </div>
                <div class="mt-2 flex items-center justify-end gap-2">
                    <button type="button" class="cursor-pointer rounded px-2 py-1 text-sm text-gray-600 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-40"
                        onclick={() => moveCategory(index, -1)} disabled={index === 0} aria-label={m.eventForm_categoryMoveUp()}>
                        <ChevronUp class="h-4 w-4" />
                    </button>
                    <button type="button" class="cursor-pointer rounded px-2 py-1 text-sm text-gray-600 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-40"
                        onclick={() => moveCategory(index, 1)} disabled={index === categories.length - 1} aria-label={m.eventForm_categoryMoveDown()}>
                        <ChevronDown class="h-4 w-4" />
                    </button>
                    <button type="button" class="cursor-pointer rounded px-2 py-1 text-sm text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                        onclick={() => removeCategory(index)}>
                        <Trash2 class="mr-1 inline h-4 w-4" />{m.eventForm_categoryRemove()}
                    </button>
                </div>
            </div>
        {/each}
    </div>

    <button type="button" class="mt-3 cursor-pointer rounded-lg border border-dashed border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        onclick={addCategory}>
        <Plus class="mr-1 inline h-4 w-4" />{m.eventForm_categoryAdd()}
    </button>
    {#if categories.length === 0}
        <p class="mt-3 text-sm text-gray-500">{m.eventForm_categoriesNoneIsFree()}</p>
    {/if}
    <p class="mt-3 text-sm text-gray-500">{m.eventForm_categoryRemoveNote()}</p>
</div>

<div class="mb-6">
    <Label for="invitation_code" class="block mb-2">{m.eventForm_invitationCode()}</Label>
    <Input type="text" id="invitation_code" name="invitation_code" bind:value={invitation_code} oninput={(e) => { invitation_code = e.target.value.toUpperCase(); }} placeholder="" class="uppercase" />
    <span class="text-sm">* {m.eventForm_invitationCodeHelp()}</span>
</div>
<div class="mb-6">
    <Label for="accepts_abstract" class="block mb-2">{m.eventForm_enableAbstract()}</Label>
    <Select id="accepts_abstract" name="accepts_abstract" bind:value={accepts_abstract} items={[
        { value: true, name: m.eventForm_yes() },
        { value: false, name: m.eventForm_no() }
    ]} />
</div>
{#if accepts_abstract}
<div class="mb-6">
    <Label for="abstract_submission_type" class="block mb-2">{m.eventForm_abstractSubmissionType()}</Label>
    <Select id="abstract_submission_type" name="abstract_submission_type" bind:value={abstract_submission_type} items={[
        { value: 'internal', name: m.eventForm_abstractInternal() },
        { value: 'external', name: m.eventForm_abstractExternal() }
    ]} />
</div>

{#if abstract_submission_type === 'external'}
<div class="mb-6">
    <Label for="external_abstract_url" class="block mb-2">{m.eventForm_externalAbstractUrl()}</Label>
    <Input type="url" id="external_abstract_url" name="external_abstract_url" bind:value={external_abstract_url} placeholder="https://example.com/submit-abstract" />
</div>
{:else}
<div class="mb-6">
    <Label for="abstract_deadline" class="block mb-2">{m.eventForm_abstractDeadline()}</Label>
    <Input type="date" id="abstract_deadline" name="abstract_deadline" value={data.abstract_deadline} />
    <span class="text-sm">* {m.eventForm_abstractDeadlineHelp()}</span>
</div>

<div class="mb-6">
    <Label for="capacity_abstract" class="block mb-2">{m.eventForm_abstractCapacity()}</Label>
    <Input type="number" id="capacity_abstract" name="capacity_abstract" bind:value={capacity_abstract} />
    <span class="text-sm">* {m.eventForm_abstractCapacityHelp()}</span>
</div>

<div class="mb-6">
    <Label for="max_votes" class="block mb-2">{m.eventForm_maxVotes()}</Label>
    <Input type="number" id="max_votes" name="max_votes" bind:value={max_votes} />
    <span class="text-sm">* {m.eventForm_maxVotesHelp()}</span>
</div>
{/if}
{/if}