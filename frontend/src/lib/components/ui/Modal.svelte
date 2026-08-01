<script>
    /** Drop-in for flowbite-svelte's Modal: bind:open, title, size, dismissable. */
    let {
        open = $bindable(false), title = '', size = 'md', dismissable = true,
        autoclose = false, outsideclose = false, onclose = undefined,
        class: className = '', children, footer, ...rest
    } = $props();

    const SIZES = { xs: 'max-w-xs', sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-xl', '2xl': 'max-w-2xl', '3xl': 'max-w-3xl', '4xl': 'max-w-4xl', '5xl': 'max-w-5xl', '6xl': 'max-w-6xl', '7xl': 'max-w-7xl' };

    function close() {
        open = false;
        onclose?.();
    }
    function onkeydown(e) {
        if (e.key === 'Escape' && dismissable) close();
    }
</script>

<svelte:window on:keydown={onkeydown} />

{#if open}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
        class="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-gray-900/50 p-4"
        role="dialog" aria-modal="true"
        onclick={(e) => { if ((outsideclose || dismissable) && e.target === e.currentTarget) close(); }}
    >
        <div class="relative max-h-full w-full {SIZES[size] ?? SIZES.md} rounded-lg bg-white shadow {className}" {...rest}>
            {#if title || dismissable}
                <div class="flex items-center justify-between rounded-t border-b p-4">
                    <h3 class="text-lg font-semibold text-gray-900">{title}</h3>
                    {#if dismissable}
                        <button type="button" aria-label="Close"
                                class="ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-200 hover:text-gray-900"
                                onclick={close}>&times;</button>
                    {/if}
                </div>
            {/if}
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div class="space-y-4 p-4" onclick={() => { if (autoclose) close(); }}>
                {@render children?.()}
            </div>
            {#if footer}
                <div class="flex items-center rounded-b border-t p-4">{@render footer()}</div>
            {/if}
        </div>
    </div>
{/if}
