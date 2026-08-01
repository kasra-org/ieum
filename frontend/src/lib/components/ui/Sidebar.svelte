<script>
    import { setContext } from 'svelte';
    let {
        alwaysOpen = false, backdrop = true, isOpen = $bindable(true),
        activeClass = 'bg-gray-100 text-gray-900',
        nonActiveClass = 'hover:bg-gray-100',
        class: className = '', children, ...rest
    } = $props();

    // SidebarItem reads these rather than each call site repeating them.
    setContext('sidebar', {
        get activeClass() { return activeClass; },
        get nonActiveClass() { return nonActiveClass; }
    });

    const visible = $derived(alwaysOpen || isOpen);
</script>

{#if visible}
    <aside class={className} aria-label="Sidebar" {...rest}>
        <div class="h-full overflow-y-auto bg-gray-50 px-3 py-4">{@render children?.()}</div>
    </aside>
{/if}
