<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<th scope="col" class="px-6 py-3 {className}" {...rest}>{@render children?.()}</th>
