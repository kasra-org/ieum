<script>
    let { href = '#', class: className = '', children, ...rest } = $props();
</script>

<a {href} class="font-medium text-primary-600 hover:underline {className}" {...rest}>{@render children?.()}</a>
