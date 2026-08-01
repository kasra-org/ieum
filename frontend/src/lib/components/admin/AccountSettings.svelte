<script>
    import { Button, Alert, Helper } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const defaultSettings = {
        account_deletion_period: 3 * 365,
        account_warning_period: 7,
        attendee_retention_years: 5,
        payment_retention_years: 5,
        minimum_retention_years: 5
    };

    // Extract initial value to avoid reactive warning
    const initialSettings = data.admin.accountSettings;
    let accountSettings = $state({ ...defaultSettings, ...initialSettings });
    let account_settings_success = $state(false);
    let account_settings_error = $state('');

    // Calculate years and days for display
    let deletionYears = $derived(Math.floor(accountSettings.account_deletion_period / 365));
    let deletionDays = $derived(accountSettings.account_deletion_period % 365);

    const afterAccountSettingsUpdate = () => {
        return async ({ result }) => {
            if (result.type === "success") {
                account_settings_success = true;
                account_settings_error = '';
                setTimeout(() => { account_settings_success = false; }, 3000);
            } else {
                account_settings_error = result.error?.message || 'An error occurred';
                account_settings_success = false;
            }
        }
    };

    function updateDeletionPeriod() {
        accountSettings.account_deletion_period = (deletionYears * 365) + deletionDays;
    }
</script>

<h2 class="text-2xl font-bold mb-2">{m.admin_accountSettings_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_accountSettings_description()}</p>

<form method="post" action="?/update_account_settings" use:enhance={afterAccountSettingsUpdate}>
    <!-- Account Inactivity Settings -->
    <div class="mb-8">
        <h3 class="text-lg font-semibold mb-4">{m.admin_accountSettings_inactivityTitle()}</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <label for="deletion_years" class="block mb-2 text-sm font-medium">{m.admin_accountSettings_deletionPeriod()}</label>
                <div class="flex gap-2 items-center">
                    <input
                        type="number"
                        id="deletion_years"
                        min="1"
                        max="10"
                        class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-20 p-2.5"
                        bind:value={deletionYears}
                        onchange={updateDeletionPeriod}
                    />
                    <span class="text-sm text-gray-600">{m.admin_accountSettings_years()}</span>
                    <input
                        type="number"
                        id="deletion_days"
                        min="0"
                        max="364"
                        class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-20 p-2.5"
                        bind:value={deletionDays}
                        onchange={updateDeletionPeriod}
                    />
                    <span class="text-sm text-gray-600">{m.admin_accountSettings_days()}</span>
                </div>
                <Helper class="mt-1">{m.admin_accountSettings_deletionPeriodHelp()}</Helper>
                <input type="hidden" name="account_deletion_period" value={accountSettings.account_deletion_period} />
            </div>
            <div>
                <label for="account_warning_period" class="block mb-2 text-sm font-medium">{m.admin_accountSettings_warningPeriod()}</label>
                <div class="flex gap-2 items-center">
                    <input
                        type="number"
                        id="account_warning_period"
                        name="account_warning_period"
                        min="1"
                        max="30"
                        class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-20 p-2.5"
                        bind:value={accountSettings.account_warning_period}
                    />
                    <span class="text-sm text-gray-600">{m.admin_accountSettings_days()}</span>
                </div>
                <Helper class="mt-1">{m.admin_accountSettings_warningPeriodHelp()}</Helper>
            </div>
        </div>
    </div>

    <!-- Data Retention Settings -->
    <div class="mb-8">
        <h3 class="text-lg font-semibold mb-4">{m.admin_accountSettings_retentionTitle()}</h3>
        <Alert color="blue" class="mb-4">
            {m.admin_accountSettings_retentionNote({ years: accountSettings.minimum_retention_years })}
        </Alert>
        <div>
            <label for="payment_retention_years" class="block mb-2 text-sm font-medium">{m.admin_accountSettings_paymentRetention()}</label>
            <div class="flex gap-2 items-center">
                <input
                    type="number"
                    id="payment_retention_years"
                    name="payment_retention_years"
                    min={accountSettings.minimum_retention_years}
                    max="20"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-20 p-2.5"
                    bind:value={accountSettings.payment_retention_years}
                />
                <span class="text-sm text-gray-600">{m.admin_accountSettings_years()}</span>
            </div>
            <Helper class="mt-1">{m.admin_accountSettings_paymentRetentionHelp()}</Helper>
        </div>
    </div>

    {#if account_settings_success}
        <Alert color="green" class="mt-4">{m.admin_accountSettings_success()}</Alert>
    {/if}
    {#if account_settings_error}
        <Alert color="red" class="mt-4">{account_settings_error}</Alert>
    {/if}
    <div class="flex justify-end mt-6">
        <Button color="primary" type="submit">{m.admin_accountSettings_save()}</Button>
    </div>
</form>
