<script>
    /** Table with a search box above it, matching flowbite-svelte's TableSearch. */
    import Table from './Table.svelte';
    let {
        inputValue = $bindable(''), placeholder = 'Search',
        hoverable = false, striped = false, divClass = 'relative overflow-x-auto',
        innerDivClass = 'p-4', inputClass = '', class: className = '', children, ...rest
    } = $props();
</script>

<div class={innerDivClass}>
    <label class="sr-only" for="table-search">{placeholder}</label>
    <input
        id="table-search" type="text" bind:value={inputValue} {placeholder}
        class="block w-80 max-w-full rounded-lg border border-gray-300 bg-gray-50 p-2 ps-3 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 {inputClass}"
    />
</div>
<Table {hoverable} {striped} {divClass} class={className} {...rest}>{@render children?.()}</Table>
