<script>
    import { Card, Button, Alert } from '$lib/components/ui';
    import { CircleAlert } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage, hasApiMessage } from '$lib/apiMessages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';

    let { data } = $props();

    // Our own codes have translations. A payment provider's message comes in
    // Korean only, so it is shown as-is to Korean readers and replaced by the
    // generic message (with the provider's code) for everyone else.
    let failureText = $derived(
        hasApiMessage(data.code) ? apiMessage(data)
            : (languageTag() === 'ko' && data.message) ? data.message
            : m.eventRegister_paymentError());
</script>

<svelte:head>
    <title>{m.payment_failedTitle()}</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card class="max-w-md w-full">
        <div class="text-center">
            <div class="flex justify-center mb-4">
                <CircleAlert class="w-16 h-16 text-red-500" />
            </div>
            <h1 class="text-2xl font-bold text-gray-900 mb-2">{m.payment_failedTitle()}</h1>
            <p class="text-gray-600 mb-4">{m.payment_cancelledMessage()}</p>

            {#if data.code || data.message}
                <Alert color="red" class="mb-6 text-left">
                    {#if data.code}<span class="font-medium">{data.code}:</span>{/if} {failureText}
                </Alert>
            {/if}

            {#if data.orderId}
                <p class="text-sm text-gray-500 mb-6">
                    {m.payment_orderNumber()}: {data.orderId}
                </p>
            {/if}

            <div class="flex flex-col gap-2">
                <Button color="primary" onclick={() => history.back()}>
                    {m.payment_tryAgain()}
                </Button>
                <Button color="light" href="/">
                    {m.common_home()}
                </Button>
            </div>
        </div>
    </Card>
</div>
