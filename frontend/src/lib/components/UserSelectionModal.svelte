<script>
    import { Modal, Button, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import { getDisplayInstitute, getDisplayName } from '$lib/utils.js';
    import * as m from '$lib/paraglide/messages.js';
    import SearchableUserList from '$lib/components/SearchableUserList.svelte';

    let {
        open = $bindable(false),
        title,
        userList = [],
        action,
        submitLabel,
        error = $bindable(''),
        onSubmit
    } = $props();

    let selectedUserId = $state(null);

    // Reset state when modal closes
    $effect(() => {
        if (!open) {
            selectedUserId = null;
            error = '';
        }
    });

    // Custom display functions for user objects
    function getUserEmail(user) {
        return user.email || user.user?.email || user.user_email || '';
    }
</script>

<Modal bind:open={open} {title} size="lg">
    <form method="POST" {action} use:enhance={onSubmit}>
        <input type="hidden" name="id" value={selectedUserId || ''} />

        <div class="mb-6">
            <SearchableUserList
                items={userList}
                bind:selectedId={selectedUserId}
                maxHeight="max-h-80"
                showChangeButton={false}
                getItemName={getDisplayName}
                getItemInstitute={getDisplayInstitute}
                getItemEmail={getUserEmail}
            />
        </div>

        {#if error}
            <Alert color="red" class="mb-6">{error}</Alert>
        {/if}

        <div class="flex justify-center gap-2">
            <Button color="alternative" type="button" onclick={() => open = false}>{m.common_cancel()}</Button>
            <Button color="primary" type="submit" disabled={!selectedUserId}>{submitLabel}</Button>
        </div>
    </form>
</Modal>
