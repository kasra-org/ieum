<script>
    import { goto } from '$app/navigation';

    import { A, Card, Button, Heading, Indicator, Label, Input, Checkbox, Select, Alert, Navbar, Textarea } from '$lib/components/ui';
    import { onMount } from 'svelte';

    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import * as m from '$lib/paraglide/messages.js';
    import { onlyLatinChars } from '$lib/utils.js';
    import { languageTag } from '$lib/paraglide/runtime.js';

    import OnSiteRegistrationForm from '$lib/components/OnSiteRegistrationForm.svelte';

    let { data, form } = $props();

    let event = $derived(data.event);

    let form_config = {
        hide_login_info: true,
    };

    const schema = yup.object({
        name: yup.string().required(m.onsiteRegistration_nameRequired()),
        email: yup.string().required(m.onsiteRegistration_emailRequired()).email(m.onsiteRegistration_emailInvalid()),
        institute: yup.string().required(m.onsiteRegistration_instituteRequired()),
        job_title: yup.string().required(m.onsiteRegistration_jobTitleRequired()),
    });

    let onsite_code_valid = $derived(data.onsite_code_valid);
    let onsite_code = $derived(data.onsite_code);

    // Same categories as normal registration, priced separately for the desk.
    // Mirrors Event.onsite_fee_for(); the server recomputes before charging.
    const onsiteFeeForTier = (tier) => {
        if (tier === 'undergraduate' && event.undergraduate_enabled) return event.onsite_registration_fee_undergraduate || 0;
        if (tier === 'graduate' && event.graduate_enabled) return event.onsite_registration_fee_graduate || 0;
        return event.onsite_registration_fee || 0;
    };
    const tierOptions = [
        ...(event.undergraduate_enabled ? [{ value: 'undergraduate', label: m.eventRegister_tierUndergraduate() }] : []),
        ...(event.graduate_enabled ? [{ value: 'graduate', label: m.eventRegister_tierGraduate() }] : []),
        { value: 'pi_non_academic', label: m.eventRegister_tierPiNonAcademic() },
    ];
    let studentStatus = $state(tierOptions[0]?.value ?? 'pi_non_academic');

    const formatFee = (fee) => fee
        ? (languageTag() === 'ko' ? `${fee.toLocaleString('ko-KR')} 원` : `KRW ${fee.toLocaleString('ko-KR')}`)
        : '';

    // Payment is taken at the desk, so the amount is stated before the form
    // rather than surprising the walk-in on the next screen.
    let onsiteFee = $derived(onsiteFeeForTier(studentStatus));
    let formattedOnsiteFee = $derived(formatFee(onsiteFee));
    let hasOnsiteFee = $derived(event.has_onsite_fee);
    let showTierChoice = $derived(hasOnsiteFee && tierOptions.length > 1);

    let error_message = $state('');
    const { form: felteForm, data: formData, errors, isSubmitting } = createForm({
        onSubmit: async (formValues) => {
            const submitData = { ...formValues, code: onsite_code, student_status: studentStatus };
            const response = await fetch('?/onsiteregister',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                    },
                    body: new URLSearchParams(submitData),
                }
            );
            const rtn = await response.json();
            if (!response.ok || response.status !== 200) {
                throw rtn.error;
            }
            // rtn should be 303 see other
            if (rtn.status !== 303) {
                throw new Error('Unexpected response status: ' + rtn.status);
            }
            goto(rtn.location);
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
    <title>{m.onsiteRegistration_title()} - {event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{event.name}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/" class="hover:underline">{m.eventDetail_breadcrumbEvents()}</a>
                <span class="mx-2">/</span>
                <a href="/event/{event.id}" class="hover:underline">{event.name}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">{m.onsiteRegistration_title()}</span>
            </p>
        </div>
    </div>

    <!-- Main Content -->
    <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
        <Heading tag="h1" class="text-2xl font-bold mb-3">{m.onsiteRegistration_title()}</Heading>
        {#if onsite_code_valid}
            <p class="mb-6 font-light">{m.onsiteRegistration_description()}</p>
            {#if showTierChoice}
                <div class="mb-6 rounded-lg border border-gray-200 p-4">
                    <p class="mb-1 font-medium text-gray-900">
                        {m.eventRegister_selectTier()} <span class="text-red-500">*</span>
                    </p>
                    <p class="mb-4 text-sm text-gray-500">{m.eventRegister_selectTierHelp()}</p>
                    <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
                        {#each tierOptions as option}
                            <label class="flex cursor-pointer items-start gap-3 rounded-lg border-2 p-3 transition-colors
                                {studentStatus === option.value ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}">
                                <input type="radio" name="student_status" value={option.value}
                                    bind:group={studentStatus} class="mt-1 h-4 w-4" />
                                <span>
                                    <span class="block text-sm font-medium text-gray-900">{option.label}</span>
                                    <span class="block text-sm text-gray-600">{formatFee(onsiteFeeForTier(option.value)) || m.eventDetail_registrationFeeFree()}</span>
                                </span>
                            </label>
                        {/each}
                    </div>
                </div>
            {/if}
            {#if onsiteFee > 0}
                <div class="mb-8 rounded-lg border border-amber-200 bg-amber-50 p-4">
                    <div class="flex items-baseline justify-between gap-4">
                        <span class="font-medium text-gray-900">{m.onsiteRegistration_feeNotice()}</span>
                        <span class="text-xl font-bold text-primary-600">{formattedOnsiteFee}</span>
                    </div>
                    <p class="mt-2 text-sm text-gray-700">{m.onsiteRegistration_payAtDesk()}</p>
                </div>
            {/if}
            <form use:felteForm method="post" class="space-y-5">
                <OnSiteRegistrationForm errors={$errors} />
                {#if error_message}
                    <Alert color="red" class="mb-4 error">{error_message}</Alert>
                {/if}
                <div class="flex flex-col md:flex-row justify-center gap-4">
                    <Button type="submit" color="primary" size="lg">{m.onsiteRegistration_register()}</Button>
                </div>
            </form>
        {:else}
            <Alert color="red" class="mt-4">{m.onsiteRegistration_invalidCode()}</Alert>
        {/if}
    </div>
</div>
