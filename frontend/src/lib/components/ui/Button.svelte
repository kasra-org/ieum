<script>
    /**
     * Drop-in for flowbite-svelte's Button: same `color`/`size`/`pill` vocabulary.
     * Renders an <a> when `href` is set, a <button> otherwise.
     */
    let {
        color = 'primary', size = 'md', type = 'button', href = undefined,
        disabled = false, pill = false, outline = false,
        class: className = '', children, ...rest
    } = $props();

    const COLORS = {
        primary:     'text-white bg-primary-700 hover:bg-primary-800 focus:ring-primary-300 disabled:hover:bg-primary-700',
        alternative: 'text-gray-900 bg-white border border-gray-200 hover:bg-gray-100 hover:text-primary-700 focus:ring-gray-200',
        light:       'text-gray-900 bg-white border border-gray-300 hover:bg-gray-100 focus:ring-gray-200',
        dark:        'text-white bg-gray-800 hover:bg-gray-900 focus:ring-gray-300',
        red:         'text-white bg-red-700 hover:bg-red-800 focus:ring-red-300',
        green:       'text-white bg-green-700 hover:bg-green-800 focus:ring-green-300',
        yellow:      'text-white bg-yellow-400 hover:bg-yellow-500 focus:ring-yellow-300',
        purple:      'text-white bg-purple-700 hover:bg-purple-800 focus:ring-purple-300',
        blue:        'text-white bg-blue-700 hover:bg-blue-800 focus:ring-blue-300',
        none:        ''
    };
    const OUTLINES = {
        primary: 'text-primary-700 border border-primary-700 hover:bg-primary-700 hover:text-white focus:ring-primary-300',
        red:     'text-red-700 border border-red-700 hover:bg-red-800 hover:text-white focus:ring-red-300',
        green:   'text-green-700 border border-green-700 hover:bg-green-800 hover:text-white focus:ring-green-300',
        dark:    'text-gray-800 border border-gray-800 hover:bg-gray-900 hover:text-white focus:ring-gray-300'
    };
    const SIZES = {
        xs: 'px-3 py-2 text-xs', sm: 'px-3 py-2 text-sm', md: 'px-5 py-2.5 text-sm',
        lg: 'px-5 py-3 text-base', xl: 'px-6 py-3.5 text-base'
    };

    const base = 'inline-flex items-center justify-center font-medium text-center focus:outline-none focus:ring-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
    const cls = $derived([
        base,
        SIZES[size] ?? SIZES.md,
        outline ? (OUTLINES[color] ?? OUTLINES.primary) : (COLORS[color] ?? COLORS.primary),
        pill ? 'rounded-full' : 'rounded-lg',
        className
    ].filter(Boolean).join(' '));
</script>

{#if href}
    <a {href} class={cls} aria-disabled={disabled} {...rest}>{@render children?.()}</a>
{:else}
    <button {type} {disabled} class={cls} {...rest}>{@render children?.()}</button>
{/if}
