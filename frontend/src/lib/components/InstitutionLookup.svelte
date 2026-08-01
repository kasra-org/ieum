<script>
  import { tick } from 'svelte';
  import { Input, Label, Alert, Modal, Button, ButtonGroup } from '$lib/components/ui';
  import { Search } from '@lucide/svelte';
  import * as m from '$lib/paraglide/messages.js';
  import { languageTag } from '$lib/paraglide/runtime.js';
  import { enhance, deserialize } from '$app/forms';

  let { value = $bindable(''), displayName = $bindable(''), error = null, required = false, institution_resolved = null } = $props();

  // Display value (institution name for UI)
  let displayValue = $state('');

  // Reference to the hidden input for event dispatching
  let hiddenInput;

  // Get display name based on current language
  function getDisplayName(institution) {
    const lang = languageTag();
    if (lang === 'ko' && institution.name_ko) {
      return institution.name_ko;
    }
    return institution.name_en;
  }

  // Get secondary name for display (opposite of primary)
  function getSecondaryName(institution) {
    const lang = languageTag();
    if (lang === 'ko' && institution.name_ko) {
      return institution.name_en; // Show English as secondary when Korean is primary
    }
    return institution.name_ko; // Show Korean as secondary when English is primary
  }

  // Initialize and update displayValue from server-resolved institution
  $effect(() => {
    if (institution_resolved) {
      displayValue = getDisplayName(institution_resolved);
    }
  });

  // Sync displayValue with displayName bindable prop
  $effect(() => {
    displayName = displayValue;
  });

  let modal_open = $state(false);
  let modal_step = $state('search'); // 'search' or 'create'
  let search_query = $state('');
  let filtered_suggestions = $state([]);
  let new_name_en = $state('');
  let new_name_ko = $state('');
  let create_error = $state('');

  // Reset modal state when closed (preserves value and displayValue)
  $effect(() => {
    if (!modal_open) {
      modal_step = 'search';
      search_query = '';
      filtered_suggestions = [];
      new_name_en = '';
      new_name_ko = '';
      create_error = '';
    }
  });

  async function filterInstitutions() {
    if (!search_query || search_query.length < 2) {
      filtered_suggestions = [];
      return;
    }

    try {
      const formData = new FormData();
      formData.append('search', search_query);

      const response = await fetch('?/search_institutions', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const result = deserialize(await response.text());
        if (result.type === 'success' && result.data?.success) {
          filtered_suggestions = result.data.institutions;
        } else {
          filtered_suggestions = [];
        }
      } else {
        filtered_suggestions = [];
      }
    } catch (error) {
      console.error('Failed to search institutions:', error);
      filtered_suggestions = [];
    }
  }

  function goToCreateStep() {
    modal_step = 'create';
    // Pre-fill the first field based on current language
    const lang = languageTag();
    if (lang === 'ko') {
      new_name_ko = search_query;
      new_name_en = '';
    } else {
      new_name_en = search_query;
      new_name_ko = '';
    }
    create_error = '';
  }

  function goBackToSearch() {
    modal_step = 'search';
    new_name_en = '';
    new_name_ko = '';
    create_error = '';
  }

  let searchTimeout;
  function handleSearchInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      filterInstitutions();
    }, 300); // Debounce by 300ms
  }

  async function selectInstitution(institution) {
    value = institution.id; // Store institution ID as number
    displayValue = getDisplayName(institution);

    // Wait for DOM to update before triggering events
    await tick();

    // Trigger events for form validation using direct reference
    if (hiddenInput) {
      hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
      hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // Close modal after dispatching events (effect will reset modal state)
    modal_open = false;
  }

  const handleCreateInstitution = () => {
    return async ({ result, update }) => {
      if (result.type === 'success' && result.data?.success) {
        value = result.data.institution.id; // Store institution ID as number
        displayValue = getDisplayName(result.data.institution);

        // Wait for DOM to update before triggering events
        await tick();

        // Trigger events for form validation using direct reference
        if (hiddenInput) {
          hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
          hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Close modal after dispatching events (effect will reset modal state)
        modal_open = false;
      } else {
        create_error = result.data?.error || 'Failed to create institution';
      }
    };
  };

  function openModal() {
    modal_open = true;
    modal_step = 'search';
    search_query = displayValue || '';
    if (search_query.length >= 2) {
      filterInstitutions();
    }
  }

  function closeModal() {
    // Setting modal_open to false triggers the effect that resets modal state
    // while preserving the selected institute value and displayValue
    modal_open = false;
  }
</script>

<Label for="institute" class="block mb-2">
  {m.form_institute()} {#if required}<span class="text-red-500">*</span>{/if}
</Label>
<input type="hidden" name="institute" bind:this={hiddenInput} value={value} />
<ButtonGroup class="w-full">
  <Input
    id="institute_display"
    type="text"
    value={displayValue}
    readonly
    placeholder={m.form_institutePlaceholder()}
    class="cursor-pointer"
    onclick={openModal}
  />
  <Button color="primary" onclick={openModal} class="min-w-48">
    <Search class="w-4 h-4 me-2" />
    {m.form_findInstitution()}
  </Button>
</ButtonGroup>

{#if error}
  <Alert color="red" class="mt-3">
    <p class="text-sm">{error}</p>
  </Alert>
{/if}

<Modal title={modal_step === 'search' ? m.form_findInstitution() : m.form_createInstitution()} bind:open={modal_open} size="md" dismissable={false}>
  <div class="space-y-4">
    {#if modal_step === 'search'}
      <!-- Search Step -->
      <div>
        <Label for="search_institution" class="block mb-2">{m.form_searchInstitution()}</Label>
        <Input
          id="search_institution"
          type="text"
          bind:value={search_query}
          oninput={handleSearchInput}
          placeholder={m.form_institutePlaceholder()}
          autofocus
        />
      </div>

      <!-- Search Results -->
      {#if filtered_suggestions.length > 0}
        <div class="border border-gray-200 rounded-lg overflow-hidden max-h-80 overflow-y-auto">
          {#each filtered_suggestions as suggestion}
            <button
              type="button"
              class="w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors"
              onclick={() => selectInstitution(suggestion)}
            >
              <div class="font-medium text-gray-900">{getDisplayName(suggestion)}</div>
              {#if getSecondaryName(suggestion)}
                <div class="text-sm text-gray-600 mt-1">{getSecondaryName(suggestion)}</div>
              {/if}
            </button>
          {/each}
        </div>
      {/if}

      <!-- No Results Message -->
      {#if search_query.length >= 2 && filtered_suggestions.length === 0}
        <div class="border border-gray-200 rounded-lg p-4 bg-gray-50 text-center">
          <p class="text-sm text-gray-600 mb-3">{m.form_noInstitutionsFound()}</p>
          <Button color="primary" onclick={goToCreateStep}>
            {m.form_createInstitution()}
          </Button>
        </div>
      {/if}

      <!-- Instructions -->
      {#if search_query.length < 2}
        <p class="text-sm text-gray-500 text-center py-4">
          {m.form_institutionSearchHint()}
        </p>
      {/if}
    {:else}
      <!-- Create Step -->
      <form id="create_institution_form" method="post" action="?/create_institution" use:enhance={handleCreateInstitution}>
        <div class="space-y-4">
          {#if languageTag() === 'ko'}
            <!-- Korean name first when UI is Korean -->
            <div>
              <Label for="new_name_ko" class="block mb-2">{m.admin_institutionNameKo()}</Label>
              <Input
                id="new_name_ko"
                name="name_ko"
                type="text"
                bind:value={new_name_ko}
                placeholder={m.admin_institutionNameKo()}
                autofocus
              />
            </div>
            <div>
              <Label for="new_name_en" class="block mb-2">{m.admin_institutionNameEn()} <span class="text-red-500">*</span></Label>
              <Input
                id="new_name_en"
                name="name_en"
                type="text"
                bind:value={new_name_en}
                placeholder={m.admin_institutionNameEn()}
                required
              />
            </div>
          {:else}
            <!-- English name first when UI is English -->
            <div>
              <Label for="new_name_en" class="block mb-2">{m.admin_institutionNameEn()} <span class="text-red-500">*</span></Label>
              <Input
                id="new_name_en"
                name="name_en"
                type="text"
                bind:value={new_name_en}
                placeholder={m.admin_institutionNameEn()}
                required
                autofocus
              />
            </div>
            <div>
              <Label for="new_name_ko" class="block mb-2">{m.admin_institutionNameKo()}</Label>
              <Input
                id="new_name_ko"
                name="name_ko"
                type="text"
                bind:value={new_name_ko}
                placeholder={m.admin_institutionNameKo()}
              />
            </div>
          {/if}
          {#if create_error}
            <Alert color="red">
              <p class="text-sm">{create_error}</p>
            </Alert>
          {/if}
        </div>
      </form>
    {/if}
  </div>

  {#snippet footer()}
    <div class="flex justify-between w-full">
      {#if modal_step === 'create'}
        <Button color="alternative" type="button" onclick={goBackToSearch}>{m.common_goBack()}</Button>
        <Button color="primary" type="submit" form="create_institution_form">{m.form_createInstitution()}</Button>
      {:else}
        <Button color="alternative" type="button" onclick={closeModal}>{m.common_cancel()}</Button>
      {/if}
    </div>
  {/snippet}
</Modal>
