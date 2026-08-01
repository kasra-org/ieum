<script>
    let { data: page_data } = $props();

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';

    import { goto } from '$app/navigation';
    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import { Alert, Input, Textarea, Select, Button, Label, InputAddon, ButtonGroup, Heading, Card, Checkbox } from '$lib/components/ui';
    import { ChevronLeft, ChevronRight, CircleUser } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { onlyLatinChars } from '$lib/utils.js';

    // Step management
    let currentStep = $state(1);
    let agreedToPrivacy = $state(false);
    let agreedToTerms = $state(false);

    let currentLang = $derived(languageTag());

    // For English, show English content + Korean content below
    let privacyContent = $derived(() => {
        if (currentLang === 'ko') {
            return page_data.privacyPolicy?.content_ko || '';
        } else {
            let result = page_data.privacyPolicy?.content_en || '';
            if (page_data.privacyPolicy?.content_ko) {
                result += '<hr class="my-8 border-gray-300"><h2>한국어 버전 (Korean Version)</h2>' + page_data.privacyPolicy.content_ko;
            }
            return result;
        }
    });

    let termsContent = $derived(() => {
        if (currentLang === 'ko') {
            return page_data.termsOfService?.content_ko || '';
        } else {
            let result = page_data.termsOfService?.content_en || '';
            if (page_data.termsOfService?.content_ko) {
                result += '<hr class="my-8 border-gray-300"><h2>한국어 버전 (Korean Version)</h2>' + page_data.termsOfService.content_ko;
            }
            return result;
        }
    });

    let canProceed = $derived(agreedToPrivacy && agreedToTerms);

    function goToStep2() {
        if (canProceed) {
            currentStep = 2;
            window.scrollTo(0, 0);
        }
    }

    function goToStep1() {
        currentStep = 1;
        window.scrollTo(0, 0);
    }

    const schema = yup.object({
        email: yup.string().email().required(m.validation_emailRequired()),
        password: yup.string().required(m.validation_passwordRequired()).min(8, m.validation_passwordMinLength()),
        confirm_password: yup.string().required(m.validation_confirmPasswordRequired()).oneOf([yup.ref('password'), null], m.validation_passwordsMismatch()),
        first_name: yup.string().required(m.validation_firstNameRequired()).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        last_name: yup.string().required(m.validation_lastNameRequired()).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        middle_initial: yup.string().max(1).test('latin-only', m.eventRegister_validationNoKorean(), onlyLatinChars),
        korean_name: yup.string(),
        nationality: yup.string().required(m.validation_nationalityRequired()),
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
    });

    let form_config = $derived({
        next: page_data.next,
        show_english_name: true,
        show_korean_name: true,
        allow_korean_institute: true,
    });

    const { form: felteForm, data, errors, isSubmitting } = createForm({
        initialValues: {
            email: '',
            password: '',
            confirm_password: '',
            first_name: '',
            last_name: '',
            middle_initial: '',
            korean_name: '',
            nationality: '1',
            job_title: '',
            department: '',
            institute: '',
            disability: '',
            dietary: '',
        },
        onSubmit: async (data) => {
            delete data.confirm_password;
            data.username = data.email;
            const response = await fetch('?/register',
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
            }
        },
        extend: validator({ schema }),
        onError: (errors) => {
            if (errors.redirect) {
                goto(`/verify-email?next=${page_data.next}`);
            } else {
                window.scrollTo(0, 0);
            }
            return errors;
        }
    });
</script>

<svelte:head>
    <title>{m.registration_title()} | {page_data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<!-- Page Header Card -->
<div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
    <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
    <div class="relative z-10">
        <h1 class="text-3xl font-bold text-white">{m.registration_title()}</h1>
        <p class="text-slate-200 mt-2">{m.registration_description()}</p>
    </div>
</div>

<!-- Step Indicator -->
<div class="flex justify-center mb-6">
    <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
            <div class={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${currentStep === 1 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'}`}>1</div>
            <span class={`text-sm ${currentStep === 1 ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>{m.registration_stepTerms()}</span>
        </div>
        <div class="w-12 h-0.5 bg-gray-300"></div>
        <div class="flex items-center gap-2">
            <div class={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${currentStep === 2 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'}`}>2</div>
            <span class={`text-sm ${currentStep === 2 ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>{m.registration_stepInfo()}</span>
        </div>
    </div>
</div>

{#if currentStep === 1}
    <!-- Step 1: Terms Agreement -->
    <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-6 sm:p-8">
        <h2 class="text-xl font-semibold mb-4">{m.registration_termsAgreementTitle()}</h2>
        <p class="text-gray-600 mb-6">{m.registration_termsAgreementDescription()}</p>

        <!-- Privacy Policy -->
        <div class="mb-6">
            <h3 class="text-lg font-medium mb-2">{m.privacyPolicy_pageTitle()}</h3>
            {#if currentLang === 'en' && page_data.privacyPolicy?.content_ko}
                <Alert color="blue" class="mb-3">
                    {m.privacyPolicy_koreanBindingNotice()}
                </Alert>
            {/if}
            <div class="border border-gray-200 rounded-lg p-4 max-h-64 overflow-y-auto bg-gray-50 prose prose-sm max-w-none leading-normal prose-p:my-2 prose-ul:my-2 prose-li:my-0 prose-h2:mt-6 prose-h2:mb-2">
                {#if privacyContent()}
                    {@html privacyContent()}
                {:else}
                    <p class="text-gray-500 italic">{m.privacyPolicy_noContent()}</p>
                {/if}
            </div>
            <div class="mt-3">
                <Checkbox bind:checked={agreedToPrivacy}>{m.registration_agreePrivacyPolicy()}</Checkbox>
            </div>
        </div>

        <!-- Terms of Service -->
        <div class="mb-6">
            <h3 class="text-lg font-medium mb-2">{m.termsOfService_pageTitle()}</h3>
            {#if currentLang === 'en' && page_data.termsOfService?.content_ko}
                <Alert color="blue" class="mb-3">
                    {m.termsOfService_koreanBindingNotice()}
                </Alert>
            {/if}
            <div class="border border-gray-200 rounded-lg p-4 max-h-64 overflow-y-auto bg-gray-50 prose prose-sm max-w-none leading-normal prose-p:my-2 prose-ul:my-2 prose-li:my-0 prose-h2:mt-6 prose-h2:mb-2">
                {#if termsContent()}
                    {@html termsContent()}
                {:else}
                    <p class="text-gray-500 italic">{m.termsOfService_noContent()}</p>
                {/if}
            </div>
            <div class="mt-3">
                <Checkbox bind:checked={agreedToTerms}>{m.registration_agreeTermsOfService()}</Checkbox>
            </div>
        </div>

        <div class="flex justify-end mt-8">
            <Button color="primary" size="lg" disabled={!canProceed} onclick={goToStep2}>
                {m.registration_next()}
                <ChevronRight class="w-4 h-4 ml-2" />
            </Button>
        </div>
    </div>
{:else}
    <!-- Step 2: Registration Form -->
    <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
        <form use:felteForm method="post">
            <RegistrationForm data={$data} errors={$errors} config={form_config} />
            <div class="flex flex-col md:flex-row justify-between gap-4 mt-8">
                <Button color="alternative" size="lg" onclick={goToStep1}>
                    <ChevronLeft class="w-4 h-4 mr-2" />
                    {m.registration_back()}
                </Button>
                <Button type="submit" size="lg" color="primary" disabled={$isSubmitting}>
                    {m.registration_submit()}
                </Button>
            </div>
        </form>
    </div>
{/if}
