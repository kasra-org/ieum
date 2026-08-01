<script>
    let {
        value = $bindable(), rows = 4, class: className = '',
        disabled = false, readonly = false, ...rest
    } = $props();
</script>

<textarea
    bind:value {rows} {disabled} {readonly}
    class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-primary-500 focus:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-60 {className}"
    {...rest}
></textarea>
