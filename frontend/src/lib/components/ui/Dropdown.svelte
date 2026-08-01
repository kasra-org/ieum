<script>
    /**
     * Drop-in for flowbite-svelte's Dropdown.
     *
     * Trigger resolution matches the original: `triggeredBy` is a selector when
     * given, otherwise the immediately preceding sibling element is the trigger.
     * Every call site here relies on the latter — an Avatar or Button followed
     * by <Dropdown simple bind:open={...}> with no explicit trigger.
     *
     * Positioned fixed against the trigger's rect rather than relying on a
     * positioned ancestor, so an overflow container cannot clip it.
     */
    let {
        open = $bindable(false), triggeredBy = undefined, simple = false,
        placement = 'bottom', class: className = '', children, ...rest
    } = $props();

    let anchor = $state(null);   // marker used to locate the preceding sibling
    let menu = $state(null);
    let x = $state(0), y = $state(0), alignEnd = $state(false);

    function triggerEl() {
        if (typeof document === 'undefined') return null;
        if (triggeredBy) return document.querySelector(triggeredBy);
        return anchor?.previousElementSibling ?? null;
    }

    function position(trigger) {
        const r = trigger.getBoundingClientRect();
        alignEnd = placement.endsWith('-end');
        x = alignEnd ? r.right : r.left;
        y = placement.startsWith('top') ? r.top : r.bottom;
    }

    $effect(() => {
        const trigger = triggerEl();
        if (!trigger) return;

        const onTrigger = (e) => {
            e.stopPropagation();
            if (!open) position(trigger);
            open = !open;
        };
        const onAway = (e) => {
            if (!open) return;
            if (menu?.contains(e.target) || trigger.contains(e.target)) return;
            open = false;
        };
        const onKey = (e) => { if (e.key === 'Escape') open = false; };

        trigger.addEventListener('click', onTrigger);
        document.addEventListener('click', onAway);
        document.addEventListener('keydown', onKey);
        return () => {
            trigger.removeEventListener('click', onTrigger);
            document.removeEventListener('click', onAway);
            document.removeEventListener('keydown', onKey);
        };
    });

    // Keep it anchored when opened programmatically rather than by a click.
    $effect(() => {
        if (!open) return;
        const trigger = triggerEl();
        if (trigger) position(trigger);
    });

    const style = $derived(
        alignEnd
            ? `right:${(typeof window !== 'undefined' ? window.innerWidth : 0) - x}px; top:${y + 4}px`
            : `left:${x}px; top:${y + 4}px`
    );
</script>

<span bind:this={anchor} class="hidden" aria-hidden="true"></span>

{#if open}
    <div
        bind:this={menu}
        class="fixed z-50 min-w-44 rounded-lg bg-white shadow-lg ring-1 ring-black/5 {className}"
        {style}
        {...rest}
    >
        <ul class="py-2 text-sm text-gray-700">{@render children?.()}</ul>
    </div>
{/if}
