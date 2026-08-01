<script>
    let { group = $bindable(), value = undefined, class: className = '', disabled = false, children, ...rest } = $props();
</script>

<label class="flex items-center gap-2 text-sm font-medium text-gray-900 {disabled ? 'opacity-60' : ''}">
    <input
        type="radio" bind:group {value} {disabled}
        class="h-4 w-4 border-gray-300 bg-gray-100 text-primary-600 focus:ring-2 focus:ring-primary-500 {className}"
        {...rest}
    />
    {@render children?.()}
</label>
