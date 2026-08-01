<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<li class={className} {...rest}>{@render children?.()}</li>
