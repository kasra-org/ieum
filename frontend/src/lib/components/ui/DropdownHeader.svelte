<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<li class="px-4 py-2 text-sm text-gray-900 {className}" {...rest}>{@render children?.()}</li>
