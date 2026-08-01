<script>
    let { triggeredBy = undefined, class: className = '', children, ...rest } = $props();
    let open = $state(false);
    let x = $state(0), y = $state(0);

    $effect(() => {
        if (!triggeredBy || typeof document === 'undefined') return;
        const trigger = document.querySelector(triggeredBy);
        if (!trigger) return;
        const enter = () => {
            const r = trigger.getBoundingClientRect();
            x = r.left + r.width / 2; y = r.top;
            open = true;
        };
        const leave = () => (open = false);
        trigger.addEventListener('mouseenter', enter);
        trigger.addEventListener('mouseleave', leave);
        return () => { trigger.removeEventListener('mouseenter', enter); trigger.removeEventListener('mouseleave', leave); };
    });
</script>

{#if open}
    <div
        role="tooltip"
        class="fixed z-50 -translate-x-1/2 -translate-y-full rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow {className}"
        style="left:{x}px; top:{y - 8}px" {...rest}
    >{@render children?.()}</div>
{/if}
