<script>
    let { color = 'gray', size = 'md', class: className = '', children, ...rest } = $props();
    const COLORS = { gray: 'bg-gray-200', red: 'bg-red-500', green: 'bg-green-500', yellow: 'bg-yellow-300', blue: 'bg-blue-500', primary: 'bg-primary-500' };
    const SIZES = { xs: 'h-2 w-2', sm: 'h-2.5 w-2.5', md: 'h-3 w-3', lg: 'h-4 w-4', xl: 'h-6 w-6' };
</script>

<span class="inline-flex items-center justify-center rounded-full {COLORS[color] ?? COLORS.gray} {SIZES[size] ?? SIZES.md} {className}" {...rest}>
    {@render children?.()}
</span>
