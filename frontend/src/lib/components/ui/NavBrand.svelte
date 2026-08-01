<script>
    let { href = '/', class: className = '', children, ...rest } = $props();
</script>

<a {href} class="flex items-center {className}" {...rest}>{@render children?.()}</a>
