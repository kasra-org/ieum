<script>
    import { Button } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { openReceiptWindow, openCardReceiptWindow, isCardPayment } from '$lib/utils.js';

    /**
     * @type {{ payment: { number: string, payment_type: string }, size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' }}
     */
    let { payment, size = 'xs' } = $props();
</script>

<Button {size} color="light" onclick={() => openReceiptWindow(payment.number)}>{m.paymentHistory_printReceipt()}</Button>
{#if isCardPayment(payment)}
    <Button {size} color="light" onclick={() => openCardReceiptWindow(payment.number)}>{m.paymentHistory_printCreditCardSlip()}</Button>
{/if}
