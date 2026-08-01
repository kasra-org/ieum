<script>
    import { Button } from '$lib/components/ui';
    import { onMount } from 'svelte';
    import * as m from '$lib/paraglide/messages.js';

    let showBanner = $state(false);

    onMount(() => {
        const consent = localStorage.getItem('cookie-consent');
        if (consent !== 'accepted') {
            showBanner = true;
        }
    });

    function acceptCookies() {
        localStorage.setItem('cookie-consent', 'accepted');
        showBanner = false;
    }
</script>

{#if showBanner}
    <div class="fixed inset-0 z-50 bg-black/50 flex items-end">
        <div class="w-full bg-white border-t border-gray-200 p-4 shadow-lg">
            <div class="container mx-auto max-w-4xl flex flex-col sm:flex-row items-center justify-between gap-4">
                <div class="text-sm text-gray-700">
                    <p>
                        {m.cookieConsent_description()}
                        <a href="/privacy-policy" class="text-primary-600 hover:text-primary-700 underline">{m.cookieConsent_learnMore()}</a>
                    </p>
                </div>
                <div class="shrink-0">
                    <Button color="primary" size="sm" onclick={acceptCookies}>
                        {m.cookieConsent_accept()}
                    </Button>
                </div>
            </div>
        </div>
    </div>
{/if}
