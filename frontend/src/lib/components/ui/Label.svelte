<script>
    let { for: forId = undefined, class: className = '', children, ...rest } = $props();
</script>

<label for={forId} class="block text-sm font-medium text-gray-900 {className}" {...rest}>
    {@render children?.()}
</label>
