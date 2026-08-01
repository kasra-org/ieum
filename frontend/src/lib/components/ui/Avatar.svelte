<script>
    let { src = undefined, alt = '', size = 'md', rounded = true, class: className = '', children, ...rest } = $props();
    const SIZES = { xs: 'h-6 w-6', sm: 'h-8 w-8', md: 'h-10 w-10', lg: 'h-20 w-20', xl: 'h-36 w-36' };
    const shape = $derived(rounded ? 'rounded-full' : 'rounded');
</script>

{#if src}
    <img {src} {alt} class="{SIZES[size] ?? SIZES.md} {shape} object-cover {className}" {...rest} />
{:else}
    <div
        class="{SIZES[size] ?? SIZES.md} {shape} inline-flex items-center justify-center bg-gray-200 text-gray-600 {className}"
        {...rest}
    >
        {#if children}{@render children()}{:else}
            <svg class="h-2/3 w-2/3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                <path fill-rule="evenodd" d="M10 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm-7 9a7 7 0 1 1 14 0H3Z" clip-rule="evenodd" />
            </svg>
        {/if}
    </div>
{/if}
