<script>
    let { files = $bindable(), multiple = false, accept = undefined, class: className = '', children, ...rest } = $props();
    let over = $state(false);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<label
    class="flex w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 {over ? 'border-primary-500 bg-primary-50' : 'border-gray-300 bg-gray-50 hover:bg-gray-100'} {className}"
    ondragover={(e) => { e.preventDefault(); over = true; }}
    ondragleave={() => (over = false)}
    ondrop={(e) => { e.preventDefault(); over = false; files = e.dataTransfer?.files; }}
>
    {@render children?.()}
    <input type="file" class="hidden" {multiple} {accept} onchange={(e) => (files = e.currentTarget.files)} {...rest} />
</label>
