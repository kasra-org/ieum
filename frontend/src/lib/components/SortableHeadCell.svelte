<script>
    // A column header that sorts its table: click for ascending, again for
    // descending, again to stop; Shift+click to sort by several columns at
    // once (see $lib/tableSort.js). With more than one, each shows its
    // priority beside the arrow.
    import { TableHeadCell } from '$lib/components/ui';
    import { ArrowDown, ArrowUp, ArrowUpDown } from '@lucide/svelte';
    import { nextSort } from '$lib/tableSort.js';

    let { key, sort = [], onsort, class: className = '', children } = $props();

    const index = $derived(sort.findIndex(s => s.key === key));
    const dir = $derived(index >= 0 ? sort[index].dir : null);
</script>

<TableHeadCell class={className} aria-sort={dir === 'asc' ? 'ascending' : dir === 'desc' ? 'descending' : undefined}>
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
</TableHeadCell>
