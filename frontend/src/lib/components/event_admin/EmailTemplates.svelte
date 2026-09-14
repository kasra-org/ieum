<script>
    import { Heading, Label, Input, Button, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import MarkdownEditor from '$lib/components/MarkdownEditor.svelte';
    import EmailAttachments from '$lib/components/EmailAttachments.svelte';

    let { data } = $props();

    let success = $state("");
    let failure = $state("");

    // Bodies are markdown and edited in place; attachments are a list the
    // picker rewrites. Seeded from the event and left alone afterwards, so a
    // save that returns the same values does not discard an in-progress edit.
    let registrationBody = $state(data.event.email_template_registration?.body ?? '');
    let abstractBody = $state(data.event.email_template_abstract_submission?.body ?? '');
    let certificateBody = $state(data.event.email_template_certificate?.body ?? '');
    // Older events have no invitation template on the event; the templates
    // endpoint creates one on demand, so read it from there.
    const invitation = data.email_templates?.invitation ?? data.event.email_template_invitation;
    let invitationBody = $state(invitation?.body ?? '');

    let registrationAttachments = $state(data.event.email_template_registration?.attachments ?? []);
    let abstractAttachments = $state(data.event.email_template_abstract_submission?.attachments ?? []);
    let certificateAttachments = $state(data.event.email_template_certificate?.attachments ?? []);
    let invitationAttachments = $state(invitation?.attachments ?? []);

    const afterSubmit = () => {
        return async ({ result, action, update }) => {
            if (result.type === "success") {
                await update({reset: false});
                success = result.data.message;
                failure = "";
            } else {
                failure = result.error.message;
                success = "";
            }
        }
    };
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.emailTemplates_title()}</Heading>
<p class="font-light mb-2">{m.emailTemplates_description()}</p>
<p class="font-light mb-6 text-sm text-gray-500">{m.emailTemplates_richTextHelp()}</p>
<form method="POST" action="?/update_email_templates" use:enhance={afterSubmit}>
    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_registrationConfirmation()}</Heading>
    <div class="mb-6">
        <Label for="email_template_registration_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_registration_subject" name="email_template_registration_subject" value={data.event.email_template_registration.subject} />
    </div>
    <div class="mb-6">
        <MarkdownEditor
            bind:value={registrationBody}
            id="email_template_registration_body"
            name="email_template_registration_body"
            label={m.emailTemplates_body()}
            rows={10}
        />
    </div>
    <div class="mb-6">
        <EmailAttachments
            bind:value={registrationAttachments}
            name="email_template_registration_attachments"
            label={m.emailTemplates_attachments()}
        />
    </div>

    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_abstractSubmissionConfirmation()}</Heading>
    <div class="mb-6">
        <Label for="email_template_abstract_submission_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_abstract_submission_subject" name="email_template_abstract_submission_subject" value={data.event.email_template_abstract_submission.subject} />
    </div>
    <div class="mb-6">
        <MarkdownEditor
            bind:value={abstractBody}
            id="email_template_abstract_submission_body"
            name="email_template_abstract_submission_body"
            label={m.emailTemplates_body()}
            rows={10}
        />
    </div>
    <div class="mb-6">
        <EmailAttachments
            bind:value={abstractAttachments}
            name="email_template_abstract_submission_attachments"
            label={m.emailTemplates_attachments()}
        />
    </div>

    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_certificate()}</Heading>
    <div class="mb-6">
        <Label for="email_template_certificate_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_certificate_subject" name="email_template_certificate_subject" value={data.event.email_template_certificate?.subject ?? ''} />
    </div>
    <div class="mb-6">
        <MarkdownEditor
            bind:value={certificateBody}
            id="email_template_certificate_body"
            name="email_template_certificate_body"
            label={m.emailTemplates_body()}
            rows={10}
        />
    </div>
    <div class="mb-6">
        <EmailAttachments
            bind:value={certificateAttachments}
            name="email_template_certificate_attachments"
            label={m.emailTemplates_attachments()}
        />
    </div>

    <Heading tag="h3" class="text-lg font-bold mb-2">{m.emailTemplates_invitation()}</Heading>
    <p class="font-light mb-6 text-sm text-gray-500">{m.emailTemplates_invitationHelp({ link: '{{ invitation_link }}' })}</p>
    <div class="mb-6">
        <Label for="email_template_invitation_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_invitation_subject" name="email_template_invitation_subject" value={invitation?.subject ?? ''} />
    </div>
    <div class="mb-6">
        <MarkdownEditor
            bind:value={invitationBody}
            id="email_template_invitation_body"
            name="email_template_invitation_body"
            label={m.emailTemplates_body()}
            rows={10}
        />
    </div>
    <div class="mb-6">
        <EmailAttachments
            bind:value={invitationAttachments}
            name="email_template_invitation_attachments"
            label={m.emailTemplates_attachments()}
        />
    </div>

    <div class="mb-6">
        {#if success}
            <Alert color="green">{success}</Alert>
        {/if}
        {#if failure}
            <Alert color="red">{failure}</Alert>
        {/if}
    </div>
    <div class="flex justify-center">
        <Button color="primary" type="submit" size="lg">{m.emailTemplates_update()}</Button>
    </div>
</form>
