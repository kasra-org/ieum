<script>
    import { page } from '$app/stores';
    import { Heading } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage, hasApiMessage } from '$lib/apiMessages.js';

    // A thrown error carries a code when the app raised it; SvelteKit's own
    // (an unknown route, a crash) only has a status, so that picks the text.
    let title = $derived(
        hasApiMessage($page.error?.code) ? apiMessage($page.error)
            : $page.status === 404 ? m.errorPage_notFoundTitle()
            : $page.status === 403 ? m.api_permission_denied()
            : $page.status >= 500 ? m.errorPage_serverTitle()
            : m.common_error());
</script>

<div class="flex mx-auto flex-col text-center items-center justify-center h-96">
    <Heading tag="h1" class="mb-4">{$page.status}</Heading>
    <Heading tag="h6">{title}</Heading>
    {#if $page.status === 404}
        <p class="mt-4">{m.errorPage_notFoundDetail()}</p>
    {:else if $page.status >= 500}
        <p class="mt-4">{m.errorPage_serverDetail()}</p>
    {/if}
</div>
