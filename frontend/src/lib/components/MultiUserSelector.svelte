<script>
    import { Input, Checkbox, Label, Spinner } from '$lib/components/ui';
    import { Search, UserMinus } from '@lucide/svelte';
    import { getDisplayName, getDisplayInstitute } from '$lib/utils.js';
    import * as m from '$lib/paraglide/messages.js';

    let {
        // Either the whole list to pick from (`users`), or a relay route that
        // searches accounts on the server (`url`, e.g. '/api/admin/users')
        // when there are too many to hand the browser.
        users = [],
        url = null,
        params = {},
        selectedIds = $bindable([]),
        // Server mode: every user picked so far, by id. Bind it from the
        // parent when this sits in a modal - a modal unmounts its content,
        // and the chips of a selection kept across reopening need the rows.
        pickedUsers = $bindable({}),
        label = '',
        placeholder = '',
        description = '',
        maxResults = 20,
        required = false
    } = $props();

    let searchTerm = $state('');

    // Server mode: the current matches. They are replaced on each search, so
    // the chips read names from pickedUsers instead - otherwise a picked user
    // whose name no longer matches the search box would show up as nothing.
    let remoteUsers = $state([]);
    let loading = $state(false);
    // A failed search is not an empty one: say which it was.
    let failed = $state(false);
    let sequence = 0;
    let timer;

    async function load(term) {
        const mine = ++sequence;
        loading = true;
        try {
            const query = new URLSearchParams({ limit: String(maxResults), search: term });
            for (const [key, value] of Object.entries(params)) {
                if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
            }
            const response = await fetch(`${url}?${query}`, { headers: { Accept: 'application/json' } });
            const body = response.ok ? await response.json() : { items: [] };
            if (mine === sequence) {
                remoteUsers = body.items ?? [];
                failed = !response.ok;
            }
        } catch {
            // Offline or dropped: show no matches rather than stale ones.
            if (mine === sequence) {
                remoteUsers = [];
                failed = true;
            }
        } finally {
            if (mine === sequence) loading = false;
        }
    }

    // Search a moment after typing stops; nothing is listed until something
    // is typed, as in the users-array mode.
    $effect(() => {
        if (!url) return;
        const term = searchTerm.trim();
        JSON.stringify(params);
        clearTimeout(timer);
        if (!term) {
            ++sequence;
            remoteUsers = [];
            failed = false;
            loading = false;
            return;
        }
        // Spinner rather than "no results" while the answer is pending.
        loading = true;
        timer = setTimeout(() => load(term), 250);
        // Closed before the pause ended: no request for a list that is gone.
        return () => clearTimeout(timer);
    });

    let filteredUsers = $derived(
        url ? remoteUsers : users.filter(user => {
            if (!searchTerm.trim()) return true;
            const searchLower = searchTerm.toLowerCase();
            const name = getDisplayName(user).toLowerCase();
            const institute = getDisplayInstitute(user).toLowerCase();
            const email = (user.email || '').toLowerCase();
            return name.includes(searchLower) || institute.includes(searchLower) || email.includes(searchLower);
        }).slice(0, maxResults)
    );

    let selectedUsers = $derived(
        url
            ? selectedIds.map(id => pickedUsers[id]).filter(Boolean)
            : users.filter(user => selectedIds.includes(user.id))
    );

    function toggleUser(user) {
        const userId = user.id;
        if (url) pickedUsers = { ...pickedUsers, [userId]: user };
        if (selectedIds.includes(userId)) {
            selectedIds = selectedIds.filter(id => id !== userId);
        } else {
            selectedIds = [...selectedIds, userId];
        }
    }

    function removeUser(userId) {
        selectedIds = selectedIds.filter(id => id !== userId);
    }
</script>

<div class="mb-6">
    {#if label}
        <Label class="block mb-2">{label} {#if required}<span class="text-red-500">*</span>{/if}</Label>
    {/if}

    <!-- Selected Users -->
    {#if selectedUsers.length > 0}
        <div class="flex flex-wrap gap-2 mb-3">
            {#each selectedUsers as user}
                <span class="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                    {getDisplayName(user)}
                    <button type="button" onclick={() => removeUser(user.id)} class="hover:text-blue-600">
                        <UserMinus class="w-4 h-4" />
                    </button>
                </span>
            {/each}
        </div>
    {/if}

    <!-- Search Users -->
    <div class="relative mb-2">
        <Input
            type="text"
            bind:value={searchTerm}
            onkeydown={(e) => { if (e.key === 'Enter') e.preventDefault(); }}
            placeholder={placeholder || m.organizers_searchPlaceholder()}
            class="pl-10"
        />
        <Search class="w-4 h-4 absolute left-3 top-3 text-gray-400" />
    </div>

    <!-- User List -->
    {#if searchTerm.trim()}
        <div class="border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
            {#if loading && filteredUsers.length === 0}
                <div class="p-4 flex justify-center"><Spinner size="6" /></div>
            {:else if filteredUsers.length === 0}
                <div class="p-4 text-center text-gray-500">{url && failed ? m.common_error() : m.userSelection_noResults()}</div>
            {:else}
                {#each filteredUsers as user (user.id)}
                    <button
                        type="button"
                        onclick={() => toggleUser(user)}
                        class="w-full text-left px-4 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 transition-colors {selectedIds.includes(user.id) ? 'bg-blue-50' : ''}"
                    >
                        <div class="flex items-center gap-2">
                            <Checkbox checked={selectedIds.includes(user.id)} />
                            <div>
                                <div class="font-medium text-gray-900">{getDisplayName(user)} {getDisplayInstitute(user) ? `(${getDisplayInstitute(user)})` : ''}</div>
                                <div class="text-sm text-gray-500">{user.email}</div>
                            </div>
                        </div>
                    </button>
                {/each}
            {/if}
        </div>
    {/if}

    {#if description}
        <span class="text-sm text-gray-600">* {description}</span>
    {/if}
</div>
