<script>
    import { Button, Alert } from '$lib/components/ui';
    import { CircleCheck, CircleX } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';

    let { data } = $props();

    const inv = $derived(data.invitation);
    const eventUrl = $derived(`/event/${inv.event_id}`);

    function formatDate(iso) {
        if (!iso) return '';
        return new Date(iso).toLocaleDateString(languageTag() === 'ko' ? 'ko-KR' : 'en-US',
            { year: 'numeric', month: 'long', day: 'numeric' });
    }
</script>

<svelte:head>
    <title>{m.invitePage_title({ event: inv.event_name })} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{inv.event_name}</h1>
        <p class="text-slate-200 mt-2">
            {formatDate(inv.event_start_date)} – {formatDate(inv.event_end_date)}{#if inv.event_venue} · {inv.event_venue}{/if}
        </p>
    </div>
</div>

<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    {#if data.outcome.ok}
        <div class="flex items-start gap-4">
            <CircleCheck class="w-12 h-12 text-green-600 shrink-0" />
            <div class="flex-1">
                <h2 class="text-xl font-semibold text-gray-900 mb-3">{m.invitePage_registered()}</h2>
                <p class="text-gray-700 mb-4">{m.invitePage_registeredDetail({ event: inv.event_name })}</p>
                {#if inv.fee_waived}
                    <Alert color="green" class="mb-6">{m.invitePage_feeWaived()}</Alert>
                {:else}
                    <Alert color="blue" class="mb-6">{m.invitePage_feeDue()}</Alert>
                {/if}
                <Button color="primary" href={eventUrl}>{m.invitePage_goToEvent()}</Button>
            </div>
        </div>
    {:else}
        <div class="flex items-start gap-4">
            <CircleX class="w-12 h-12 text-red-600 shrink-0" />
            <div class="flex-1">
                <h2 class="text-xl font-semibold text-gray-900 mb-3">{m.invitePage_notApplied()}</h2>
                {#if data.outcome.code === 'wrong_account'}
                    <p class="text-gray-700 mb-4">{m.invitePage_wrongAccount({ email: inv.email })}</p>
                    <Button color="primary" href="/logout?next={encodeURIComponent(`/invite/${data.invitation.token ?? ''}`)}">{m.invitePage_switchAccount()}</Button>
                {:else if data.outcome.code === 'event_full'}
                    <p class="text-gray-700 mb-4">{m.invitePage_eventFull()}</p>
                {:else}
                    <p class="text-gray-700 mb-4">{data.outcome.message || m.invitePage_genericError()}</p>
                {/if}
            </div>
        </div>
    {/if}
</div>
