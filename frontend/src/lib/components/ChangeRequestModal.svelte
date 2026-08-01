<script>
    import { Button, Alert, Modal, Textarea, Spinner } from '$lib/components/ui';
    import * as m from '$lib/paraglide/messages.js';
    import { enhance } from '$app/forms';

    let { open = $bindable(false), actionUrl = '?/changeRequest', eventId = null } = $props();

    let changeRequestMessage = $state('');
    let isSubmitting = $state(false);
    let submitSuccess = $state(false);
    let submitError = $state('');

    function handleEnhance() {
        isSubmitting = true;
        submitError = '';

        return async ({ result }) => {
            isSubmitting = false;
            if (result.type === 'success' && result.data?.success) {
                submitSuccess = true;
                changeRequestMessage = '';
            } else {
                submitError = result.data?.error || m.common_error();
            }
        };
    }

    function closeModal() {
        open = false;
        submitSuccess = false;
        submitError = '';
        changeRequestMessage = '';
    }
</script>

<Modal bind:open size="md" title={m.changeRequest_title()} outsideclose>
    {#if submitSuccess}
        <div class="text-center py-4">
            <Alert color="green" class="mb-4">
                {m.changeRequest_success()}
            </Alert>
            <Button color="primary" onclick={closeModal}>{m.common_close()}</Button>
        </div>
    {:else}
        <form method="POST" action={actionUrl} use:enhance={handleEnhance}>
            {#if eventId}
                <input type="hidden" name="eventId" value={eventId} />
            {/if}
            <p class="text-gray-600 mb-4">{m.changeRequest_description()}</p>
            <Textarea
                name="message"
                bind:value={changeRequestMessage}
                placeholder={m.changeRequest_placeholder()}
                rows="10"
                class="w-full mb-4"
            />
            {#if submitError}
                <Alert color="red" class="mb-4">{submitError}</Alert>
            {/if}
            <div class="flex justify-end gap-3">
                <Button color="light" type="button" onclick={closeModal}>{m.common_cancel()}</Button>
                <Button
                    color="primary"
                    type="submit"
                    disabled={isSubmitting || !changeRequestMessage.trim()}
                >
                    {#if isSubmitting}
                        <Spinner size="4" class="mr-2" />
                    {/if}
                    {m.common_submit()}
                </Button>
            </div>
        </form>
    {/if}
</Modal>
