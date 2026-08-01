<script>
    let { tag = 'ul', list = 'disc', class: className = '', children, ...rest } = $props();
    const STYLES = { disc: 'list-disc', decimal: 'list-decimal', none: 'list-none' };
</script>

<svelte:element this={tag} class="space-y-1 ps-5 text-gray-700 {STYLES[list] ?? STYLES.disc} {className}" {...rest}>
    {@render children?.()}
</svelte:element>
