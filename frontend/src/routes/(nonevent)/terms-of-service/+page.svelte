<script>
    import { Card, Alert } from '$lib/components/ui';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    let currentLang = $derived(languageTag());
    let updatedAt = $derived(data.termsOfService.updated_at ? new Date(data.termsOfService.updated_at).toLocaleDateString(currentLang === 'ko' ? 'ko-KR' : 'en-US') : '');

    // For English, show English content + Korean content below
    let content = $derived(() => {
        if (currentLang === 'ko') {
            return data.termsOfService.content_ko;
        } else {
            let result = data.termsOfService.content_en || '';
            if (data.termsOfService.content_ko) {
                result += '<hr class="my-8 border-gray-300"><h2>한국어 버전 (Korean Version)</h2>' + data.termsOfService.content_ko;
            }
            return result;
        }
    });
</script>

<svelte:head>
    <title>{m.termsOfService_pageTitle()}</title>
</svelte:head>

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{m.termsOfService_pageTitle()}</h1>
            {#if updatedAt}
                <p class="text-slate-200 mt-2">{m.termsOfService_lastUpdated({ date: updatedAt })}</p>
            {/if}
        </div>
    </div>

    {#if currentLang === 'en' && data.termsOfService.content_ko}
        <Alert color="blue" class="mb-6">
            {m.termsOfService_koreanBindingNotice()}
        </Alert>
    {/if}

    <Card size="xl" padding="none" class="w-full p-6 sm:p-8 prose max-w-none leading-normal prose-p:my-2 prose-ul:my-2 prose-li:my-0 prose-h2:mt-6 prose-h2:mb-2">
        {#if content()}
            {@html content()}
        {:else}
            <p class="text-gray-500 italic">{m.termsOfService_noContent()}</p>
        {/if}
    </Card>
</div>
