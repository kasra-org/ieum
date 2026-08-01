<script>
    let { tableBodyClass = '', class: className = '', children, ...rest } = $props();
</script>

<tbody class="{tableBodyClass} {className}" {...rest}>{@render children?.()}</tbody>
