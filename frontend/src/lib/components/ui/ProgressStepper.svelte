<script>
    /** `steps` is a list of labels (or {label}); `current` is the 0-based index. */
    let {
        steps = [], current = 0, clickable = false,
        showCheckmarkForCompleted = true, onstepclick = undefined,
        class: className = '', ...rest
    } = $props();

    const label = (s) => (typeof s === 'string' ? s : (s?.label ?? ''));
</script>

<ol class="flex w-full items-center text-sm font-medium text-gray-500 sm:text-base {className}" {...rest}>
    {#each steps as step, i}
        {@const done = i < current}
        {@const active = i === current}
        <li class="flex items-center {i < steps.length - 1 ? 'w-full' : ''} {active ? 'text-primary-600' : done ? 'text-gray-900' : ''}">
            <span class="flex items-center">
                <span class="me-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs {active ? 'bg-primary-600 text-white' : done ? 'bg-gray-200 text-gray-900' : 'bg-gray-100 text-gray-500'}">
                    {#if done && showCheckmarkForCompleted}✓{:else}{i + 1}{/if}
                </span>
                {#if clickable}
                    <button type="button" class="hover:underline" onclick={() => onstepclick?.(i)}>{label(step)}</button>
                {:else}
                    {label(step)}
                {/if}
            </span>
            {#if i < steps.length - 1}
                <span class="mx-3 hidden h-px flex-1 bg-gray-200 sm:inline-block"></span>
            {/if}
        </li>
    {/each}
</ol>
