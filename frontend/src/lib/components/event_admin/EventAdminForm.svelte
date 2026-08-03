<script>
    import { Label, Input, Select, Checkbox } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
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
        registration_fee: null,
        onsite_registration_fee: null,
        onsite_registration_fee_undergraduate: null,
        onsite_registration_fee_graduate: null,
        undergraduate_enabled: false,
        registration_fee_undergraduate: null,
        graduate_enabled: false,
        registration_fee_graduate: null,
        invitation_code: '',
        accepts_abstract: false,
        abstract_submission_type: 'internal',
        external_abstract_url: '',
        abstract_deadline: '',
        capacity_abstract: 0,
        max_votes: 2,
    }) } = $props();

    // Local so the price field can appear only when its tier is enabled; the
    // checkboxes still post their own values.
    let undergraduate_enabled = $state(data.undergraduate_enabled ?? false);
    let graduate_enabled = $state(data.graduate_enabled ?? false);

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
<!-- All three categories priced in one block. PI/non-academic used to sit in a
     separate "standard fee" field, which made it easy to price the student tiers
     and leave PI at zero without noticing. -->
<div class="mb-6 rounded-lg border border-gray-200 p-4">
    <p class="mb-1 text-sm font-medium">{m.eventForm_registrationFees()}</p>
    <p class="mb-4 text-sm text-gray-500">{m.eventForm_registrationFeesHelp()}</p>

    <div class="mb-4">
        <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" name="undergraduate_enabled" bind:checked={undergraduate_enabled}
                class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
            <span class="text-sm font-medium">{m.eventForm_tierUndergraduate()}</span>
        </label>
        {#if undergraduate_enabled}
            <div class="mt-2 ps-6">
                <Input type="number" id="registration_fee_undergraduate" name="registration_fee_undergraduate"
                    value={data.registration_fee_undergraduate} step="1" min="0" placeholder="0" />
            </div>
        {/if}
    </div>

    <div class="mb-4">
        <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" name="graduate_enabled" bind:checked={graduate_enabled}
                class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500" />
            <span class="text-sm font-medium">{m.eventForm_tierGraduate()}</span>
        </label>
        {#if graduate_enabled}
            <div class="mt-2 ps-6">
                <Input type="number" id="registration_fee_graduate" name="registration_fee_graduate"
                    value={data.registration_fee_graduate} step="1" min="0" placeholder="0" />
            </div>
        {/if}
    </div>

    <div>
        <p class="mb-2 text-sm font-medium">{m.eventForm_tierPiNonAcademic()}</p>
        <div class="ps-6">
            <Input type="number" id="registration_fee" name="registration_fee" value={data.registration_fee} step="1" min="0" placeholder="0" />
            <p class="mt-1 text-sm text-gray-500">{m.eventForm_tierPiNonAcademicHelp()}</p>
        </div>
    </div>
</div>
<div class="mb-6 rounded-lg border border-gray-200 p-4">
    <p class="mb-1 text-sm font-medium">{m.eventForm_onsiteRegistrationFee()}</p>
    <p class="mb-4 text-sm text-gray-500">{m.eventForm_onsiteRegistrationFeeHelp()}</p>

    {#if undergraduate_enabled}
        <div class="mb-4">
            <p class="mb-2 text-sm font-medium">{m.eventForm_tierUndergraduate()}</p>
            <div class="ps-6">
                <Input type="number" id="onsite_registration_fee_undergraduate" name="onsite_registration_fee_undergraduate"
                    value={data.onsite_registration_fee_undergraduate} step="1" min="0" placeholder="0" />
            </div>
        </div>
    {/if}
    {#if graduate_enabled}
        <div class="mb-4">
            <p class="mb-2 text-sm font-medium">{m.eventForm_tierGraduate()}</p>
            <div class="ps-6">
                <Input type="number" id="onsite_registration_fee_graduate" name="onsite_registration_fee_graduate"
                    value={data.onsite_registration_fee_graduate} step="1" min="0" placeholder="0" />
            </div>
        </div>
    {/if}
    <div>
        <p class="mb-2 text-sm font-medium">{m.eventForm_tierPiNonAcademic()}</p>
        <div class="ps-6">
            <Input type="number" id="onsite_registration_fee" name="onsite_registration_fee" value={data.onsite_registration_fee} step="1" min="0" placeholder="0" />
        </div>
    </div>
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