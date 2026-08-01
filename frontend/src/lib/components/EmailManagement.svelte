<script>
    import { Alert, Badge, Button, Heading, Input, Label, Modal } from '$lib/components/ui';
    import { onMount } from 'svelte';
    import * as m from '$lib/paraglide/messages.js';

    let { emails = [], csrf_token = '', onPrimaryChanged = () => {} } = $props();

    let emailList = $state(emails);

    onMount(() => {
        refreshEmails();
    });
    let newEmail = $state('');
    let loading = $state(false);
    let successMessage = $state('');
    let errorMessage = $state('');
    let showRemoveModal = $state(false);
    let emailToRemove = $state('');

    async function apiCall(method, body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf_token,
            },
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch('/_allauth/browser/v1/account/email', options);
        const data = await response.json();
        return { ok: response.ok, data };
    }

    async function refreshEmails() {
        const result = await apiCall('GET');
        if (result.ok && result.data?.data) {
            emailList = result.data.data;
        }
    }

    async function handleAddEmail() {
        if (!newEmail || loading) return;
        loading = true;
        successMessage = '';
        errorMessage = '';
        try {
            const result = await apiCall('POST', { email: newEmail });
            if (result.ok) {
                newEmail = '';
                successMessage = m.profile_emailAddSuccess();
                await refreshEmails();
            } else {
                errorMessage = result.data?.errors?.[0]?.message || m.profile_emailError();
            }
        } catch {
            errorMessage = m.profile_emailError();
        }
        loading = false;
    }

    function confirmRemove(email) {
        emailToRemove = email;
        showRemoveModal = true;
    }

    async function handleRemoveEmail() {
        if (!emailToRemove || loading) return;
        loading = true;
        showRemoveModal = false;
        successMessage = '';
        errorMessage = '';
        try {
            const result = await apiCall('DELETE', { email: emailToRemove });
            if (result.ok) {
                successMessage = m.profile_emailRemoveSuccess();
                await refreshEmails();
            } else {
                errorMessage = result.data?.errors?.[0]?.message || m.profile_emailError();
            }
        } catch {
            errorMessage = m.profile_emailError();
        }
        emailToRemove = '';
        loading = false;
    }

    async function handleSetPrimary(email) {
        if (loading) return;
        loading = true;
        successMessage = '';
        errorMessage = '';
        try {
            const result = await apiCall('PATCH', { email, primary: true });
            if (result.ok) {
                successMessage = m.profile_emailPrimarySuccess();
                await refreshEmails();
                onPrimaryChanged(email);
            } else {
                errorMessage = result.data?.errors?.[0]?.message || m.profile_emailError();
            }
        } catch {
            errorMessage = m.profile_emailError();
        }
        loading = false;
    }

    async function handleResendVerification(email) {
        if (loading) return;
        loading = true;
        successMessage = '';
        errorMessage = '';
        try {
            const result = await apiCall('PUT', { email });
            if (result.ok) {
                successMessage = m.profile_emailResendSuccess();
            } else {
                errorMessage = result.data?.errors?.[0]?.message || m.profile_emailError();
            }
        } catch {
            errorMessage = m.profile_emailError();
        }
        loading = false;
    }
</script>

<Label class="block mb-2 text-dark">{m.profile_emailAddresses()}</Label>

{#if successMessage}
    <Alert color="green" class="mb-4" dismissable onclose={() => successMessage = ''}>{successMessage}</Alert>
{/if}
{#if errorMessage}
    <Alert color="red" class="mb-4" dismissable onclose={() => errorMessage = ''}>{errorMessage}</Alert>
{/if}

<div class="divide-y divide-gray-100">
    {#each emailList as emailItem}
        <div class="flex flex-col sm:flex-row sm:items-center justify-between py-3 gap-2">
            <div class="flex items-center gap-2 flex-wrap">
                <span class="text-gray-900">{emailItem.email}</span>
                {#if emailItem.primary}
                    <Badge color="blue">{m.profile_emailPrimary()}</Badge>
                {/if}
                {#if emailItem.verified}
                    <Badge color="green">{m.profile_emailVerified()}</Badge>
                {:else}
                    <Badge color="yellow">{m.profile_emailUnverified()}</Badge>
                {/if}
            </div>
            <div class="flex gap-2 flex-wrap">
                {#if !emailItem.primary && emailItem.verified}
                    <Button size="xs" color="light" disabled={loading} onclick={() => handleSetPrimary(emailItem.email)}>
                        {m.profile_emailSetPrimary()}
                    </Button>
                {/if}
                {#if !emailItem.verified}
                    <Button size="xs" color="light" disabled={loading} onclick={() => handleResendVerification(emailItem.email)}>
                        {m.profile_emailResendVerification()}
                    </Button>
                {/if}
                {#if !emailItem.primary}
                    <Button size="xs" color="red" outline disabled={loading} onclick={() => confirmRemove(emailItem.email)}>
                        {m.profile_emailRemove()}
                    </Button>
                {/if}
            </div>
        </div>
    {/each}
</div>

<div class="flex gap-2 mt-4">
    <Input type="email" bind:value={newEmail} placeholder={m.profile_emailAddPlaceholder()} class="flex-1" />
    <Button color="primary" onclick={handleAddEmail} disabled={loading || !newEmail}>
        {m.profile_emailAdd()}
    </Button>
</div>

<Modal bind:open={showRemoveModal} size="sm" autoclose={false} class="w-full">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">{m.profile_emailRemoveConfirmTitle()}</h3>
    <p class="text-gray-600 mb-6">{m.profile_emailRemoveConfirmMessage()}</p>
    <p class="text-gray-900 font-medium mb-6">{emailToRemove}</p>
    <div class="flex justify-end gap-3">
        <Button color="alternative" onclick={() => showRemoveModal = false}>{m.common_cancel()}</Button>
        <Button color="red" onclick={handleRemoveEmail}>{m.profile_emailRemove()}</Button>
    </div>
</Modal>
