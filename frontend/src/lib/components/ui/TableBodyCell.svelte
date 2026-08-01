<script>
    let { class: className = '', colspan = undefined, children, ...rest } = $props();
</script>

<td {colspan} class="px-6 py-4 {className}" {...rest}>{@render children?.()}</td>
