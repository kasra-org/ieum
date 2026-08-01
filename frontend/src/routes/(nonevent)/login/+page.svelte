<script>
    import { A, Card, Button, Heading, Indicator, Label, Input, Checkbox, Select, Alert, Modal } from '$lib/components/ui';
    import { onMount } from 'svelte';
    import * as m from '$lib/paraglide/messages.js';

    import 'academicons';

    let { data, form } = $props();

    let successModal = $state(false);

    // Show modal when verification email is sent successfully
    $effect(() => {
        if (form?.success) {
            successModal = true;
        }
    });

    function fUp(s){
        return s[0].toUpperCase() + s.slice(1);
    }

    const loginWithProvider = (provider) => {
        const next = data.next || '/';
        const callback_url = `/login${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`;

        let formdata = {
            provider: provider,
            process: 'login',
            callback_url: callback_url,
            csrfmiddlewaretoken: data.csrf_token,
        };
        // create a form element
        let form = document.createElement('form');
        form.setAttribute('method', 'POST');
        form.setAttribute('action', '/_allauth/browser/v1/auth/provider/redirect');
        form.style.display = 'hidden';
        // append the form to the body
        document.body.appendChild(form);
        // add the data to the form
        for (let key in formdata) {
            let input = document.createElement('input');
            input.setAttribute('type', 'hidden');
            input.setAttribute('name', key);
            input.setAttribute('value', formdata[key]);
            form.appendChild(input);
        }
        // submit the form
        form.submit();
    };

    const resendVerification = (email, verificationKey) => {
        // create a form element dynamically to submit the resend action
        let resendForm = document.createElement('form');
        resendForm.setAttribute('method', 'POST');
        resendForm.setAttribute('action', '?/resendVerification');
        resendForm.style.display = 'none';

        // add email input
        let emailInput = document.createElement('input');
        emailInput.setAttribute('type', 'hidden');
        emailInput.setAttribute('name', 'email');
        emailInput.setAttribute('value', email);
        resendForm.appendChild(emailInput);

        // add verification key input
        let keyInput = document.createElement('input');
        keyInput.setAttribute('type', 'hidden');
        keyInput.setAttribute('name', 'verificationKey');
        keyInput.setAttribute('value', verificationKey);
        resendForm.appendChild(keyInput);

        // append to body and submit
        document.body.appendChild(resendForm);
        resendForm.submit();
    };
</script>

<svelte:head>
    <title>{m.login_title()} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="container mx-auto max-w-4xl my-10 px-3 sm:px-7">
    <Card size="xl" padding="none" class="grid md:grid-cols-2">
        <div class="p-8 flex flex-col space-y-8 border-l border-b border-gray-300">
            <h3 class="text-xl font-medium text-gray-900 dark:text-white">{m.login_createAccountTitle()}</h3>
            <p class="text-sm !mt-2">{m.login_createAccountDescription()}</p>
            <Button class="w-full" href="/registration?next={encodeURIComponent(data.next || '/')}">{m.login_createAccountButton()}</Button>
        </div>
        <div class="border-l border-b border-gray-300 p-8">
            <h3 class="text-xl font-medium text-gray-900 dark:text-white">{m.login_title()}</h3>
            <p class="text-sm !mt-2">{m.login_description()}</p>
            <form method="POST" action="?/login" class="space-y-4 mt-6">
                <input type="hidden" name="next" value={data.next || '/'} />
                <div>
                    <label for="email" class="block text-sm font-medium text-gray-700">{m.form_email()}*</label>
                    <Input id="email" name="email" type="email" required class="mt-1" />
                </div>
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-700">{m.form_password()}*</label>
                    <Input id="password" name="password" type="password" required class="mt-1" />
                </div>
                {#if form?.error}
                <Alert color="red" class="mb-4" dismissable>
                    <p>{form.message}</p>
                    {#if form?.needsVerification}
                        <p class="text-sm mt-2">
                            {m.login_emailNotDelivered()} <button type="button" class="underline" onclick={() => resendVerification(form.email, form.verificationKey)}>{m.login_resendVerificationLink()}</button>
                        </p>
                    {/if}
                </Alert>
                {/if}
                {#if data.sociallogin_error}
                <Alert color="red" class="mb-4" dismissable>{m.login_socialNotLinked()}</Alert>
                {/if}
                <Button type="submit" color="primary" class="w-full">{m.login_submit()}</Button>

                <p class="text-sm text-gray-600 text-center mb-0">
                    <a href="/forgot-password?next={encodeURIComponent(data.next || '/')}" class="text-blue-500 hover:underline">{m.login_forgotPassword()}</a>
                </p>

                <div class="relative my-4">
                    <div class="absolute inset-0 flex items-center">
                        <div class="w-full border-t border-gray-300"></div>
                    </div>
                    <div class="relative flex justify-center text-sm">
                        <span class="bg-white px-2 text-gray-500">{m.login_orContinueWith()}</span>
                    </div>
                </div>

                <div class="flex gap-3">
                    <Button onclick={() => loginWithProvider('google')} color="light" class="flex-1 flex items-center justify-center gap-2">
                        <svg class="w-5 h-5" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                        </svg>
                        Google
                    </Button>
                    <Button onclick={() => loginWithProvider('orcid')} color="light" class="flex-1 flex items-center justify-center gap-2">
                        <i class="ai ai-orcid ai-lg" style="color: #A6CE39;"></i>
                        ORCID
                    </Button>
                </div>
            </form>
        </div>
    </Card>
</div>

<Modal bind:open={successModal} size="sm" autoclose outsideclose>
    <div class="text-center">
        <svg class="mx-auto mb-4 text-green-600 w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <h3 class="mb-5 text-lg font-normal text-gray-500">
            {form?.message || m.login_verificationEmailSent()}
        </h3>
        <Button color="green" onclick={() => successModal = false}>{m.common_ok()}</Button>
    </div>
</Modal>
