<script>
    let { checked = $bindable(false), class: className = '', disabled = false, children, ...rest } = $props();
</script>

<label class="inline-flex cursor-pointer items-center gap-3 {disabled ? 'opacity-60' : ''} {className}">
    <input type="checkbox" bind:checked {disabled} class="peer sr-only" {...rest} />
    <span class="relative h-6 w-11 rounded-full bg-gray-200 after:absolute after:start-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-primary-600 peer-checked:after:translate-x-full peer-checked:after:border-white peer-focus:ring-4 peer-focus:ring-primary-300"></span>
    <span class="text-sm font-medium text-gray-900">{@render children?.()}</span>
</label>
