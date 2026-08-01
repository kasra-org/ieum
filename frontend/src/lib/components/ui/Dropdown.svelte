<script>
    /**
     * flowbite-svelte's Dropdown positions itself against a `triggeredBy`
     * selector; the same prop is honoured here.
     */
    let {
        open = $bindable(false), triggeredBy = undefined, simple = false,
        class: className = '', children, ...rest
    } = $props();

    let el = $state(null);

    $effect(() => {
        if (!triggeredBy || typeof document === 'undefined') return;
        const trigger = document.querySelector(triggeredBy);
        if (!trigger) return;
        const toggle = (e) => { e.stopPropagation(); open = !open; };
        const away = (e) => { if (open && el && !el.contains(e.target) && !trigger.contains(e.target)) open = false; };
        trigger.addEventListener('click', toggle);
        document.addEventListener('click', away);
        return () => { trigger.removeEventListener('click', toggle); document.removeEventListener('click', away); };
    });
</script>

{#if open}
    <div bind:this={el} class="absolute z-50 min-w-44 rounded-lg bg-white shadow ring-1 ring-black/5 {className}" {...rest}>
        <ul class="py-2 text-sm text-gray-700">{@render children?.()}</ul>
    </div>
{/if}
