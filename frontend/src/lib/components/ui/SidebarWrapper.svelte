<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<div class="overflow-y-auto rounded bg-gray-50 px-3 py-4 {className}" {...rest}>{@render children?.()}</div>
