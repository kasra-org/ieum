<script>
    let { data } = $props();

    import { Button, Alert, Spinner } from '$lib/components/ui';
    import { CircleCheck, Mail } from '@lucide/svelte';
    import { goto } from '$app/navigation';
    import * as m from '$lib/paraglide/messages.js';

    let verifying = $state(false);
    let success = $state(false);
    let errorMessage = $state('');

    const verifyEmail = async () => {
        verifying = true;
        errorMessage = '';

        const response = await fetch('?/verify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            body: new URLSearchParams({
                key: data.key
            }),
        });

        if (!response.ok || response.status !== 200) {
            verifying = false;
            const rtn = await response.json();
            errorMessage = rtn.error?.message || 'An error occurred during verification.';
        } else {
            success = true;
            // Show success message briefly, then redirect to login
            setTimeout(() => {
                goto('/login');
            }, 2000);
        }
    };
</script>

<svelte:head>
    <title>{m.verifyEmail_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="container mx-auto max-w-2xl my-10 px-3 sm:px-7">
    <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
        <div class="text-center mb-6">
            {#if success}
                <CircleCheck class="mx-auto mb-4 text-green-600 w-16 h-16" />
            {:else if verifying}
                <div class="flex justify-center mb-4">
                    <Spinner size="12" color="blue" />
                </div>
            {:else}
                <Mail class="mx-auto mb-4 text-blue-600 w-16 h-16" />
            {/if}

            <h1 class="text-3xl font-bold text-gray-900 mb-3">
                {m.verifyEmail_title()}
            </h1>

            <p class="text-base text-gray-600">
                {#if success}
                    {m.verifyEmail_successMessage()}
                {:else if verifying}
                    {m.verifyEmail_verifying()}
                {:else}
                    {m.verifyEmail_description()}
                {/if}
            </p>
        </div>

        {#if errorMessage}
            <Alert color="red" class="mb-6" dismissable>
                <p>{errorMessage}</p>
            </Alert>
        {/if}

        {#if !verifying && !success}
            <div class="flex justify-center">
                <Button onclick={verifyEmail} color="primary" size="lg" class="w-full sm:w-auto">
                    {m.verifyEmail_submit()}
                </Button>
            </div>
        {/if}
    </div>
</div>
