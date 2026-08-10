<script>
    import { Button } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { openReceiptWindow, openCardReceiptWindow, isCardPayment } from '$lib/utils.js';

    /**
     * @type {{ payment: { number: string, payment_type: string, amount: number }, size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' }}
     */
    let { payment, size = 'xs' } = $props();

    // Nothing was charged, so there is no receipt to issue - a waived speaker
    // fee is the usual case. The button stays visible but inert, which reads
    // better than the row quietly losing its action.
    const nothingToReceipt = $derived(!payment?.amount);
</script>

<Button {size} color="light" disabled={nothingToReceipt}
    onclick={() => openReceiptWindow(payment.number)}>{m.paymentHistory_printReceipt()}</Button>
{#if isCardPayment(payment)}
    <Button {size} color="light" disabled={nothingToReceipt}
        onclick={() => openCardReceiptWindow(payment.number)}>{m.paymentHistory_printCreditCardSlip()}</Button>
{/if}
