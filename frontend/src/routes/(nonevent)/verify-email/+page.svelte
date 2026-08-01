<script>
    let { data } = $props();
    import { A, Alert } from '$lib/components/ui';
    import { Mail } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
</script>

<svelte:head>
    <title>{m.verifyEmailPending_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.verifyEmailPending_title()}</h1>
        <p class="text-slate-200 mt-2">{m.verifyEmailPending_description()}</p>
    </div>
</div>

<!-- Content Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <div class="flex items-start gap-4">
        <div class="flex-shrink-0">
            <Mail class="w-12 h-12 text-blue-600" />
        </div>
        <div class="flex-1">
            <h2 class="text-xl font-semibold text-gray-900 mb-3">{m.verifyEmailPending_checkInbox()}</h2>
            <p class="text-gray-700 mb-4">{m.verifyEmailPending_instructions()}</p>
            <Alert color="blue" class="mb-0">
                {m.verifyEmailPending_spamWarning()}
            </Alert>
        </div>
    </div>
</div>