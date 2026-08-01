<script>
    import { Label } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { onMount } from 'svelte';

    // Props
    let { selectedYear = $bindable('all'), onYearChange } = $props();

    // Year navigation
    const currentYear = new Date().getFullYear();
    let yearOffset = $state(0);

    // Container width tracking
    let containerRef = $state(null);
    let numYearsToShow = $state(5); // Number of years to display (always odd)
    let gapSize = $state(4); // Dynamic gap size in pixels

    // Get years to display - dynamically calculated based on container width
    let displayYears = $derived(() => {
        const centerYear = currentYear + yearOffset;
        const halfRange = Math.floor(numYearsToShow / 2);
        const years = [];
        for (let i = -halfRange; i <= halfRange; i++) {
            years.push(centerYear + i);
        }
        return years;
    });

    // Measure container width and calculate how many years can fit
    onMount(() => {
        if (!containerRef) return;

        const updateDisplay = () => {
            if (containerRef) {
                const width = containerRef.offsetWidth;

                // Approximate sizes:
                // - Each navigation arrow: ~20px
                // - Each year button: ~36px (4 chars at text-sm + px-1 padding)
                // - Minimum gap: 4px (gap-1)
                // - Buffer: 4px

                const arrowsWidth = 40; // 2 arrows
                const buffer = 4;
                const buttonWidth = 40; // Approximate width of each year button
                const minGap = 1; // Minimum gap between buttons

                const availableWidth = width - arrowsWidth - buffer;

                // Calculate how many years fit with minimum gap
                const maxYears = Math.floor((availableWidth + minGap) / (buttonWidth + minGap));

                // Ensure odd number (1, 3, 5, 7, 9, ...) with minimum of 1 and maximum of 13
                let calculated = maxYears;
                if (calculated % 2 === 0) calculated -= 1; // Make it odd
                calculated = Math.max(1, Math.min(13, calculated)); // Clamp between 1 and 13

                numYearsToShow = calculated;

                // Calculate optimal gap size to distribute remaining space
                const totalButtonsWidth = calculated * buttonWidth;
                const remainingSpace = availableWidth - totalButtonsWidth;
                const numGaps = calculated - 1; // Gaps between buttons

                if (numGaps > 0) {
                    // Distribute remaining space across gaps, with max gap of 12px
                    const calculatedGap = Math.floor(remainingSpace / numGaps);
                    gapSize = Math.max(minGap, Math.min(12, calculatedGap));
                } else {
                    gapSize = minGap;
                }
            }
        };

        // Initial measurement
        updateDisplay();

        // Watch for size changes
        const resizeObserver = new ResizeObserver(updateDisplay);
        resizeObserver.observe(containerRef);

        return () => {
            resizeObserver.disconnect();
        };
    });

    function navigateYears(direction) {
        yearOffset += direction;
    }

    function selectYear(year) {
        selectedYear = year.toString();
        if (onYearChange) {
            onYearChange(year.toString());
        }
    }
</script>

<div bind:this={containerRef}>
    <Label class="mb-3 text-sm font-semibold text-gray-700">{m.events_year()}</Label>
    <div class="flex items-center justify-between gap-1">
        <button
            type="button"
            onclick={() => navigateYears(-1)}
            class="p-1 hover:bg-gray-100 rounded transition-colors flex-shrink-0"
            aria-label="Previous years"
        >
            <span class="text-gray-600 font-bold text-lg">&lt;</span>
        </button>
        <div class="flex items-center flex-1 justify-center min-w-0" style="gap: {gapSize}px">
            {#each displayYears() as year}
                <button
                    type="button"
                    onclick={() => selectYear(year)}
                    class={`px-1 py-1 text-sm rounded transition-colors cursor-pointer flex-shrink-0
                        ${selectedYear === year.toString() ? 'bg-blue-600 text-white font-bold' : 'hover:bg-gray-100 text-gray-600'}
                        ${year === currentYear && selectedYear !== year.toString() ? 'font-bold text-gray-900' : ''}
                    `}
                >
                    {year}
                </button>
            {/each}
        </div>
        <button
            type="button"
            onclick={() => navigateYears(1)}
            class="p-1 hover:bg-gray-100 rounded transition-colors flex-shrink-0"
            aria-label="Next years"
        >
            <span class="text-gray-600 font-bold text-lg">&gt;</span>
        </button>
    </div>
</div>
