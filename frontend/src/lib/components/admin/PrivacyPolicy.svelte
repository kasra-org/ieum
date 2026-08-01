<script>
    import { Button, Alert, Helper, Textarea } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const initialPolicy = data.admin.privacyPolicy || { content_en: '', content_ko: '' };
    let content_en = $state(initialPolicy.content_en);
    let content_ko = $state(initialPolicy.content_ko);
    let save_success = $state(false);
    let save_error = $state('');

    const afterSave = () => {
        return async ({ result }) => {
            if (result.type === "success") {
                save_success = true;
                save_error = '';
                setTimeout(() => { save_success = false; }, 3000);
            } else {
                save_error = result.error?.message || 'An error occurred';
                save_success = false;
            }
        }
    };
</script>

<h2 class="text-2xl font-bold mb-2">{m.admin_privacyPolicy_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_privacyPolicy_description()}</p>

<Alert color="blue" class="mb-6">
    <p class="font-medium mb-2">{m.admin_privacyPolicy_templateHelp()}</p>
    <ul class="list-disc list-inside text-sm space-y-1">
        <li><code class="bg-blue-100 px-1 rounded">{'{{ business_name }}'}</code> - {m.admin_privacyPolicy_varBusinessName()}</li>
        <li><code class="bg-blue-100 px-1 rounded">{'{{ business_registration_number }}'}</code> - {m.admin_privacyPolicy_varRegistrationNumber()}</li>
        <li><code class="bg-blue-100 px-1 rounded">{'{{ address }}'}</code> - {m.admin_privacyPolicy_varAddress()}</li>
        <li><code class="bg-blue-100 px-1 rounded">{'{{ representative }}'}</code> - {m.admin_privacyPolicy_varRepresentative()}</li>
        <li><code class="bg-blue-100 px-1 rounded">{'{{ phone }}'}</code> - {m.admin_privacyPolicy_varPhone()}</li>
        <li><code class="bg-blue-100 px-1 rounded">{'{{ email }}'}</code> - {m.admin_privacyPolicy_varEmail()}</li>
    </ul>
</Alert>

<form method="post" action="?/update_privacy_policy" use:enhance={afterSave}>
    <!-- Korean Privacy Policy (Legally Binding) -->
    <div class="mb-8">
        <h3 class="text-lg font-semibold mb-2">{m.admin_privacyPolicy_korean()}</h3>
        <Helper class="mb-3">{m.admin_privacyPolicy_koreanBindingNote()}</Helper>
        <Textarea
            id="content_ko"
            name="content_ko"
            rows={15}
            class="w-full font-mono"
            bind:value={content_ko}
            placeholder={m.admin_privacyPolicy_placeholder()}
        />
    </div>

    <!-- English Privacy Policy -->
    <div class="mb-6">
        <h3 class="text-lg font-semibold mb-2">{m.admin_privacyPolicy_english()}</h3>
        <Helper class="mb-3">{m.admin_privacyPolicy_englishNote()}</Helper>
        <Textarea
            id="content_en"
            name="content_en"
            rows={15}
            class="w-full font-mono"
            bind:value={content_en}
            placeholder={m.admin_privacyPolicy_placeholder()}
        />
    </div>

    {#if save_success}
        <Alert color="green" class="mb-4">{m.admin_privacyPolicy_success()}</Alert>
    {/if}
    {#if save_error}
        <Alert color="red" class="mb-4">{save_error}</Alert>
    {/if}
    <div class="flex justify-end">
        <Button color="primary" type="submit">{m.admin_privacyPolicy_save()}</Button>
    </div>
</form>
