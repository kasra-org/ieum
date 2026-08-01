<script>
    import { getContext } from 'svelte';
    let { class: className = '', children, ...rest } = $props();
    const ctx = getContext('table');
</script>

<tr
    class="border-b bg-white {ctx?.hoverable ? 'hover:bg-gray-50' : ''} {ctx?.striped ? 'odd:bg-white even:bg-gray-50' : ''} {className}"
    {...rest}
>{@render children?.()}</tr>
