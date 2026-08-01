<script>
    let { class: className = '', ...rest } = $props();
</script>

<hr class="my-4 border-gray-200 {className}" {...rest} />
