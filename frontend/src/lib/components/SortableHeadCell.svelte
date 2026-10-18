<script>
    // A column header that sorts its table: click for ascending, again for
    // descending, again to stop; Shift+click to sort by several columns at
    // once (see $lib/tableSort.js). With more than one, each shows its
    // priority beside the arrow.
    import { TableHeadCell } from '$lib/components/ui';
    import { ArrowDown, ArrowUp, ArrowUpDown } from '@lucide/svelte';
    import { nextSort } from '$lib/tableSort.js';
    import * as m from '$lib/paraglide/messages.js';

    let { key, sort = [], onsort, class: className = '', children } = $props();

    const index = $derived(sort.findIndex(s => s.key === key));
    const dir = $derived(index >= 0 ? sort[index].dir : null);
</script>

<TableHeadCell class={className} aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : undefined}>
    <!-- The hint shows below the header, as ActionTooltip's does above: the
         table's scrolling wrapper would clip it above the header row. -->
    <span class="group relative inline-flex">
    <!-- Shift+click would otherwise select the header text. -->
    <button
        type="button"
        class="inline-flex items-center gap-1 select-none cursor-pointer hover:text-gray-900 {dir ? 'text-gray-900' : ''}"
        onmousedown={(e) => { if (e.shiftKey) e.preventDefault(); }}
        onclick={(e) => onsort?.(nextSort(sort, key, e.shiftKey))}
    >
        {@render children?.()}
        {#if dir === 'asc'}
            <ArrowUp class="h-3.5 w-3.5 shrink-0" />
        {:else if dir === 'desc'}
            <ArrowDown class="h-3.5 w-3.5 shrink-0" />
        {:else}
            <ArrowUpDown class="h-3.5 w-3.5 shrink-0 opacity-30" />
        {/if}
        {#if index >= 0 && sort.length > 1}
            <span class="text-[10px] leading-none text-primary-700">{index + 1}</span>
        {/if}
    </button>
    <span role="tooltip" class="invisible group-hover:visible absolute top-full left-1/2 -translate-x-1/2 mt-1 px-2 py-1 text-xs font-normal normal-case text-white bg-gray-800 rounded whitespace-nowrap z-50">
        {m.table_sortHint()}
        <span class="absolute bottom-full left-1/2 -translate-x-1/2 border-4 border-transparent border-b-gray-800"></span>
    </span>
    </span>
</TableHeadCell>
