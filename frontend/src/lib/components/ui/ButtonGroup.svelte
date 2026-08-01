<script>
    let { class: className = '', children, ...rest } = $props();
</script>

<div class="inline-flex rounded-md shadow-sm [&>*:not(:first-child)]:rounded-s-none [&>*:not(:last-child)]:rounded-e-none {className}" role="group" {...rest}>
    {@render children?.()}
</div>
