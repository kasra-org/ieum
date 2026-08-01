<script>
    let { size = 'sm', padding = 'lg', href = undefined, class: className = '', children, ...rest } = $props();
    const SIZES = { xs: 'max-w-xs', sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-lg', xl: 'max-w-xl', '2xl': 'max-w-2xl', '3xl': 'max-w-3xl', '4xl': 'max-w-4xl', '5xl': 'max-w-5xl', none: '' };
    const PADDINGS = { none: '', sm: 'p-4', md: 'p-5', lg: 'p-6', xl: 'p-8' };
    const cls = $derived(['rounded-lg border border-gray-200 bg-white shadow-sm', SIZES[size] ?? SIZES.sm, PADDINGS[padding] ?? PADDINGS.lg, className].filter(Boolean).join(' '));
</script>

{#if href}
    <a {href} class="{cls} hover:bg-gray-50" {...rest}>{@render children?.()}</a>
{:else}
    <div class={cls} {...rest}>{@render children?.()}</div>
{/if}
