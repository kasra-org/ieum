<script>
    let { hoverable = false, striped = false, divClass = 'relative overflow-x-auto', class: className = '', children, ...rest } = $props();
    // Descendant rows read these for hover/stripe styling.
    import { setContext } from 'svelte';
    setContext('table', { get hoverable() { return hoverable; }, get striped() { return striped; } });
</script>

<div class={divClass}>
    <table class="w-full text-left text-sm text-gray-500 {className}" {...rest}>
        {@render children?.()}
    </table>
</div>
