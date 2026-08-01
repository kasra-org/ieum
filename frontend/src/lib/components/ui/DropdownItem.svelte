<script>
    let { href = undefined, class: className = '', children, ...rest } = $props();
</script>

<li>
    {#if href}
        <a {href} class="block px-4 py-2 hover:bg-gray-100 {className}" {...rest}>{@render children?.()}</a>
    {:else}
        <button type="button" class="block w-full px-4 py-2 text-left hover:bg-gray-100 {className}" {...rest}>
            {@render children?.()}
        </button>
    {/if}
</li>
