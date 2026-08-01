<script>
    import { goto } from '$app/navigation';
    import { Alert, Button, Label, Input } from '$lib/components/ui';
    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const schema = yup.object({
        password: yup.string().required(m.validation_passwordRequired()).min(8, m.validation_passwordMinLength()),
        confirm_password: yup.string().required(m.validation_passwordsMismatch()).oneOf([yup.ref('password'), null], m.validation_passwordsMismatch()),
    });

    let error_message = $state('');
    let success_message = $state('');
    let submitted = $state(false);

    const { form: felteForm, data: formData, errors, isSubmitting } = createForm({
        onSubmit: async (formData) => {
            const response = await fetch('?/password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                },
                body: new URLSearchParams(formData),
            });
            if (!response.ok || response.status !== 200) {
                const rtn = await response.json();
                throw rtn.error;
            } else {
                submitted = true;
                success_message = m.resetPassword_successMessage();
            }
        },
        extend: validator({ schema }),
        onError: (errors) => {
            error_message = errors.message;
            return errors;
        }
    });
</script>

<svelte:head>
    <title>{m.resetPassword_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.resetPassword_title()}</h1>
        <p class="text-slate-200 mt-2">{m.resetPassword_description()}</p>
    </div>
</div>

<!-- Form Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <form use:felteForm method="post">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div class="mb-6">
                <Label for="password" class="block mb-2">{m.form_password()} <span class="text-red-500">*</span></Label>
                <Input id="password" name="password" type="password" bind:value={$formData.password} />
                {#if $errors.password}
                <Alert type="error" color="red" class="mb-6 mt-3">
                    <p class="text-sm">{$errors.password}</p>
                </Alert>
                {/if}
            </div>
            <div class="mb-6">
                <Label for="confirm_password" class="block mb-2">{m.form_confirmPassword()} <span class="text-red-500">*</span></Label>
                <Input id="confirm_password" name="confirm_password" type="password" bind:value={$formData.confirm_password} />
                {#if $errors.confirm_password}
                <Alert type="error" color="red" class="mb-6 mt-3">
                    <p class="text-sm">{$errors.confirm_password}</p>
                </Alert>
                {/if}
            </div>
            <input type="hidden" name="key" value={data.key} />
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
            {#if submitted}
            <Button onclick={() => goto('/login')} color="primary" size="lg">{m.resetPassword_loginButton()}</Button>
            {:else}
            <Button type="submit" color="primary" size="lg" disabled={$isSubmitting}>{m.resetPassword_submit()}</Button>
            {/if}
        </div>
    </form>
</div>
