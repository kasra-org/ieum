<script>
    /**
     * Minimal stand-in for flowbite-svelte's Datepicker, backed by the native
     * date input. Nothing in this project used it; it exists so the barrel
     * export stays complete.
     */
    let { value = $bindable(), class: className = '', ...rest } = $props();
</script>

<input
    type="date" bind:value
    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 {className}"
    {...rest}
/>
