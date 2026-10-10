<script>
    // SearchableUserList for lists too big to hand the browser whole: the
    // search runs on the server (a paginated relay route under /api), and
    // only the first `limit` matches are shown. The picked row is kept, so
    // the selection survives the next search replacing the results.
    import { Input, Button, Spinner } from '$lib/components/ui';
    import { Search } from '@lucide/svelte';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import * as m from '$lib/paraglide/messages.js';

    let {
        // Relay route answering {items, total}, e.g. `/api/event/7/attendees`.
        url,
        // Extra query parameters: the picker's exclusions (has_abstract=false...).
        params = {},
        limit = 20,
        selectedId = $bindable(null),
        // The row object picked, for callers that need more than its id.
        selectedItem = $bindable(null),
        placeholder = '',
        // For a <Label for=...> outside: the id of the search box.
        inputId = undefined,
        noResultsMessage = '',
        maxHeight = 'max-h-48',
        showChangeButton = true,
        getItemId = (item) => item.id,
        getItemName = null,
        getItemSecondaryName = null,
        getItemInstitute = null,
        getItemEmail = null,
        onSelect = null
    } = $props();

    let searchKeyword = $state('');
    let items = $state([]);
    let loading = $state(false);
    // A failed search is not an empty one: say which it was.
    let failed = $state(false);
    let sequence = 0;
    let timer;

    const getName = (item) => getItemName ? getItemName(item) : getDisplayName(item);
    const getInstitute = (item) => getItemInstitute ? getItemInstitute(item) : getDisplayInstitute(item);
    const getSecondaryName = (item) => getItemSecondaryName ? getItemSecondaryName(item) : '';
    const getEmail = (item) => getItemEmail
        ? getItemEmail(item)
        : (item.email || item.user?.email || item.user_email || '');

    function nameWithInstitute(item) {
        const name = getName(item);
        const institute = getInstitute(item);
        return institute ? `${name} (${institute})` : name;
    }

    async function load() {
        const mine = ++sequence;
        loading = true;
        try {
            const query = new URLSearchParams({ limit: String(limit) });
            for (const [key, value] of Object.entries(params)) {
                if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
            }
            const term = searchKeyword.trim();
            if (term) query.set('search', term);
            const response = await fetch(`${url}?${query}`, { headers: { Accept: 'application/json' } });
            const body = response.ok ? await response.json() : { items: [] };
            if (mine === sequence) {
                items = body.items ?? [];
                failed = !response.ok;
            }
        } catch {
            // Offline or dropped: no stale matches, and an error, not "none".
            if (mine === sequence) {
                items = [];
                failed = true;
            }
        } finally {
            if (mine === sequence) loading = false;
        }
    }

    // First results at once, then a moment after typing stops.
    let first = true;
    $effect(() => {
        searchKeyword;
        JSON.stringify(params);
        clearTimeout(timer);
        if (first) {
            first = false;
            load();
        } else {
            timer = setTimeout(load, 250);
        }
        // Closed before the pause ended: no request for a list that is gone.
        return () => clearTimeout(timer);
    });

    // The picked row stays in view: once the search box clears after a pick,
    // the first matches may not include it.
    let shownItems = $derived(
        selectedItem && !searchKeyword.trim() && !items.some(item => getItemId(item) === getItemId(selectedItem))
            ? [selectedItem, ...items]
            : items
    );

    function selectItem(item) {
        selectedId = getItemId(item);
        selectedItem = item;
        // As the in-page picker did: a pick clears the search.
        searchKeyword = '';
        onSelect?.(item);
    }

    function clearSelection() {
        selectedId = null;
        selectedItem = null;
        searchKeyword = '';
    }

    // Cleared from outside (a modal reset): drop the kept row too.
    $effect(() => {
        if (selectedId === null || selectedId === undefined) selectedItem = null;
    });
</script>

{#if selectedItem && showChangeButton}
    <div class="border border-blue-300 bg-blue-50 rounded-lg p-3">
        <div class="flex justify-between items-center">
            <div>
                <div class="font-medium text-gray-900">{nameWithInstitute(selectedItem)}</div>
                {#if getSecondaryName(selectedItem)}<div class="text-sm text-gray-500">{getSecondaryName(selectedItem)}</div>{/if}
                <div class="text-sm text-gray-600">{getEmail(selectedItem)}</div>
            </div>
            <Button color="light" size="xs" onclick={clearSelection}>{m.common_change()}</Button>
        </div>
    </div>
{:else}
    <div class="relative mb-2">
        <Input
            id={inputId}
            type="text"
            bind:value={searchKeyword}
            onkeydown={(e) => { if (e.key === 'Enter') e.preventDefault(); }}
            placeholder={placeholder || m.userSelection_searchPlaceholder()}
            class="pl-10"
        />
        <Search class="w-4 h-4 absolute left-3 top-3 text-gray-400" />
    </div>
    <div class="border border-gray-200 rounded-lg {maxHeight} overflow-y-auto">
        {#if loading && shownItems.length === 0}
            <div class="p-4 flex justify-center"><Spinner size="6" /></div>
        {:else}
            <!-- Above the pick it still shows: a search on its way, or one that failed. -->
            {#if loading}
                <div class="p-2 flex justify-center"><Spinner size="4" /></div>
            {:else if failed}
                <div class="p-4 text-center text-gray-500">{m.common_error()}</div>
            {:else if shownItems.length === 0}
                <div class="p-4 text-center text-gray-500">{noResultsMessage || m.userSelection_noResults()}</div>
            {/if}
            {#each shownItems as item (getItemId(item))}
                <button
                    type="button"
                    onclick={() => selectItem(item)}
                    class="w-full text-left px-4 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors {selectedId === getItemId(item) ? 'bg-blue-50 hover:bg-blue-100' : ''}"
                >
                    <div class="font-medium text-gray-900">{nameWithInstitute(item)}</div>
                    {#if getSecondaryName(item)}<div class="text-sm text-gray-500">{getSecondaryName(item)}</div>{/if}
                    <div class="text-sm text-gray-500">{getEmail(item)}</div>
                </button>
            {/each}
        {/if}
    </div>
{/if}
