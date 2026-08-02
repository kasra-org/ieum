<script>
    import { Heading, Card, Button } from '$lib/components/ui';
    import { CircleCheck, Wallet } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';

    export let data;
    const onsiteid = data.onsiteid;
    const event = data.event;

    // With a fee the registration is not finished yet, so the page must not
    // claim it is; payment is taken at the desk.
    const onsiteFee = event.onsite_registration_fee || 0;
    const formattedFee = onsiteFee
        ? (languageTag() === 'ko'
            ? `${onsiteFee.toLocaleString('ko-KR')} 원`
            : `KRW ${onsiteFee.toLocaleString('ko-KR')}`)
        : '';
</script>

<svelte:head>
    <title>{m.onsiteRegistration_complete()} - {event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="flex items-center justify-center min-h-screen bg-gray-50 px-4">
    <Card size="xl" class="max-w-md w-full text-center">
        <div class="flex justify-center mb-4">
            {#if onsiteFee > 0}
                <Wallet class="w-16 h-16 text-amber-500" />
            {:else}
                <CircleCheck class="w-16 h-16 text-green-500" />
            {/if}
        </div>
        <Heading tag="h1" class="text-2xl font-bold mb-3">
            {onsiteFee > 0 ? m.onsiteRegistration_paymentPending() : m.onsiteRegistration_complete()}
        </Heading>
        <p class="mb-6 text-gray-600">
            {#if onsiteFee > 0}
                {m.onsiteRegistration_paymentPendingDetail({ fee: formattedFee })}
            {:else if languageTag() === 'ko'}
                <span class="font-semibold">{event.name}</span>{m.onsiteRegistration_thankYou()}
            {:else}
                {m.onsiteRegistration_thankYou()} <span class="font-semibold">{event.name}</span>.
            {/if}
        </p>
        <div class="bg-gray-50 rounded-lg p-4 mb-6">
            <p class="text-sm text-gray-500 mb-1">{m.onsiteRegistration_yourId()}</p>
            <p class="text-3xl font-bold text-primary-600">{onsiteid}</p>
        </div>
        <p class="text-sm text-gray-500 mb-6">
            {onsiteFee > 0 ? m.onsiteRegistration_payAtDesk() : m.onsiteRegistration_keepForRecords()}
        </p>
        <Button href="/event/{event.id}" color="primary" size="lg" class="w-full">
            {m.onsiteRegistration_backToEvent()}
        </Button>
    </Card>
</div>