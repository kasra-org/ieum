<script>
    import { Input, Checkbox, Label } from '$lib/components/ui';
    import { Search, UserMinus } from '@lucide/svelte';
    import { getDisplayName, getDisplayInstitute } from '$lib/utils.js';
    import * as m from '$lib/paraglide/messages.js';

    let {
        users = [],
        selectedIds = $bindable([]),
        label = '',
        placeholder = '',
        description = '',
        maxResults = 20,
        required = false
    } = $props();

    let searchTerm = $state('');

    let filteredUsers = $derived(
        users.filter(user => {
            if (!searchTerm.trim()) return true;
            const searchLower = searchTerm.toLowerCase();
            const name = getDisplayName(user).toLowerCase();
            const institute = getDisplayInstitute(user).toLowerCase();
            const email = (user.email || '').toLowerCase();
            return name.includes(searchLower) || institute.includes(searchLower) || email.includes(searchLower);
        }).slice(0, maxResults)
    );

    let selectedUsers = $derived(
        users.filter(user => selectedIds.includes(user.id))
    );

    function toggleUser(userId) {
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
            placeholder={placeholder || m.organizers_searchPlaceholder()}
            class="pl-10"
        />
        <Search class="w-4 h-4 absolute left-3 top-3 text-gray-400" />
    </div>

    <!-- User List -->
    {#if searchTerm.trim()}
        <div class="border border-gray-200 rounded-lg max-h-48 overflow-y-auto">
            {#if filteredUsers.length === 0}
                <div class="p-4 text-center text-gray-500">{m.userSelection_noResults()}</div>
            {:else}
                {#each filteredUsers as user}
                    <button
                        type="button"
                        onclick={() => toggleUser(user.id)}
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
