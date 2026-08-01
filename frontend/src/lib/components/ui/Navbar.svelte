<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<nav class="w-full px-4 {className}" {...rest}>
    <div class="mx-auto flex flex-wrap items-center justify-between">{@render children?.()}</div>
</nav>
