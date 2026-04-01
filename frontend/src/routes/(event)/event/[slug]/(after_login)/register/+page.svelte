<script>
    import { enhance } from '$app/forms';
    import { goto, invalidateAll } from '$app/navigation';

    import { A, Card, Button, Heading, Indicator, Label, Input, Checkbox, Select, Alert, Navbar, Textarea, ProgressStepper, Modal, Spinner } from 'flowbite-svelte';
    import { ClipboardListSolid, CheckCircleSolid, CheckCircleOutline, CreditCardSolid } from 'flowbite-svelte-icons';
    import { onMount } from 'svelte';

    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import { get } from 'svelte/store';

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';
    import { requestCardPayment } from '$lib/tossPayments.js';
    import { renderPayPalButtons } from '$lib/paypalPayments.js';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { formatDateRange, onlyLatinChars, generateOrderId } from '$lib/utils.js';
    import 'academicons';

    let { data, form } = $props();

    let event = data.event;
    const isFreeEvent = event.registration_fee === null || event.registration_fee === 0;
    const startAtPaymentStep = data.startAtPaymentStep || false;

    // Stepper state and configuration
    // Start at step 3 if user is already registered but needs to pay
    let currentStep = $state(startAtPaymentStep ? 3 : 1);
    const steps = $derived(
        isFreeEvent
            ? [
                { id: 1, label: m.eventRegister_stepRegistration(), icon: ClipboardListSolid },
                { id: 2, label: m.eventRegister_stepConfirm(), icon: CheckCircleSolid }
            ]
            : [
                { id: 1, label: m.eventRegister_stepRegistration(), icon: ClipboardListSolid },
                { id: 2, label: m.eventRegister_stepConfirmRegister(), icon: CheckCircleSolid },
                { id: 3, label: m.eventRegister_stepPayment(), icon: CreditCardSolid }
            ]
    );
    let deadline = event.registration_deadline ? new Date(event.registration_deadline) : new Date(event.start_date);
    deadline.setHours(23, 59, 59, 999);
    let now = new Date();

    // Determine which languages are included in the event
    const hasEnglish = event.main_languages && event.main_languages.includes('en');
    const hasKorean = event.main_languages && event.main_languages.includes('ko');

    let form_config = {
        hide_login_info: true,
        show_english_name: hasEnglish,
        show_korean_name: hasKorean,
        allow_korean_institute: hasKorean,
    };

    // Build dynamic validation schema based on event languages and nationality
    const schemaFields = {
        nationality: yup.string().required(),
        // All personal info fields allow all languages (set by institution modal or user input)
        job_title: yup.string().required(m.validation_jobTitleRequired()),
        department: yup.string(),
        institute: yup.mixed().transform((value, originalValue) => {
            // If it's already a number, return it
            if (typeof originalValue === 'number') return originalValue;
            // If it's an empty string, return undefined to trigger required validation
            if (originalValue === '' || originalValue === null || originalValue === undefined) return undefined;
            // Otherwise convert to number
            const num = Number(originalValue);
            return isNaN(num) ? undefined : num;
        }).required(m.validation_instituteRequired()),
        disability: yup.string(),
        dietary: yup.string(),
    };

    // English name fields - required if:
    // 1. Event includes English (always mandatory), OR
    // 2. Nationality is Non-Korean or Prefer not to say
    if (hasEnglish) {
        // Event has English - fields are always required
        schemaFields.first_name = yup.string().required(m.validation_firstNameRequired()).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars);
        schemaFields.last_name = yup.string().required(m.validation_lastNameRequired()).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars);
        schemaFields.middle_initial = yup.string().max(1).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars);
    } else {
        // Event doesn't have English - fields required only for non-Korean nationals
        schemaFields.first_name = yup.string().when('nationality', {
            is: (val) => val === '2' || val === '3', // Non-Korean or Prefer not to say
            then: (schema) => schema.required(m.validation_firstNameRequired()).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars),
            otherwise: (schema) => schema
        });

        schemaFields.last_name = yup.string().when('nationality', {
            is: (val) => val === '2' || val === '3',
            then: (schema) => schema.required(m.validation_lastNameRequired()).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars),
            otherwise: (schema) => schema
        });

        schemaFields.middle_initial = yup.string().max(1).test('no-korean', m.eventRegister_validationNoKorean(), onlyLatinChars);
    }

    // Korean name field - required only if event is Korean-only AND nationality is Korean
    schemaFields.korean_name = yup.string().when('nationality', {
        is: '1', // Korean
        then: (schema) => (hasKorean && !hasEnglish)
            ? schema.required(m.validation_koreanNameRequired())
            : schema,
        otherwise: (schema) => schema // Optional for non-Korean
    });

    // Add invitation code validation if event is invitation-only
    const isInvitationOnly = event.is_invitation_only;
    if (isInvitationOnly) {
        schemaFields.invitation_code = yup.string().required(m.validation_invitationCodeRequired());
    }

    const schema = yup.object(schemaFields);

    let me = data.user;
    let error_message = $state('');
    let invitation_code_error = $state('');
    let isSubmittingFinal = $state(false);
    let checkoutModalOpen = $state(false);
    let checkoutStatus = $state('processing'); // 'processing' or 'success'
    let instituteDisplayName = $state('');

    // Payment method selection (for paid events)
    let paymentMethod = $state('toss'); // 'toss' or 'paypal'
    let paypalButtonsRendered = $state(false);
    let paypalContainerRef = $state(null);

    const { form: felteForm, data: formData, errors, isSubmitting, validate } = createForm({
        initialValues: {
            first_name: me?me.first_name:'',
            middle_initial: me?me.middle_initial:'',
            korean_name: me?(me.korean_name || ''):'',
            last_name: me?me.last_name:'',
            nationality: me?(me.nationality ? me.nationality.toString() : '1'):'1',
            institute: me && me.institute ? Number(me.institute) : null,
            department: me?me.department:'',
            job_title: me?me.job_title:'',
            disability: me?me.disability:'',
            dietary: me?me.dietary:'',
            invitation_code: '',
        },
        extend: validator({ schema }),
        transform: (values) => ({
            ...values,
            institute: values.institute ? Number(values.institute) : null,
        }),
    });

    // Handler for "Next Step" button - validates and shows summary
    async function handleNextStep() {
        // Read store values synchronously before async calls
        const currentFormData = get(formData);

        await validate();

        // Read errors after validation completes
        const currentErrors = get(errors);
        const errorEntries = Object.entries(currentErrors).filter(([, err]) => err && err.length > 0);

        if (errorEntries.length > 0) {
            // Scroll to the first field with an error
            const firstErrorField = errorEntries[0][0];
            const el = document.getElementById(firstErrorField);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.focus();
            }
            return;
        }

        // Verify invitation code if event is invitation-only
        if (isInvitationOnly) {
            invitation_code_error = '';
            try {
                const fd = new FormData();
                fd.append('invitation_code', currentFormData.invitation_code || '');
                const response = await fetch('?/verify_invitation_code', {
                    method: 'POST',
                    body: fd
                });
                if (!response.ok) {
                    invitation_code_error = m.validation_invalidInvitationCode();
                    const el = document.getElementById('invitation_code');
                    if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        el.focus();
                    }
                    return;
                }
            } catch (err) {
                invitation_code_error = m.validation_invalidInvitationCode();
                return;
            }
        }

        error_message = '';
        currentStep = 2;
    }

    // Handle step 2 confirmation - for free events, register directly; for paid events, register then go to step 3
    async function handleConfirmAndRegister() {
        error_message = '';
        isSubmittingFinal = true;

        if (isFreeEvent) {
            // Free event - submit registration directly
            await submitRegistration();
        } else {
            // Paid event - submit registration first, then move to payment step
            await submitRegistrationForPayment();
        }
    }

    // Handle registration error - navigate back to step 1 if needed
    function handleRegistrationError(message) {
        error_message = message;
        currentStep = 1;
        isSubmittingFinal = false;
        // Scroll to the relevant field after DOM update
        requestAnimationFrame(() => {
            const el = document.getElementById('invitation_code') || document.querySelector('.error');
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                el.focus?.();
            }
        });
    }

    // Submit registration for paid events (before payment)
    async function submitRegistrationForPayment() {
        try {
            const response = await fetch('?/register',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                    },
                    body: new URLSearchParams($formData),
                }
            );

            if (!response.ok || response.status !== 200) {
                let msg = 'Registration failed';
                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const rtn = await response.json();
                        msg = rtn.error?.message || msg;
                    } else {
                        const text = await response.text();
                        msg = text || msg;
                    }
                } catch (parseErr) {}
                handleRegistrationError(msg);
                return;
            }

            // Registration successful - move to payment step
            // Note: Don't call invalidateAll() here to avoid triggering the redirect in the load function
            isSubmittingFinal = false;
            currentStep = 3;
        } catch (err) {
            console.error('Registration error:', err);
            handleRegistrationError(err.message || 'Registration failed');
        }
    }

    // Handle payment initiation (step 3)
    async function handlePayment() {
        error_message = '';
        isSubmittingFinal = true;

        try {
            // Save event info to sessionStorage for retrieval after payment
            // Note: Attendee is already created in step 2, we just need eventId for payment confirmation
            const paymentData = {
                eventId: event.id,
                eventSlug: event.slug || event.id,
            };
            sessionStorage.setItem('pendingPayment', JSON.stringify(paymentData));

            // Generate unique order ID
            const orderId = generateOrderId();

            // Get user info for Toss
            const user = data.user;
            const customerName = user?.korean_name || `${user?.first_name || ''} ${user?.last_name || ''}`.trim() || 'Guest';

            // Open Toss payment
            await requestCardPayment({
                customerKey: `user-${user?.id || 'anonymous'}`,
                amount: event.registration_fee,
                orderId: orderId,
                orderName: event.name,
                successUrl: `${window.location.origin}/payment/success`,
                failUrl: `${window.location.origin}/payment/fail`,
                customerEmail: user?.email,
                customerName: customerName,
            });
        } catch (err) {
            console.error('Payment initiation failed:', err);
            error_message = err.message || m.eventRegister_paymentError?.() || 'Payment failed';
            isSubmittingFinal = false;
            // Clear stored data on error
            sessionStorage.removeItem('pendingPayment');
        }
    }

    // Actual registration submission
    async function submitRegistration() {
        isSubmittingFinal = true;
        error_message = '';

        try {
            const response = await fetch('?/register',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                    },
                    body: new URLSearchParams($formData),
                }
            );

            if (!response.ok || response.status !== 200) {
                let msg = 'Registration failed';
                try {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const rtn = await response.json();
                        msg = rtn.error?.message || msg;
                    } else {
                        const text = await response.text();
                        msg = text || msg;
                    }
                } catch (parseErr) {}
                handleRegistrationError(msg);
                return;
            }

            // Success - invalidate all cached data and redirect to event page
            await invalidateAll();
            goto(`/event/${event.id}`);
        } catch (err) {
            console.error('Registration error:', err);
            handleRegistrationError(err.message || 'Registration failed');
        }
    }

    function goBackStep() {
        error_message = '';
        if (currentStep > 1) {
            currentStep = currentStep - 1;
        }
    }

    // Format registration fee
    const formattedRegistrationFee = $derived(() => {
        const fee = event.registration_fee || 0;
        if (fee === 0) return m.eventDetail_registrationFeeFree();
        const formattedAmount = fee.toLocaleString('ko-KR', {maximumFractionDigits: 0});
        return languageTag() === 'ko' ? `${formattedAmount} 원` : `KRW ${formattedAmount}`;
    });

    // Render PayPal buttons when PayPal is selected and on step 3
    $effect(() => {
        if (currentStep === 3 && paymentMethod === 'paypal' && !paypalButtonsRendered) {
            // Small delay to ensure the container is rendered
            setTimeout(() => {
                const container = document.getElementById('paypal-button-container');
                if (container && !paypalButtonsRendered) {
                    renderPayPalButtons({
                        containerId: 'paypal-button-container',
                        amount: event.registration_fee,
                        onSuccess: handlePayPalSuccess,
                        onError: handlePayPalError,
                        onCancel: handlePayPalCancel,
                    });
                    paypalButtonsRendered = true;
                }
            }, 100);
        }
    });

    // Handle PayPal payment success
    function handlePayPalSuccess(result) {
        // Store payment result in sessionStorage for the success page
        sessionStorage.setItem('paymentResult', JSON.stringify({
            success: true,
            event_id: event.id,
            event_name: event.name,
            payment_method: 'paypal',
            ...result
        }));
        // Redirect to success page
        goto('/payment/success');
    }

    // Handle PayPal payment error
    function handlePayPalError(error) {
        console.error('PayPal payment error:', error);
        error_message = error.message || m.eventRegister_paymentError?.() || 'Payment failed';
    }

    // Handle PayPal payment cancellation
    function handlePayPalCancel() {
        error_message = m.eventRegister_paymentCancelled?.() || 'Payment was cancelled';
    }
</script>

<svelte:head>
    <title>{m.eventRegister_title()} - {event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

{#snippet process_spaces(text)}
    {@html text.replace(/\n/g, '<br>').replace(/ /g, '&nbsp;')}
{/snippet}

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{m.eventRegister_title()}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/" class="hover:underline">{m.eventDetail_breadcrumbEvents()}</a>
                <span class="mx-2">/</span>
                <a href="/event/{event.id}" class="hover:underline">{event.name}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">{m.eventRegister_title()}</span>
            </p>
        </div>
    </div>

    {#if deadline && deadline < now}
        <!-- Registration Closed -->
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
            <Alert color="red">
                {m.eventRegister_closed()}
            </Alert>
            <p class="text-center mt-6">
                <Button color="alternative" href="/event/{event.id}" size="lg">{m.eventRegister_returnToEvent()}</Button>
            </p>
        </div>
    {:else}
        <!-- Registration Form with Stepper -->
        <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
            <!-- ProgressStepper -->
            <div class="mb-8">
                <ProgressStepper {steps} current={currentStep} clickable={false} showCheckmarkForCompleted={false} />
                <div class="flex justify-between mt-4 px-0">
                    {#each steps as step}
                        <div class="flex-1 text-center">
                            <p class="text-sm font-medium {currentStep === step.id ? 'text-primary-600' : 'text-gray-500'}">
                                {step.label}
                            </p>
                        </div>
                    {/each}
                </div>
            </div>

            <!-- Single persistent form to preserve Felte state across steps -->
            <form use:felteForm method="post" class="space-y-6">
                <!-- Step 1: Registration Form (always rendered, hidden when on step 2) -->
                <div class:hidden={currentStep !== 1}>
                    <div class="mb-8">
                        <p class="text-gray-700 mb-2">
                            {m.eventRegister_description()}
                        </p>
                        <ul class="list-disc ml-8 mb-4 text-gray-700 space-y-1">
                            <li>
                                <span class="font-medium">{m.eventRegister_eventName()}</span> {event.name}
                            </li>
                            <li>
                                <span class="font-medium">{m.eventRegister_eventDates()}</span> {formatDateRange(event.start_date, event.end_date)}
                            </li>
                            {#if !isFreeEvent}
                                <li>
                                    <span class="font-medium">{m.eventDetail_registrationFee()}</span> {formattedRegistrationFee()}
                                </li>
                            {/if}
                        </ul>
                        <p class="text-gray-700 mb-4">
                            {m.eventRegister_instructions()}
                        </p>
                        <Alert color="yellow" class="mb-0">
                            {m.eventRegister_warning()}
                        </Alert>
                    </div>

                    {#if isInvitationOnly}
                        <div class="mb-6 p-4 border border-blue-200 bg-blue-50 rounded-lg">
                            <Label for="invitation_code" class="block mb-2 font-medium text-blue-800">
                                {m.eventRegister_invitationCode()} <span class="text-red-500">*</span>
                            </Label>
                            <Input
                                type="text"
                                id="invitation_code"
                                name="invitation_code"
                                bind:value={$formData.invitation_code}
                                oninput={(e) => { $formData.invitation_code = e.target.value.toUpperCase(); }}
                                placeholder={m.eventRegister_invitationCodePlaceholder()}
                                class="bg-white uppercase"
                            />
                            {#if $errors.invitation_code}
                                <p class="text-sm text-red-600 mt-1">{$errors.invitation_code}</p>
                            {/if}
                            {#if invitation_code_error}
                                <p class="text-sm text-red-600 mt-1">{invitation_code_error}</p>
                            {/if}
                            <p class="text-sm text-blue-700 mt-2">{m.eventRegister_invitationCodeHelp()}</p>
                        </div>
                    {/if}

                    <RegistrationForm data={$formData} errors={$errors} config={form_config} institution_resolved={data.user?.institution_resolved} bind:instituteDisplayName={instituteDisplayName} />

                    {#if data.questions.length > 0}
                        <div class="pt-6 border-t border-gray-200">
                            <h2 class="text-xl font-bold text-gray-900 mb-6">{m.eventRegister_eventSpecificInfo()}</h2>
                            <div class="space-y-6">
                                {#each data.questions as question}
                                    <div>
                                        <Label for={question.id} class="block mb-2">{@render process_spaces(question.question.question)}</Label>
                                        {#if question.question.type === 'select'}
                                            <Select id={question.id} name={question.id} required bind:value={$formData[question.id]}>
                                                <option value="" disabled selected>{m.eventRegister_selectOption()}</option>
                                                {#each question.question.options as option, oidx}
                                                    <option value={option}>{option}</option>
                                                {/each}
                                            </Select>
                                        {:else if question.question.type === 'checkbox'}
                                            <div class="space-y-2">
                                                {#each question.question.options as option, oidx}
                                                    <Checkbox id={`${question.id}_${oidx}`} name={`${question.id}_${oidx}`} checked>{option}</Checkbox>
                                                {/each}
                                            </div>
                                        {:else if question.question.type === 'text'}
                                            <Input type="text" id={question.id} name={question.id} />
                                        {:else if question.question.type === 'textarea'}
                                            <Textarea id={question.id} name={question.id} rows={4} class="w-full" />
                                        {/if}
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {/if}

                    {#if error_message}
                        <Alert color="red" class="error">{error_message}</Alert>
                    {/if}

                    <div class="flex flex-col md:flex-row justify-center gap-4 pt-4">
                        <Button color="alternative" href="/event/{event.id}" size="lg">{m.eventRegister_returnToEvent()}</Button>
                        <Button color="primary" type="button" size="lg" onclick={handleNextStep}>{m.eventRegister_nextStep()}</Button>
                    </div>
                </div>

                <!-- Step 2: Confirmation (always rendered, hidden when on step 1) -->
                <div class:hidden={currentStep !== 2} class="space-y-6">
                    <div class="mb-8">
                        <h2 class="text-2xl font-bold text-gray-900 mb-4">{m.eventRegister_confirmTitle()}</h2>
                        <p class="text-gray-700 mb-6">{m.eventRegister_confirmDescription()}</p>
                    </div>

                    <!-- Confirmation Card -->
                    <div class="border border-gray-200 rounded-lg p-6">
                        <!-- Personal Information -->
                        <h3 class="text-lg font-semibold text-gray-900 mb-4">{m.eventRegister_personalInfo()}</h3>
                        <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {#if hasEnglish}
                                <div>
                                    <dt class="text-sm font-medium text-gray-500">{m.profile_firstName()}</dt>
                                    <dd class="mt-1 text-sm text-gray-900">{$formData.first_name}</dd>
                                </div>
                                {#if $formData.middle_initial}
                                    <div>
                                        <dt class="text-sm font-medium text-gray-500">{m.profile_middleInitial()}</dt>
                                        <dd class="mt-1 text-sm text-gray-900">{$formData.middle_initial}</dd>
                                    </div>
                                {/if}
                                <div>
                                    <dt class="text-sm font-medium text-gray-500">{m.profile_lastName()}</dt>
                                    <dd class="mt-1 text-sm text-gray-900">{$formData.last_name}</dd>
                                </div>
                            {/if}
                            {#if hasKorean && $formData.korean_name}
                                <div>
                                    <dt class="text-sm font-medium text-gray-500">{m.profile_koreanName()}</dt>
                                    <dd class="mt-1 text-sm text-gray-900">{$formData.korean_name}</dd>
                                </div>
                            {/if}
                            {#if instituteDisplayName}
                                <div>
                                    <dt class="text-sm font-medium text-gray-500">{m.form_institute()}</dt>
                                    <dd class="mt-1 text-sm text-gray-900">{instituteDisplayName}</dd>
                                </div>
                            {/if}
                            <div>
                                <dt class="text-sm font-medium text-gray-500">{m.profile_jobTitle()}</dt>
                                <dd class="mt-1 text-sm text-gray-900">{$formData.job_title}</dd>
                            </div>
                            {#if $formData.department}
                                <div>
                                    <dt class="text-sm font-medium text-gray-500">{m.profile_department()}</dt>
                                    <dd class="mt-1 text-sm text-gray-900">{$formData.department}</dd>
                                </div>
                            {/if}
                        </dl>

                        <!-- Additional Information -->
                        {#if $formData.disability || $formData.dietary}
                            <hr class="my-6 border-gray-200" />
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">{m.form_additionalInfo()}</h3>
                            <dl class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {#if $formData.disability}
                                    <div>
                                        <dt class="text-sm font-medium text-gray-500">{m.profile_disability()}</dt>
                                        <dd class="mt-1 text-sm text-gray-900">{$formData.disability}</dd>
                                    </div>
                                {/if}
                                {#if $formData.dietary}
                                    <div>
                                        <dt class="text-sm font-medium text-gray-500">{m.profile_dietary()}</dt>
                                        <dd class="mt-1 text-sm text-gray-900">{$formData.dietary}</dd>
                                    </div>
                                {/if}
                            </dl>
                        {/if}

                        <!-- Event-Specific Questions -->
                        {#if data.questions.length > 0}
                            <hr class="my-6 border-gray-200" />
                            <h3 class="text-lg font-semibold text-gray-900 mb-4">{m.eventRegister_eventSpecificInfo()}</h3>
                            <dl class="space-y-4">
                                {#each data.questions as question}
                                    <div>
                                        <dt class="text-sm font-medium text-gray-500 mb-2">{@render process_spaces(question.question.question)}</dt>
                                        <dd class="text-sm text-gray-900">
                                            {#if question.question.type === 'checkbox'}
                                                <div class="space-y-1">
                                                    {#each question.question.options as option, oidx}
                                                        {@const fieldName = `${question.id}_${oidx}`}
                                                        {@const isChecked = $formData[fieldName] === true || $formData[fieldName] === 'on'}
                                                        <div class="flex items-center gap-2">
                                                            <Checkbox checked={isChecked} disabled class="pointer-events-none" />
                                                            <span>{option}</span>
                                                        </div>
                                                    {/each}
                                                </div>
                                            {:else}
                                                {$formData[question.id] || '-'}
                                            {/if}
                                        </dd>
                                    </div>
                                {/each}
                            </dl>
                        {/if}
                    </div>

                    {#if error_message}
                        <Alert color="red" class="error">{error_message}</Alert>
                    {/if}

                    <div class="flex flex-col md:flex-row justify-center gap-4 pt-4">
                        <Button color="alternative" type="button" size="lg" onclick={goBackStep} disabled={isSubmittingFinal}>{m.eventRegister_goBack()}</Button>
                        <Button color="primary" type="button" size="lg" onclick={handleConfirmAndRegister} disabled={isSubmittingFinal}>
                            {isFreeEvent ? m.eventRegister_register() : m.eventRegister_confirmAndRegister()}
                        </Button>
                    </div>
                </div>

                <!-- Step 3: Payment (only for paid events) -->
                {#if !isFreeEvent}
                    <div class:hidden={currentStep !== 3} class="space-y-6">
                        <div class="mb-8">
                            <h2 class="text-2xl font-bold text-gray-900 mb-4">{m.eventRegister_paymentTitle()}</h2>
                            <p class="text-gray-700 mb-6">{m.eventRegister_paymentDescription()}</p>
                        </div>

                        <!-- Payment Summary Card -->
                        <div class="border border-gray-200 rounded-lg p-6">
                            <div class="flex items-center justify-center mb-6">
                                <CheckCircleOutline class="w-12 h-12 text-green-500 mr-3" />
                                <div>
                                    <h3 class="text-lg font-semibold text-gray-900">{m.eventRegister_registrationComplete()}</h3>
                                    <p class="text-sm text-gray-600">{m.eventRegister_proceedToPayment()}</p>
                                </div>
                            </div>

                            <hr class="my-6 border-gray-200" />

                            <div class="flex justify-between items-center mb-6">
                                <span class="text-lg font-semibold text-gray-900">{m.eventDetail_registrationFee()}</span>
                                <span class="text-2xl font-bold text-primary-600">{formattedRegistrationFee()}</span>
                            </div>

                            <hr class="my-6 border-gray-200" />

                            <!-- Payment Method Selection -->
                            <div class="mb-6">
                                <h3 class="text-lg font-semibold text-gray-900 mb-4">{m.eventRegister_selectPaymentMethod()}</h3>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <!-- Toss Payments Option -->
                                    <label class="relative flex items-center p-4 border-2 rounded-lg cursor-pointer transition-colors {paymentMethod === 'toss' ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}">
                                        <input
                                            type="radio"
                                            name="payment_method"
                                            value="toss"
                                            bind:group={paymentMethod}
                                            class="sr-only"
                                        />
                                        <div class="flex items-center gap-3 w-full">
                                            <div class="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-blue-100">
                                                <CreditCardSolid class="w-6 h-6 text-blue-600" />
                                            </div>
                                            <div>
                                                <p class="font-semibold text-gray-900">{m.eventRegister_payWithToss()}</p>
                                                <p class="text-sm text-gray-500">{m.eventRegister_tossDescription()}</p>
                                            </div>
                                        </div>
                                        {#if paymentMethod === 'toss'}
                                            <CheckCircleSolid class="absolute top-2 right-2 w-5 h-5 text-primary-500" />
                                        {/if}
                                    </label>

                                    <!-- PayPal Option -->
                                    <label class="relative flex items-center p-4 border-2 rounded-lg cursor-pointer transition-colors {paymentMethod === 'paypal' ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}">
                                        <input
                                            type="radio"
                                            name="payment_method"
                                            value="paypal"
                                            bind:group={paymentMethod}
                                            class="sr-only"
                                        />
                                        <div class="flex items-center gap-3 w-full">
                                            <div class="flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-lg bg-yellow-100">
                                                <svg class="w-6 h-6 text-blue-800" viewBox="0 0 24 24" fill="currentColor">
                                                    <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944 3.72a.77.77 0 0 1 .76-.654h6.033c2.027 0 3.621.53 4.585 1.533.928.965 1.248 2.326.954 4.044-.008.05-.018.1-.028.152-.355 2.048-1.527 3.547-3.182 4.319-1.01.472-2.16.694-3.446.694H8.71a.77.77 0 0 0-.76.654l-.873 5.53z"/>
                                                    <path d="M18.094 8.888c-.01.068-.02.137-.033.205-.866 4.443-3.83 5.98-7.615 5.98H8.67a.935.935 0 0 0-.923.793l-.781 4.943-.222 1.404a.485.485 0 0 0 .479.561h3.362a.773.773 0 0 0 .763-.656l.032-.163.605-3.839.039-.212a.773.773 0 0 1 .763-.657h.48c3.11 0 5.545-1.262 6.258-4.914.297-1.524.143-2.797-.643-3.691a3.062 3.062 0 0 0-.888-.754z"/>
                                                </svg>
                                            </div>
                                            <div>
                                                <p class="font-semibold text-gray-900">{m.eventRegister_payWithPayPal()}</p>
                                                <p class="text-sm text-gray-500">{m.eventRegister_paypalDescription()}</p>
                                            </div>
                                        </div>
                                        {#if paymentMethod === 'paypal'}
                                            <CheckCircleSolid class="absolute top-2 right-2 w-5 h-5 text-primary-500" />
                                        {/if}
                                    </label>
                                </div>
                            </div>
                        </div>

                        {#if error_message}
                            <Alert color="red" class="error">{error_message}</Alert>
                        {/if}

                        <!-- Payment Actions -->
                        <div class="flex flex-col gap-4 pt-4">
                            {#if paymentMethod === 'toss'}
                                <!-- Toss Payment Button -->
                                <div class="flex flex-col md:flex-row justify-center gap-4">
                                    <Button color="alternative" type="button" size="lg" href="/event/{event.id}" disabled={isSubmittingFinal}>
                                        {m.eventRegister_payLater()}
                                    </Button>
                                    <Button color="primary" type="button" size="lg" onclick={handlePayment} disabled={isSubmittingFinal}>
                                        {m.eventRegister_payNow()}
                                    </Button>
                                </div>
                            {:else}
                                <!-- PayPal Buttons -->
                                <div class="max-w-md mx-auto w-full">
                                    <div id="paypal-button-container" class="min-h-[150px]"></div>
                                </div>
                                <div class="flex justify-center">
                                    <Button color="alternative" type="button" size="lg" href="/event/{event.id}">
                                        {m.eventRegister_payLater()}
                                    </Button>
                                </div>
                            {/if}
                        </div>
                    </div>
                {/if}
            </form>
        </div>

        <!-- Checkout Modal (for paid events) -->
        <Modal bind:open={checkoutModalOpen} size="sm" dismissable={false} class="text-center">
            <div class="py-8">
                {#if checkoutStatus === 'processing'}
                    <Spinner size="12" class="mx-auto mb-4" />
                    <h3 class="text-xl font-semibold text-gray-900 mb-2">{m.eventRegister_processingPayment()}</h3>
                    <p class="text-gray-600">{m.eventRegister_pleaseWait()}</p>
                {:else if checkoutStatus === 'success'}
                    <CheckCircleOutline class="w-16 h-16 mx-auto mb-4 text-green-500" />
                    <h3 class="text-xl font-semibold text-gray-900 mb-2">{m.eventRegister_paymentSuccess()}</h3>
                    <p class="text-gray-600">{m.eventRegister_completingRegistration()}</p>
                {/if}
            </div>
        </Modal>
    {/if}
</div>