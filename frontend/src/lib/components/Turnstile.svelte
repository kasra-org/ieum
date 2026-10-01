<script>
    // Cloudflare Turnstile widget. Rendered explicitly rather than by the
    // script's page scan, which only runs once: a client-side navigation back
    // to the form would otherwise show no widget. The widget puts its token in
    // a hidden `cf-turnstile-response` input inside the enclosing form.
    import { onMount } from 'svelte';
    import { languageTag } from '$lib/paraglide/runtime.js';

    let { sitekey } = $props();

    const SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

    let container;

    function loadScript() {
        if (window.turnstile) return Promise.resolve();
        let script = document.querySelector(`script[src="${SCRIPT_URL}"]`);
        if (!script) {
            script = document.createElement('script');
            script.src = SCRIPT_URL;
            script.async = true;
            document.head.appendChild(script);
        }
        return new Promise((resolve, reject) => {
            script.addEventListener('load', () => resolve(), { once: true });
            script.addEventListener('error', () => reject(new Error('Turnstile failed to load')), { once: true });
        });
    }

    onMount(() => {
        let widgetId = null;
        let destroyed = false;
        loadScript()
            .then(() => {
                if (!destroyed) widgetId = window.turnstile.render(container, {
                    sitekey,
                    // The site's language, not the browser's: someone reading the
                    // page in Korean gets the widget in Korean too.
                    language: languageTag(),
                });
            })
            .catch((error) => console.error(error));
        return () => {
            destroyed = true;
            if (widgetId !== null) window.turnstile?.remove(widgetId);
        };
    });
</script>

<div bind:this={container} class="flex justify-center"></div>
