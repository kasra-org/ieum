<script>
    import { ButtonGroup, Button } from '$lib/components/ui';
    import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from '@lucide/svelte';

    let { currentPage, totalPages, onPageChange } = $props();

    const btnClass = "!px-3.5 !py-1.5";

    // Generate page numbers to display (show max 5 pages around current)
    let visiblePages = $derived(() => {
        const pages = [];
        const maxVisible = 5;
        const total = Math.max(1, totalPages);

        let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(total, start + maxVisible - 1);

        // Adjust start if we're near the end
        if (end - start + 1 < maxVisible) {
            start = Math.max(1, end - maxVisible + 1);
        }

        for (let i = start; i <= end; i++) {
            pages.push(i);
        }

        return pages;
    });

    let effectiveTotalPages = $derived(Math.max(1, totalPages));
</script>

<div class="flex items-center justify-center mt-4">
        <ButtonGroup>
            <Button
                color="light"
                size="sm"
                class={btnClass}
                disabled={currentPage === 1}
                onclick={() => onPageChange(1)}
            ><ChevronsLeft class="h-4 w-4" /></Button>
            <Button
                color="light"
                size="sm"
                class={btnClass}
                disabled={currentPage === 1}
                onclick={() => onPageChange(currentPage - 1)}
            ><ChevronLeft class="h-4 w-4" /></Button>
            {#each visiblePages() as page}
                <!-- The current page in the primary colour: highlight classes laid
                     over the light button lost to its own white background. -->
                <Button
                    color={currentPage === page ? 'primary' : 'light'}
                    size="sm"
                    class={btnClass}
                    aria-current={currentPage === page ? 'page' : undefined}
                    onclick={() => onPageChange(page)}
                >{page}</Button>
            {/each}
            <Button
                color="light"
                size="sm"
                class={btnClass}
                disabled={currentPage >= effectiveTotalPages}
                onclick={() => onPageChange(currentPage + 1)}
            ><ChevronRight class="h-4 w-4" /></Button>
            <Button
                color="light"
                size="sm"
                class={btnClass}
                disabled={currentPage >= effectiveTotalPages}
                onclick={() => onPageChange(effectiveTotalPages)}
            ><ChevronsRight class="h-4 w-4" /></Button>
        </ButtonGroup>
    </div>
