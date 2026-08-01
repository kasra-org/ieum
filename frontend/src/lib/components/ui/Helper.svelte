<script>
    let { color = 'gray', class: className = '', children, ...rest } = $props();
    const COLORS = { gray: 'text-gray-500', red: 'text-red-600', green: 'text-green-600' };
</script>

<p class="mt-1 text-xs {COLORS[color] ?? COLORS.gray} {className}" {...rest}>{@render children?.()}</p>
