<script>
    let { text, children } = $props();
</script>

<div class="group relative inline-flex">
    {@render children()}
    <div class="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 text-xs text-white bg-gray-800 rounded whitespace-nowrap z-50">
        {text}
        <div class="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-800"></div>
    </div>
</div>
