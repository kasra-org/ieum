<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<span class="inline-flex items-center rounded-s-lg border border-e-0 border-gray-300 bg-gray-200 px-3 text-sm text-gray-900 {className}" {...rest}>
    {@render children?.()}
</span>
