<script>
    let { border = false, class: className = '', children, ...rest } = $props();
</script>

<ul class="space-y-2 {border ? 'mt-4 border-t border-gray-200 pt-4' : ''} {className}" {...rest}>
    {@render children?.()}
</ul>
