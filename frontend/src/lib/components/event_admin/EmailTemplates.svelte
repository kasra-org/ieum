<script>
    import { Heading, Label, Input, Textarea, Button, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    let success = $state("");
    let failure = $state("");

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
<p class="font-light mb-6">{m.emailTemplates_description()}</p>
<form method="POST" action="?/update_email_templates" use:enhance={afterSubmit}>
    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_registrationConfirmation()}</Heading>
    <div class="mb-6">
        <Label for="email_template_registration_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_registration_subject" name="email_template_registration_subject" value={data.event.email_template_registration.subject} />
    </div>
    <div class="mb-6">
        <Label for="email_template_registration_body" class="block mb-2">{m.emailTemplates_body()}</Label>
        <Textarea id="email_template_registration_body" name="email_template_registration_body" rows="10" value={data.event.email_template_registration.body} class="w-full" />
    </div>
    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_abstractSubmissionConfirmation()}</Heading>
    <div class="mb-6">
        <Label for="email_template_abstract_submission_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_abstract_submission_subject" name="email_template_abstract_submission_subject" value={data.event.email_template_abstract_submission.subject} />
    </div>
    <div class="mb-6">
        <Label for="email_template_abstract_submission_body" class="block mb-2">{m.emailTemplates_body()}</Label>
        <Textarea id="email_template_abstract_submission_body" name="email_template_abstract_submission_body" rows="10" value={data.event.email_template_abstract_submission.body} class="w-full" />
    </div>
    <Heading tag="h3" class="text-lg font-bold mb-6">{m.emailTemplates_certificate()}</Heading>
    <div class="mb-6">
        <Label for="email_template_certificate_subject" class="block mb-2">{m.emailTemplates_subject()}</Label>
        <Input id="email_template_certificate_subject" name="email_template_certificate_subject" value={data.event.email_template_certificate?.subject ?? ''} />
    </div>
    <div class="mb-6">
        <Label for="email_template_certificate_body" class="block mb-2">{m.emailTemplates_body()}</Label>
        <Textarea id="email_template_certificate_body" name="email_template_certificate_body" rows="10" value={data.event.email_template_certificate?.body ?? ''} class="w-full" />
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
