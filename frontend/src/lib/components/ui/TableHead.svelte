<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<thead class="bg-gray-50 text-xs uppercase text-gray-700 {className}" {...rest}>
    <tr>{@render children?.()}</tr>
</thead>
