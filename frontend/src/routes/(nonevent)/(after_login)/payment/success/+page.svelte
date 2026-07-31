<script>
    import { onMount } from 'svelte';
    import { enhance } from '$app/forms';
    import { Card, Button, Alert, Spinner } from 'flowbite-svelte';
    import { CheckCircleSolid, ExclamationCircleSolid } from 'flowbite-svelte-icons';
    import * as m from '$lib/paraglide/messages.js';

    let { data, form } = $props();

    let status = $state('processing'); // 'processing', 'success', 'error'
    let errorMessage = $state('');
    let paymentResult = $state(null);
    let eventId = $state(null);
    let formElement = $state(null);

    function formatAmount(amount) {
        if (!amount) return '';
        return amount.toLocaleString('ko-KR') + '원';
    }

    // Handle form result
    $effect(() => {
        if (form) {
            if (form.success) {
                sessionStorage.removeItem('pendingPayment');
                paymentResult = form.data;
                status = 'success';
            } else if (form.error) {
                status = 'error';
                errorMessage = form.error;
            }
        }
    });

    onMount(() => {
        // NicePay: the backend approved the payment before redirecting here, so
        // the record was already loaded server-side.
        if (data.provider === 'nicepay') {
            sessionStorage.removeItem('pendingPayment');
            if (data.nicepayResult) {
                paymentResult = data.nicepayResult;
                status = 'success';
            } else {
                status = 'error';
                errorMessage = data.nicepayError || 'Payment not found';
            }
            return;
        }

        // Check if this is a PayPal payment result (stored directly in sessionStorage)
        const storedPayPalResult = sessionStorage.getItem('paymentResult');
        if (storedPayPalResult) {
            try {
                paymentResult = JSON.parse(storedPayPalResult);
                sessionStorage.removeItem('paymentResult');
                sessionStorage.removeItem('pendingPayment');
                status = 'success';
                return;
            } catch (e) {
                // Continue with Toss flow if parsing fails
            }
        }

        // Toss Payments flow: Validate required parameters
        if (!data.paymentKey || !data.orderId || !data.amount) {
            status = 'error';
            errorMessage = 'Missing payment confirmation parameters';
            return;
        }

        // Retrieve payment data from sessionStorage
        const storedData = sessionStorage.getItem('pendingPayment');
        if (!storedData) {
            status = 'error';
            errorMessage = 'Payment data not found. Please try again.';
            return;
        }

        let paymentData;
        try {
            paymentData = JSON.parse(storedData);
        } catch (e) {
            status = 'error';
            errorMessage = 'Invalid payment data';
            return;
        }

        eventId = paymentData.eventId;

        // Auto-submit the form after setting eventId
        setTimeout(() => {
            if (formElement) {
                formElement.requestSubmit();
            }
        }, 100);
    });
</script>

<svelte:head>
    <title>{status === 'success' ? m.payment_successTitle() : status === 'error' ? m.payment_failedTitle() : m.common_loading()}</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 flex items-center justify-center p-4">
    <Card class="max-w-md w-full p-6">
        {#if status === 'processing'}
            <div class="text-center py-8">
                <Spinner size="12" class="mx-auto mb-4" />
                <h1 class="text-xl font-semibold text-gray-900 mb-2">{m.common_loading()}</h1>
                <p class="text-gray-600">{m.payment_confirmingPayment?.() || 'Confirming your payment...'}</p>
            </div>

            <!-- Hidden form for server-side confirmation -->
            <form
                bind:this={formElement}
                method="POST"
                action="?/confirm"
                use:enhance
                class="hidden"
            >
                <input type="hidden" name="paymentKey" value={data.paymentKey || ''} />
                <input type="hidden" name="orderId" value={data.orderId || ''} />
                <input type="hidden" name="amount" value={data.amount || ''} />
                <input type="hidden" name="eventId" value={eventId || ''} />
            </form>
        {:else if status === 'success'}
            <div class="text-center">
                <div class="flex justify-center mb-4">
                    <CheckCircleSolid class="w-16 h-16 text-green-500" />
                </div>
                <h1 class="text-2xl font-bold text-gray-900 mb-2">{m.payment_successTitle()}</h1>
                <p class="text-gray-600 mb-6">{m.payment_successMessage()}</p>

                {#if paymentResult}
                    <div class="bg-gray-50 rounded-lg p-4 mb-6 text-left">
                        <div class="flex justify-between py-2">
                            <span class="text-gray-600">{m.payment_orderNumber()}</span>
                            <span class="font-medium">{paymentResult.number}</span>
                        </div>
                        <div class="flex justify-between py-2">
                            <span class="text-gray-600">{m.payment_amount()}</span>
                            <span class="font-medium">{formatAmount(paymentResult.amount)}</span>
                        </div>
                        {#if paymentResult.event_name}
                            <div class="flex justify-between py-2">
                                <span class="text-gray-600">{m.payment_eventName()}</span>
                                <span class="font-medium">{paymentResult.event_name}</span>
                            </div>
                        {/if}
                    </div>
                {/if}

                <div class="flex flex-col gap-2">
                    {#if paymentResult?.event_id}
                        <Button color="primary" href="/event/{paymentResult.event_id}/registration">
                            {m.payment_viewRegistration()}
                        </Button>
                        <Button color="light" href="/event/{paymentResult.event_id}">
                            {m.payment_returnToEvent()}
                        </Button>
                    {/if}
                </div>
            </div>
        {:else}
            <div class="text-center">
                <div class="flex justify-center mb-4">
                    <ExclamationCircleSolid class="w-16 h-16 text-red-500" />
                </div>
                <h1 class="text-2xl font-bold text-gray-900 mb-2">{m.payment_failedTitle()}</h1>
                <p class="text-gray-600 mb-4">{m.payment_failedMessage()}</p>

                {#if errorMessage}
                    <Alert color="red" class="mb-6 text-left">
                        {errorMessage}
                    </Alert>
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
        {/if}
    </Card>
</div>
