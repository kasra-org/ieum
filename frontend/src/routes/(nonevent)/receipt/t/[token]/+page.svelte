<script>
    import ReceiptView from '$lib/components/ReceiptView.svelte';

    let { data } = $props();
</script>

<ReceiptView payment={data.payment} />
