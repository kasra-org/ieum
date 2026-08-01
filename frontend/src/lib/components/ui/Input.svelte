<script>
    let {
        value = $bindable(), type = 'text', class: className = '', disabled = false,
        readonly = false, required = false, children, ...rest
    } = $props();

    const base = 'block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-60';
</script>

{#if children}
    <div class="flex">{@render children?.()}
        <input {type} bind:value {disabled} {readonly} {required} class="{base} {className}" {...rest} />
    </div>
{:else}
    <input {type} bind:value {disabled} {readonly} {required} class="{base} {className}" {...rest} />
{/if}
