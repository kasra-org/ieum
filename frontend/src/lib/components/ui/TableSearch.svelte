<script>
    /** Table with a search box above it, matching flowbite-svelte's TableSearch. */
    import Table from './Table.svelte';
    import * as m from '$lib/paraglide/messages.js';
    // fields: optional [{ value, name }] - when given, a dropdown in front of
    // the box picks which column to search ('all' searches every one). The
    // filtering itself is the caller's, via matchesSearch in $lib/utils.js.
    let {
        inputValue = $bindable(''), field = $bindable('all'), fields = null, placeholder = 'Search',
        hoverable = false, striped = false, divClass = 'relative overflow-x-auto',
        innerDivClass = 'p-4', inputClass = '', class: className = '', children, ...rest
    } = $props();
</script>

<div class="{innerDivClass} flex flex-wrap items-center gap-2">
    {#if fields?.length}
        <label class="sr-only" for="table-search-field">{m.search_field()}</label>
        <select
            id="table-search-field" bind:value={field}
            class="rounded-lg border border-gray-300 bg-gray-50 p-2 pe-8 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500"
        >
            <option value="all">{m.search_all()}</option>
            {#each fields as f}
                <option value={f.value}>{f.name}</option>
            {/each}
        </select>
    {/if}
    <label class="sr-only" for="table-search">{placeholder}</label>
    <input
        id="table-search" type="text" bind:value={inputValue}
        placeholder={fields?.length ? m.search_placeholder() : placeholder}
        class="block w-80 max-w-full rounded-lg border border-gray-300 bg-gray-50 p-2 ps-3 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 {inputClass}"
    />
</div>
<Table {hoverable} {striped} {divClass} class={className} {...rest}>{@render children?.()}</Table>
