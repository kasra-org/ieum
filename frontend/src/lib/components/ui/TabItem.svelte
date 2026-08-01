<script>
    import { getContext, untrack } from 'svelte';
    let { open = false, title = '', class: className = '', children, ...rest } = $props();
    const ctx = getContext('tabs');
    const id = Symbol('tab');
    // Register once; `open` is only an initial hint, so read it untracked
    // rather than letting it look like a reactive dependency.
    $effect.pre(() => { untrack(() => (open ? ctx?.select(id) : ctx?.register(id))); });
    const active = $derived(ctx?.selected === id);
</script>

<li class="me-2">
    <button
        type="button"
        class="inline-block rounded-t-lg p-4 {active ? 'border-b-2 border-primary-600 text-primary-600' : 'hover:border-b-2 hover:border-gray-300 hover:text-gray-600'} {className}"
        onclick={() => ctx?.select(id)} {...rest}
    >{title}</button>
</li>
{#if active}
    <div class="w-full p-4">{@render children?.()}</div>
{/if}
