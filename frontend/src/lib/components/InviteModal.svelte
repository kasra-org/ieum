<script>
    // Invite people who have not registered: each address gets its own link,
    // and opening it registers them - creating the account first if needed.
    // The body starts from the event's invitation template and is a template
    // itself: {{ invitation_link }} is filled in per recipient on the server.
    import { Modal, Button, Label, Input, Textarea, Checkbox, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import MarkdownEditor from '$lib/components/MarkdownEditor.svelte';

    let { open = $bindable(false), template = null } = $props();

    let emails = $state('');
    let subject = $state('');
    let body = $state('');
    let feeWaived = $state(false);
    let error_message = $state('');
    let successModal = $state(false);
    let sentCount = $state(0);

    // Seed from the template each time the modal opens, so an edit made for
    // one batch does not leak into the next; the modal's content unmounts when
    // it closes, which is what makes the editor pick the new value up.
    $effect(() => {
        if (open) {
            emails = '';
            subject = template?.subject ?? '';
            body = template?.body ?? '';
            feeWaived = false;
            error_message = '';
        }
    });

    let recipientCount = $derived(
        emails.split(/[;,\s]+/).map(e => e.trim()).filter(e => e.includes('@')).length
    );

    const afterSubmit = () => {
        return async ({ result, update }) => {
            if (result.type === 'success') {
                sentCount = recipientCount;
                await update({ reset: false });
                open = false;
                successModal = true;
            } else {
                error_message = result.error?.message || m.invite_sendError();
            }
        };
    };
</script>

<Modal id="invite_modal" size="lg" title={m.invite_title()} bind:open outsideclose>
    <form method="post" action="?/send_invitations" use:enhance={afterSubmit}>
        <p class="text-sm text-gray-600 dark:text-gray-400 mb-6">{m.invite_description()}</p>

        <div class="mb-6">
            <Label for="invite_emails" class="block mb-2">{m.invite_recipients()}</Label>
            <Textarea id="invite_emails" name="emails" rows="3" bind:value={emails}
                placeholder={m.invite_recipientsPlaceholder()} class="w-full" />
            <p class="mt-1 text-xs text-gray-500">{m.invite_recipientsHelp()}</p>
        </div>

        <div class="mb-6">
            <Label for="invite_subject" class="block mb-2">{m.attendees_subject()}</Label>
            <Input id="invite_subject" name="subject" bind:value={subject} />
        </div>

        <div class="mb-6">
            <MarkdownEditor bind:value={body} id="invite_body" name="body" label={m.attendees_message()} rows={10} />
            <p class="mt-1 text-xs text-gray-500">{m.invite_linkHelp()}</p>
        </div>

        <div class="mb-6">
            <input type="hidden" name="fee_waived" value={feeWaived ? 'true' : 'false'} />
            <Checkbox bind:checked={feeWaived}>{m.invite_waiveFee()}</Checkbox>
            <p class="mt-1 ms-6 text-xs text-gray-500">{m.invite_waiveFeeHelp()}</p>
        </div>

        {#if error_message}
            <Alert color="red" class="mb-6">{error_message}</Alert>
        {/if}

        <div class="flex justify-center gap-2">
            <Button color="primary" type="submit" disabled={recipientCount === 0}>
                {m.invite_send({ count: recipientCount })}
            </Button>
            <Button color="light" type="button" onclick={() => open = false}>{m.common_cancel()}</Button>
        </div>
    </form>
</Modal>

<Modal size="sm" bind:open={successModal} outsideclose>
    <div class="text-center p-4">
        <p class="text-lg mb-4">{m.invite_sentSuccess({ count: sentCount })}</p>
        <Button color="primary" onclick={() => successModal = false}>{m.attendees_ok()}</Button>
    </div>
</Modal>
