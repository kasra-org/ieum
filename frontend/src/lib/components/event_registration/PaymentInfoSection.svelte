<script>
    import { CreditCard } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { formatDate } from '$lib/utils.js';
    import ReceiptButtons from '$lib/components/ReceiptButtons.svelte';
    import { Button } from '$lib/components/ui';
    import { getStudentStatusLabel } from '$lib/utils.js';

    let { payment, attendee = null, event = null } = $props();

    // What this attendee owes, from their category. payment_status is 'free',
    // 'paid' or 'pending'; a pending registration has no payment record yet,
    // which is exactly the case that needs a pay button rather than an empty tab.
    const fee = $derived(attendee?.registration_fee ?? 0);
    const isUnpaid = $derived(attendee?.payment_status === 'pending');
    const isFree = $derived(attendee?.payment_status === 'free' || !fee);

    function formatAmount(amount) {
        const formattedAmount = amount.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
        return languageTag() === 'ko' ? `${formattedAmount}원` : `KRW ${formattedAmount}`;
    }

    function getStatusText(status) {
        switch (status) {
            case 'completed':
                return m.paymentHistory_statusCompleted();
            case 'cancelled':
                return m.paymentHistory_statusCancelled();
            case 'pending':
                return m.paymentHistory_statusPending();
            default:
                return status;
        }
    }

    function getStatusColor(status) {
        switch (status) {
            case 'completed':
                return 'text-green-600';
            case 'cancelled':
                return 'text-red-600';
            case 'pending':
                return 'text-orange-500';
            default:
                return 'text-gray-600';
        }
    }
</script>

<div class="flex items-center gap-2 mb-6">
    <CreditCard class="w-6 h-6 text-gray-700" />
    <h2 class="text-xl font-bold text-gray-900">{m.myRegistration_paymentInfo()}</h2>
</div>

<div class="space-y-4 pl-8">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {#if event?.has_tiered_fees}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.eventRegister_selectTier()}</p>
                <p class="text-base text-gray-900">{getStudentStatusLabel(attendee?.student_status, m)}</p>
            </div>
        {/if}
        <div>
            <p class="text-sm font-medium text-gray-500">{m.eventDetail_registrationFee()}</p>
            <p class="text-base text-gray-900">
                {isFree ? m.eventDetail_registrationFeeFree() : formatAmount(fee)}
            </p>
        </div>
        {#if !payment && !isFree}
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_paymentStatus()}</p>
                <p class="text-base font-bold {isUnpaid ? 'text-orange-500' : 'text-green-600'}">
                    {isUnpaid ? m.paymentHistory_statusPending() : m.paymentHistory_statusCompleted()}
                </p>
            </div>
        {/if}
    </div>

    {#if isUnpaid}
        <div class="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <p class="mb-3 text-sm text-gray-700">{m.myRegistration_paymentPendingNotice()}</p>
            <Button color="primary" href="/event/{event?.id}/register">{m.eventRegister_payNow()}</Button>
        </div>
    {/if}
</div>

{#if payment}
    <div class="space-y-4 pl-8 mt-6 pt-6 border-t border-gray-200">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_paymentDate()}</p>
                <p class="text-base text-gray-900">{formatDate(payment.checkout_date)}</p>
            </div>
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_receiptNumber()}</p>
                <p class="text-base text-gray-900">{payment.number}</p>
            </div>
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_paymentAmount()}</p>
                <p class="text-base text-gray-900">{formatAmount(payment.amount)}</p>
            </div>
            <div>
                <p class="text-sm font-medium text-gray-500">{m.myRegistration_paymentStatus()}</p>
                <p class="text-base font-bold {getStatusColor(payment.status)}">{getStatusText(payment.status)}</p>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-wrap gap-4 mt-8 pt-6 border-t border-gray-200">
            <ReceiptButtons {payment} size="md" />
        </div>
    </div>
{:else if !isUnpaid && isFree}
    <div class="pl-8">
        <p class="text-gray-600">{m.myRegistration_noPayment()}</p>
    </div>
{/if}
