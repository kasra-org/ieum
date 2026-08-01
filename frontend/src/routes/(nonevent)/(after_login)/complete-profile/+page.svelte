<script>
    let { data: page_data } = $props();

    import { onMount } from 'svelte';
    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import { Alert, Input, Textarea, Select, Button, Label, InputAddon, ButtonGroup, Heading, Card } from '$lib/components/ui';
    import { CircleUser } from '@lucide/svelte';
    import { goto } from '$app/navigation';
    import * as m from '$lib/paraglide/messages.js';
    import { onlyLatinChars } from '$lib/utils.js';

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';

    let success = $state(false);
    let serverError = $state('');

    const schema = yup.object({
        email: yup.string().email().required(),
        // English name is always required for all users (Latin characters only)
        first_name: yup.string().required(m.validation_firstNameRequired()).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        last_name: yup.string().required(m.validation_lastNameRequired()).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        middle_initial: yup.string().max(1).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        // Korean name is required for Korean nationals, optional for others
        korean_name: yup.string().when('nationality', {
            is: '1',
            then: (schema) => schema.required(m.validation_koreanNameRequired()),
            otherwise: (schema) => schema
        }),
        nationality: yup.string().required(m.validation_nationalityRequired()),
        job_title: yup.string().required(m.validation_jobTitleRequired()),
        department: yup.string(),
        institute: yup.mixed().transform((value, originalValue) => {
            if (typeof originalValue === 'number') return originalValue;
            if (originalValue === '' || originalValue === null || originalValue === undefined) return undefined;
            const num = Number(originalValue);
            return isNaN(num) ? undefined : num;
        }).required(m.validation_instituteRequired()),
        orcid: yup.string(),
        google: yup.string(),
        disability: yup.string(),
        dietary: yup.string(),
    });

    let form_config = {
        next: page_data.next,
        action: 'complete-profile',
        hide_password: true,
        hide_login_info: true,
        show_english_name: true,
        show_korean_name: true,
        csrf_token: page_data.csrf_token,
    }

    let me = page_data.user;

    const { form: felteForm, data, errors, isSubmitting } = createForm({
        initialValues: {
            email: me.email,
            first_name: me.first_name || '',
            middle_initial: me.middle_initial || '',
            korean_name: me.korean_name || '',
            last_name: me.last_name || '',
            nationality: me.nationality ? me.nationality.toString() : undefined,
            institute: me.institute,
            department: me.department || '',
            job_title: me.job_title || '',
            disability: me.disability || '',
            dietary: me.dietary || '',
            orcid: me.orcid || '',
            google: me.google || '',
        },
        onSubmit: async (formData) => {
            success = false;
            serverError = '';
            formData.username = formData.email;
            formData.next = page_data.next;

            const response = await fetch('?/update',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                    },
                    body: new URLSearchParams(formData),
                }
            );
            if (!response.ok || response.status !== 200) {
                // Check if it's a redirect (profile complete)
                if (response.redirected) {
                    window.location.href = response.url;
                    return;
                }
                const rtn = await response.json();
                serverError = rtn.error?.message || 'An error occurred. Please try again.';
                throw rtn.error;
            }
            // If we get here, the server should have redirected us
            // But just in case, redirect manually
            window.location.href = page_data.next;
        },
        extend: validator({ schema }),
        onError: (err) => {
            return err;
        }
    });
</script>

<svelte:head>
    <title>{m.completeProfile_title()} | {page_data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.completeProfile_title()}</h1>
        <p class="text-slate-200 mt-2">{m.completeProfile_description()}</p>
    </div>
</div>

<!-- Info Alert -->
<Alert color="blue" class="mb-6">
    <span class="font-medium">{m.completeProfile_infoTitle()}</span> {m.completeProfile_infoMessage()}
</Alert>

<!-- Form Card -->
<div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
    <form use:felteForm method="post">
        <input type="hidden" name="next" value={page_data.next} />
        <RegistrationForm data={$data} errors={$errors} config={form_config} institution_resolved={page_data.user?.institution_resolved} />
        {#if serverError}
        <Alert color="red" class="mb-4" dismissable>{serverError}</Alert>
        {/if}
        <div class="flex flex-col md:flex-row justify-center gap-4 mt-8">
            <Button type="submit" size="lg" color="primary" disabled={$isSubmitting}>{m.completeProfile_submit()}</Button>
        </div>
    </form>
</div>
