<script>
    import { getContext } from 'svelte';
    let {
        label = '', href = undefined, active = false, activeClass = undefined,
        nonActiveClass = undefined, class: className = '', icon, subtext, children, ...rest
    } = $props();

    const ctx = getContext('sidebar');
    const activeCls = $derived(activeClass ?? ctx?.activeClass ?? 'bg-gray-100 text-gray-900');
    const idleCls = $derived(nonActiveClass ?? ctx?.nonActiveClass ?? 'hover:bg-gray-100');
</script>

<li>
    <a
        {href}
        class="flex items-center gap-3 rounded-lg p-2 text-base font-normal text-gray-900 {active ? activeCls : idleCls} {className}"
        aria-current={active ? 'page' : undefined}
        {...rest}
    >
        {@render icon?.()}
        <span class="flex-1 whitespace-nowrap">{label}</span>
        {@render subtext?.()}
        {@render children?.()}
    </a>
</li>
