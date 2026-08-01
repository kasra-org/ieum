<script>
    /** `steps` is a list of labels (or {label}); `current` is the 0-based index. */
    let {
        steps = [], current = 0, clickable = false,
        showCheckmarkForCompleted = true, onstepclick = undefined,
        class: className = '', ...rest
    } = $props();

    const label = (s) => (typeof s === 'string' ? s : (s?.label ?? ''));
</script>

<!--
    Every step keeps its natural width and the connectors are a fixed length, so
    labels never get squeezed into wrapping and the group stays compact and
    centred instead of being flung to the container's edges on wide screens.
-->
<ol class="flex w-full items-center justify-center overflow-x-auto text-sm {className}" {...rest}>
    {#each steps as step, i}
        {@const done = i < current}
        {@const active = i === current}
        <li class="flex shrink-0 items-center">
            <span class="flex shrink-0 items-center gap-2.5">
                <span
                    class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors
                    {active
                        ? 'bg-primary-600 text-white ring-4 ring-primary-100'
                        : done
                            ? 'bg-primary-600 text-white'
                            : 'bg-gray-100 text-gray-400'}"
                >
                    {#if done && showCheckmarkForCompleted}
                        <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                            <path
                                fill-rule="evenodd"
                                d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.8 3.8 6.8-6.8a1 1 0 0 1 1.4 0Z"
                                clip-rule="evenodd"
                            />
                        </svg>
                    {:else}
                        {i + 1}
                    {/if}
                </span>
                {#if clickable}
                    <button
                        type="button"
                        class="whitespace-nowrap font-medium transition-colors hover:underline
                        {active ? 'text-gray-900' : done ? 'text-gray-700' : 'text-gray-400'}"
                        onclick={() => onstepclick?.(i)}
                    >{label(step)}</button>
                {:else}
                    <span class="whitespace-nowrap font-medium {active ? 'text-gray-900' : done ? 'text-gray-700' : 'text-gray-400'}">
                        {label(step)}
                    </span>
                {/if}
            </span>
            {#if i < steps.length - 1}
                <span
                    class="mx-2 h-px w-8 shrink-0 sm:mx-4 sm:w-16 {done ? 'bg-primary-300' : 'bg-gray-200'}"
                    aria-hidden="true"
                ></span>
            {/if}
        </li>
    {/each}
</ol>
