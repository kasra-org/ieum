<script>
    import { Modal, Button } from '$lib/components/ui';
    import { CircleAlert } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';

    let {
        open = $bindable(false),
        title = '',
        message = '',
        confirmLabel = '',
        cancelLabel = '',
        confirmColor = 'primary',
        onConfirm = () => {},
        loading = false
    } = $props();

    function handleConfirm() {
        onConfirm();
    }

    function handleCancel() {
        open = false;
    }
</script>

<Modal bind:open={open} size="sm" outsideclose>
    <div class="text-center">
        <CircleAlert class="mx-auto mb-4 text-gray-400 w-12 h-12" />
        {#if title}
            <h3 class="mb-2 text-lg font-medium text-gray-900">{title}</h3>
        {/if}
        <p class="mb-5 text-gray-500">{message}</p>
        <div class="flex justify-center gap-3">
            <Button color="alternative" onclick={handleCancel} disabled={loading}>
                {cancelLabel || m.common_cancel()}
            </Button>
            <Button color={confirmColor} onclick={handleConfirm} disabled={loading}>
                {#if loading}
                    <span class="animate-spin mr-2">...</span>
                {/if}
                {confirmLabel || m.common_confirm()}
            </Button>
        </div>
    </div>
</Modal>
