<script>
    let { class: className = '', ...rest } = $props();
</script>

<li role="separator"><hr class="my-1 border-gray-100 {className}" {...rest} /></li>
