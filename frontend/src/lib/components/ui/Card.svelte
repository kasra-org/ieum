<script>
    /**
     * Card. The `size` scale is deliberately NOT `max-w-{size}` — it follows the
     * scale the call sites were written against, where md/lg/xl widen faster
     * than their names suggest and `xl` is unconstrained:
     *   xs->max-w-xs  sm->max-w-sm  md->max-w-lg  lg->max-w-2xl  xl->none
     * Several pages (login, admin, reviewer, onsite) rely on xl being
     * unconstrained to lay out multi-column content.
     */
    let {
        size = 'sm', padding = 'lg', href = undefined, horizontal = false,
        shadow = true, class: className = '', children, ...rest
    } = $props();

    const SIZES = {
        xs: 'max-w-xs', sm: 'max-w-sm', md: 'max-w-lg',
        lg: 'max-w-2xl', xl: 'max-w-none', none: ''
    };
    const PADDINGS = { none: '', xs: 'p-2', sm: 'p-4', md: 'p-5', lg: 'p-6', xl: 'p-8' };

    const cls = $derived([
        'w-full rounded-lg border border-gray-200 bg-white',
        horizontal ? 'flex flex-row' : 'flex flex-col',
        shadow ? 'shadow-sm' : '',
        SIZES[size] ?? SIZES.sm,
        PADDINGS[padding] ?? PADDINGS.lg,
        className
    ].filter(Boolean).join(' '));
</script>

{#if href}
    <a {href} class="{cls} hover:bg-gray-50" {...rest}>{@render children?.()}</a>
{:else}
    <div class={cls} {...rest}>{@render children?.()}</div>
{/if}
