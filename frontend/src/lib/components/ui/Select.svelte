<script>
    /** `items` is [{ value, name }], matching flowbite-svelte. */
    let {
        value = $bindable(), items = [], placeholder = '', class: className = '',
        disabled = false, children, ...rest
    } = $props();
</script>

<select
    bind:value {disabled}
    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-60 {className}"
    {...rest}
>
    {#if placeholder}<option value="" disabled selected>{placeholder}</option>{/if}
    {#if children}
        {@render children?.()}
    {:else}
        {#each items as item}
            <option value={item.value} disabled={item.disabled}>{item.name}</option>
        {/each}
    {/if}
</select>
