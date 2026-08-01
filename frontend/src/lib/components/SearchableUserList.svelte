<script>
    import { Input, Button } from '$lib/components/ui';
    import { Search } from '@lucide/svelte';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import * as m from '$lib/paraglide/messages.js';

    let {
        items = [],
        selectedId = $bindable(null),
        placeholder = '',
        noResultsMessage = '',
        maxHeight = 'max-h-48',
        showChangeButton = true,
        // Custom display functions (optional)
        getItemName = null,
        getItemSecondaryName = null,
        getItemInstitute = null,
        getItemEmail = null,
        // Optional callback when an item is selected (receives the full item object)
        onSelect = null
    } = $props();

    let searchKeyword = $state('');

    // Default display functions
    function defaultGetName(item) {
        return getDisplayName(item);
    }

    function defaultGetInstitute(item) {
        return getDisplayInstitute(item);
    }

    function defaultGetEmail(item) {
        return item.email || item.user?.email || item.user_email || '';
    }

    // Use custom functions if provided, otherwise use defaults
    function getName(item) {
        return getItemName ? getItemName(item) : defaultGetName(item);
    }

    function getInstitute(item) {
        return getItemInstitute ? getItemInstitute(item) : defaultGetInstitute(item);
    }

    function getSecondaryName(item) {
        return getItemSecondaryName ? getItemSecondaryName(item) : '';
    }

    function getEmail(item) {
        return getItemEmail ? getItemEmail(item) : defaultGetEmail(item);
    }

    function getNameWithInstitute(item) {
        const name = getName(item);
        const institute = getInstitute(item);
        if (institute) {
            return `${name} (${institute})`;
        }
        return name;
    }

    // Filter items based on search keyword
    let filteredItems = $derived(
        items.filter(item => {
            if (!searchKeyword.trim()) return true;
            const searchLower = searchKeyword.toLowerCase();
            const name = getName(item).toLowerCase();
            const secondaryName = getSecondaryName(item).toLowerCase();
            const institute = getInstitute(item).toLowerCase();
            const email = getEmail(item).toLowerCase();
            return name.includes(searchLower) ||
                   secondaryName.includes(searchLower) ||
                   institute.includes(searchLower) ||
                   email.includes(searchLower);
        })
    );

    // Get selected item object
    let selectedItem = $derived(
        selectedId ? items.find(item => item.id === selectedId) : null
    );

    function selectItem(item) {
        selectedId = item.id;
        if (onSelect) {
            onSelect(item);
        }
    }

    function clearSelection() {
        selectedId = null;
        searchKeyword = '';
    }

    // Reset search when selection changes
    $effect(() => {
        if (selectedId) {
            searchKeyword = '';
        }
    });
</script>

{#if selectedItem && showChangeButton}
    <!-- Show selected item -->
    <div class="border border-blue-300 bg-blue-50 rounded-lg p-3">
        <div class="flex justify-between items-center">
            <div>
                <div class="font-medium text-gray-900">{getNameWithInstitute(selectedItem)}</div>
                {#if getSecondaryName(selectedItem)}<div class="text-sm text-gray-500">{getSecondaryName(selectedItem)}</div>{/if}
                <div class="text-sm text-gray-600">{getEmail(selectedItem)}</div>
            </div>
            <Button color="light" size="xs" onclick={clearSelection}>{m.common_change()}</Button>
        </div>
    </div>
{:else}
    <!-- Search and select -->
    <div class="relative mb-2">
        <Input
            type="text"
            bind:value={searchKeyword}
            placeholder={placeholder || m.userSelection_searchPlaceholder()}
            class="pl-10"
        />
        <Search class="w-4 h-4 absolute left-3 top-3 text-gray-400" />
    </div>
    <div class="border border-gray-200 rounded-lg {maxHeight} overflow-y-auto">
        {#if filteredItems.length === 0}
            <div class="p-4 text-center text-gray-500">
                {noResultsMessage || m.userSelection_noResults()}
            </div>
        {:else}
            {#each filteredItems as item}
                <button
                    type="button"
                    onclick={() => selectItem(item)}
                    class="w-full text-left px-4 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors {selectedId === item.id ? 'bg-blue-50 hover:bg-blue-100' : ''}"
                >
                    <div class="font-medium text-gray-900">{getNameWithInstitute(item)}</div>
                    {#if getSecondaryName(item)}<div class="text-sm text-gray-500">{getSecondaryName(item)}</div>{/if}
                    <div class="text-sm text-gray-500">{getEmail(item)}</div>
                </button>
            {/each}
        {/if}
    </div>
{/if}
