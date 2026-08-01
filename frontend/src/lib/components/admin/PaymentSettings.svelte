<script>
    import { Button, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const defaultSettings = {
        domestic_provider: 'toss',
        international_provider: 'paypal'
    };

    const initialSettings = data.admin.paymentSettings;
    let paymentSettings = $state({ ...defaultSettings, ...initialSettings });
    let payment_settings_success = $state(false);
    let payment_settings_error = $state('');

    // Radio groups rather than checkboxes: exactly one provider per category.
    const domesticOptions = [
        { value: 'toss', label: m.admin_paymentSettings_toss(), hint: m.admin_paymentSettings_tossHint() },
        { value: 'nicepay', label: m.admin_paymentSettings_nicepay(), hint: m.admin_paymentSettings_nicepayHint() },
        { value: 'none', label: m.admin_paymentSettings_disabled(), hint: m.admin_paymentSettings_disabledHint() }
    ];
    const internationalOptions = [
        { value: 'paypal', label: m.admin_paymentSettings_paypal(), hint: m.admin_paymentSettings_paypalHint() },
        { value: 'none', label: m.admin_paymentSettings_disabled(), hint: m.admin_paymentSettings_disabledHint() }
    ];

    const bothDisabled = $derived(
        paymentSettings.domestic_provider === 'none' && paymentSettings.international_provider === 'none'
    );

    const afterPaymentSettingsUpdate = () => {
        return async ({ result }) => {
            if (result.type === "success") {
                payment_settings_success = true;
                payment_settings_error = '';
                setTimeout(() => { payment_settings_success = false; }, 3000);
            } else {
                payment_settings_error = result.error?.message || 'An error occurred';
                payment_settings_success = false;
            }
        }
    };
</script>

{#snippet providerGroup(name, options, selected)}
    <div class="space-y-2">
        {#each options as option}
            <label class="flex items-start gap-3 p-3 border-2 rounded-lg cursor-pointer transition-colors
                {selected === option.value ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-gray-300'}">
                <input
                    type="radio"
                    {name}
                    value={option.value}
                    checked={selected === option.value}
                    onchange={() => {
                        if (name === 'domestic_provider') paymentSettings.domestic_provider = option.value;
                        else paymentSettings.international_provider = option.value;
                    }}
                    class="mt-1 h-4 w-4 text-primary-600 focus:ring-primary-500"
                />
                <span>
                    <span class="block text-sm font-medium text-gray-900">{option.label}</span>
                    <span class="block text-sm text-gray-500">{option.hint}</span>
                </span>
            </label>
        {/each}
    </div>
{/snippet}

<h2 class="text-2xl font-bold mb-2">{m.admin_paymentSettings_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_paymentSettings_description()}</p>

<form method="post" action="?/update_payment_settings" use:enhance={afterPaymentSettingsUpdate}>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
            <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
                {m.admin_paymentSettings_domestic()}
            </h3>
            {@render providerGroup('domestic_provider', domesticOptions, paymentSettings.domestic_provider)}
        </div>
        <div>
            <h3 class="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
                {m.admin_paymentSettings_international()}
            </h3>
            {@render providerGroup('international_provider', internationalOptions, paymentSettings.international_provider)}
        </div>
    </div>

    {#if bothDisabled}
        <Alert color="yellow" class="mt-4">{m.admin_paymentSettings_bothDisabledWarning()}</Alert>
    {/if}
    {#if payment_settings_success}
        <Alert color="green" class="mt-4">{m.admin_paymentSettings_success()}</Alert>
    {/if}
    {#if payment_settings_error}
        <Alert color="red" class="mt-4">{payment_settings_error}</Alert>
    {/if}

    <div class="flex justify-end mt-6">
        <Button color="primary" type="submit">{m.admin_paymentSettings_save()}</Button>
    </div>
</form>
