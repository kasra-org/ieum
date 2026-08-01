<script>
    import { setContext } from 'svelte';
    let { class: className = '', contentClass = 'p-4', children, ...rest } = $props();
    let selected = $state(null);
    setContext('tabs', {
        get selected() { return selected; },
        select: (id) => (selected = id),
        register: (id) => { if (selected === null) selected = id; }
    });
</script>

<div {...rest}>
    <ul class="flex flex-wrap border-b border-gray-200 text-center text-sm font-medium text-gray-500 {className}">
        {@render children?.()}
    </ul>
</div>
