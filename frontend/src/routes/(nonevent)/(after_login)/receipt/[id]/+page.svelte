<script>
    import { Button, Alert, Select } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag, setLanguageTag } from '$lib/paraglide/runtime.js';
    import { formatDate, formatDateRange } from '$lib/utils.js';

    let { data } = $props();

    // Language selector state
    let selectedLanguage = $state(languageTag());

    const languageOptions = [
        { value: 'en', name: 'English' },
        { value: 'ko', name: '한국어' }
    ];

    function changeLanguage(event) {
        const lang = event.target.value;
        setLanguageTag(lang);
        selectedLanguage = lang;
    }

    let payment = $derived(data.payment);
    let contactEmail = $derived(data.contact_email);

    // Use selectedLanguage to trigger reactivity when language changes
    function formatAmount(amount) {
        if (!amount) return '';
        const formattedAmount = amount.toLocaleString('ko-KR', { maximumFractionDigits: 0 });
        return selectedLanguage === 'ko' ? `${formattedAmount}원` : `KRW ${formattedAmount}`;
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

    // Format today's date as YYYY-MM-DD for formatDate function
    function getTodayDateString() {
        const today = new Date();
        const year = today.getFullYear();
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const day = String(today.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function handlePrint() {
        window.print();
    }

    // Get localized attendee name based on selected language
    function getDisplayName(payment) {
        if (selectedLanguage === 'ko' && payment.attendee_name_ko) {
            return payment.attendee_name_ko;
        }
        return payment.attendee_name;
    }

    // Get localized attendee institute based on selected language
    function getDisplayInstitute(payment) {
        if (selectedLanguage === 'ko' && payment.attendee_institute_ko) {
            return payment.attendee_institute_ko;
        }
        return payment.attendee_institute;
    }

    // Get localized venue based on selected language (reactive version)
    function getLocalizedVenue(obj) {
        if (selectedLanguage === 'ko' && obj.venue_ko) {
            return obj.venue_ko;
        }
        return obj.venue || '';
    }

    // Get localized organizers based on selected language (reactive version)
    function getLocalizedOrganizers(obj) {
        if (selectedLanguage === 'ko' && obj.organizers_ko) {
            return obj.organizers_ko;
        }
        return obj.organizers_en || '';
    }

    // Get payment type text
    function getPaymentTypeText(paymentType) {
        switch (paymentType) {
            case 'card':
                return m.receipt_paymentTypeCard();
            case 'transfer':
                return m.receipt_paymentTypeTransfer();
            case 'cash':
                return m.receipt_paymentTypeCash();
            default:
                return paymentType;
        }
    }
</script>

<svelte:head>
    <title>{m.receipt_title()}</title>
</svelte:head>

<style>
    @media print {
        .no-print {
            display: none !important;
        }
        .receipt-content {
            border: none !important;
            box-shadow: none !important;
        }
    }
    @media screen {
        .receipt-container {
            max-width: 48rem;
            margin: 0 auto;
            padding: 0 1rem 2rem 1rem;
        }
        .receipt-content {
            border: 1px solid #d1d5db;
            border-radius: 0.5rem;
        }
    }
</style>

<div class="receipt-container">
    {#if payment}
        <!-- Print and Close Buttons -->
        <div class="no-print mb-6 flex justify-center items-center gap-2">
            <Select items={languageOptions} bind:value={selectedLanguage} onchange={changeLanguage} class="w-32" />
            <Button color="primary" onclick={handlePrint}>{m.common_print()}</Button>
            <Button color="light" onclick={() => window.close()}>{m.common_close()}</Button>
        </div>

        <!-- Receipt Content -->
        <div class="receipt-content bg-white p-8">
            <!-- Header -->
            <div class="mb-8">
                <h1 class="text-2xl font-bold text-center mb-6">{m.receipt_title()}</h1>
                <div class="flex justify-between">
                    <p class="text-gray-500">{m.receipt_number()}: #{payment.number.toString().padStart(10, '0')}</p>
                    <p class="text-gray-500">{m.receipt_issueDate()}: {formatDate(getTodayDateString())}</p>
                </div>
            </div>

            <!-- Event Information -->
            <div class="mb-6">
                <h2 class="text-lg font-semibold border-b border-gray-200 pb-2 mb-4">{m.receipt_eventInfo()}</h2>
                <table class="w-full">
                    <tbody>
                        <tr>
                            <td class="py-2 text-gray-600 w-1/3">{m.registrationHistory_eventName()}</td>
                            <td class="py-2 font-medium">{payment.event_name}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.registrationHistory_dates()}</td>
                            <td class="py-2">{formatDateRange(payment.start_date, payment.end_date)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.registrationHistory_venue()}</td>
                            <td class="py-2">{getLocalizedVenue(payment)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.registrationHistory_organizers()}</td>
                            <td class="py-2">{getLocalizedOrganizers(payment)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Attendee Information -->
            <div class="mb-6">
                <h2 class="text-lg font-semibold border-b border-gray-200 pb-2 mb-4">{m.receipt_attendeeInfo()}</h2>
                <table class="w-full">
                    <tbody>
                        <tr>
                            <td class="py-2 text-gray-600 w-1/3">{m.attendees_name()}</td>
                            <td class="py-2 font-medium">{getDisplayName(payment)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.attendees_institute()}</td>
                            <td class="py-2">{getDisplayInstitute(payment)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Payment Information -->
            <div class="mb-6">
                <h2 class="text-lg font-semibold border-b border-gray-200 pb-2 mb-4">{m.receipt_paymentInfo()}</h2>
                <table class="w-full">
                    <tbody>
                        <tr>
                            <td class="py-2 text-gray-600 w-1/3">{m.receipt_paymentType()}</td>
                            <td class="py-2">{getPaymentTypeText(payment.payment_type)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.receipt_paymentDate()}</td>
                            <td class="py-2">{formatDate(payment.checkout_date)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.paymentHistory_amount()}</td>
                            <td class="py-2 font-bold text-lg">{formatAmount(payment.amount)}</td>
                        </tr>
                        <tr>
                            <td class="py-2 text-gray-600">{m.paymentHistory_status()}</td>
                            <td class="py-2 font-medium">{getStatusText(payment.status)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Contact Information -->
            {#if contactEmail}
            <div class="mb-6">
                <h2 class="text-lg font-semibold border-b border-gray-200 pb-2 mb-4">{m.receipt_contactInfo()}</h2>
                <table class="w-full">
                    <tbody>
                        <tr>
                            <td class="py-2 text-gray-600 w-1/3">{m.receipt_email()}</td>
                            <td class="py-2"><a href="mailto:{contactEmail}" class="text-blue-600">{contactEmail}</a></td>
                        </tr>
                    </tbody>
                </table>
            </div>
            {/if}

            <!-- Footer -->
            <div class="mt-8 text-center text-gray-500 text-sm">
                <p>{m.receipt_footer()}</p>
            </div>
        </div>
    {:else}
        <Alert color="red">
            {m.common_error()}
        </Alert>
    {/if}
</div>
