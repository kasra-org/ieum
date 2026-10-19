<script>
    import { enhance } from '$app/forms';
    import { Alert, Button } from '$lib/components/ui';
    import ReceiptView from '$lib/components/ReceiptView.svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';

    let { data } = $props();

    // Sending is offered only to an admin of the event (the API says so by
    // handing over payment_id), and only for a completed payment.
    let sending = $state(false);
    let notice = $state(null);
    const afterSend = () => {
        sending = true;
        notice = null;
        return async ({ result }) => {
            sending = false;
            notice = result.type === 'success'
                ? { color: 'green', message: m.transactions_receiptSent() }
                : { color: 'red', message: apiMessage(result.data ?? result.error, m.transactions_receiptSendError) };
        };
    };
</script>

<ReceiptView payment={data.payment}>
    {#snippet tools()}
        {#if data.payment?.payment_id}
            <form method="post" action="?/send" use:enhance={afterSend}
                  class="flex flex-wrap items-center justify-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
                <input type="hidden" name="event_id" value={data.payment.event_id} />
                <input type="hidden" name="payment_id" value={data.payment.payment_id} />
                <span class="text-gray-600">{m.receipt_sendTo({ email: data.payment.send_to || '—' })}</span>
                <Button color="primary" size="sm" type="submit"
                        disabled={sending || !data.payment.send_to || data.payment.status !== 'completed'}>
                    {sending ? '...' : m.transactions_sendReceipt()}
                </Button>
            </form>
            {#if notice}
                <Alert color={notice.color} class="mt-3">{notice.message}</Alert>
            {/if}
        {/if}
    {/snippet}
</ReceiptView>
