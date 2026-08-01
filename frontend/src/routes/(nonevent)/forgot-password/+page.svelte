<script>
    import { enhance } from '$app/forms';
    import { goto } from '$app/navigation';

    import { A, List, Li, Card, Button, Heading, Indicator, Label, Input, Dropzone, Checkbox, Select, Alert, Navbar } from '$lib/components/ui';
    import { onMount } from 'svelte';
    import * as m from '$lib/paraglide/messages.js';

    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';

    let { data, form } = $props();

    const schema = yup.object({
        email: yup.string().required(m.validation_emailRequired()),
    });

    let me = data.user;
    let submitted = $state(false);
    let error_message = $state('');
    let success_message = $state('');
    const { form: felteForm, data: formData, errors, isSubmitting } = createForm({
        onSubmit: async (data) => {
            const response = await fetch('?/password',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                    },
                    body: new URLSearchParams(data),
                }
            );
            if (!response.ok || response.status !== 200) {
                const rtn = await response.json();
                throw rtn.error;
            } else {
                submitted = true;
                success_message = m.forgotPassword_successMessage();
            }
        },
        extend: validator({ schema }),
        onError: (errors) => {
            // scroll to top
            error_message = errors.message;
            return errors;
        }
    });
</script>

<svelte:head>
    <title>{m.forgotPassword_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.forgotPassword_title()}</h1>
        <p class="text-slate-200 mt-2">{m.forgotPassword_description()}</p>
    </div>
</div>

<!-- Form Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <form use:felteForm method="post">
        <div class="mb-6">
            <Label for="email" class="block mb-2">{m.form_email()} <span class="text-red-500">*</span></Label>
            <Input id="email" name="email" type="email" bind:value={$formData.email} />
            {#if $errors.email}
                <Alert type="error" color="red" class="mb-6 mt-3">
                    <p class="text-sm">{$errors.email}</p>
                </Alert>
            {/if}
        </div>
        {#if error_message}
            <Alert type="error" color="red" class="mb-6 mt-3">
                <p class="text-sm">{error_message}</p>
            </Alert>
        {/if}
        {#if success_message}
            <Alert type="success" color="green" class="mb-6 mt-3">
                <p class="text-sm">{success_message}</p>
            </Alert>
        {/if}
        <div class="flex flex-col md:flex-row justify-center gap-4 mt-8">
            <Button type="submit" color="primary" size="lg" disabled={$isSubmitting || submitted}>{m.forgotPassword_submit()}</Button>
            <Button href={data.next} color="alternative" size="lg" data-sveltekit-reload>{m.common_goBack()}</Button>
        </div>
    </form>
</div>