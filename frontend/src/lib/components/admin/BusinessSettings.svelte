<script>
    import { Button, Alert } from 'flowbite-svelte';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const defaultSettings = {
        business_name: '',
        business_registration_number: '',
        address: '',
        representative: '',
        phone: '',
        email: '',
        timezone: 'Asia/Seoul',
        business_name_en: '',
        address_en: '',
        representative_en: ''
    };

    const timezoneOptions = [
        'Asia/Seoul',
        'Asia/Tokyo',
        'Asia/Shanghai',
        'Asia/Singapore',
        'Asia/Kolkata',
        'Europe/London',
        'Europe/Paris',
        'Europe/Berlin',
        'America/New_York',
        'America/Chicago',
        'America/Denver',
        'America/Los_Angeles',
        'Pacific/Auckland',
        'Australia/Sydney',
        'UTC',
    ];

    // Extract initial value to avoid reactive warning (we intentionally want initial value only)
    const initialSettings = data.admin.businessSettings;
    let businessSettings = $state({ ...defaultSettings, ...initialSettings });
    let business_settings_success = $state(false);
    let business_settings_error = $state('');

    const afterBusinessSettingsUpdate = () => {
        return async ({ result }) => {
            if (result.type === "success") {
                business_settings_success = true;
                business_settings_error = '';
                setTimeout(() => { business_settings_success = false; }, 3000);
            } else {
                business_settings_error = result.error?.message || 'An error occurred';
                business_settings_success = false;
            }
        }
    };
</script>

<h2 class="text-2xl font-bold mb-2">{m.admin_businessSettings_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_businessSettings_description()}</p>

<form method="post" action="?/update_business_settings" use:enhance={afterBusinessSettingsUpdate}>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
            <label for="business_name" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_businessName()}</label>
            <input type="text" id="business_name" name="business_name" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.business_name} />
        </div>
        <div>
            <label for="business_name_en" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_businessNameEn()}</label>
            <input type="text" id="business_name_en" name="business_name_en" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.business_name_en} />
        </div>
        <div>
            <label for="representative" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_representative()}</label>
            <input type="text" id="representative" name="representative" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.representative} />
        </div>
        <div>
            <label for="representative_en" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_representativeEn()}</label>
            <input type="text" id="representative_en" name="representative_en" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.representative_en} />
        </div>
        <div>
            <label for="business_registration_number" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_businessRegistrationNumber()}</label>
            <input type="text" id="business_registration_number" name="business_registration_number" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.business_registration_number} />
        </div>
        <div>
            <label for="phone" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_phone()}</label>
            <input type="text" id="phone" name="phone" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.phone} />
        </div>
        <div>
            <label for="email" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_email()}</label>
            <input type="email" id="email" name="email" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.email} />
        </div>
        <div class="md:col-span-2">
            <label for="address" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_address()}</label>
            <input type="text" id="address" name="address" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.address} />
        </div>
        <div class="md:col-span-2">
            <label for="address_en" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_addressEn()}</label>
            <input type="text" id="address_en" name="address_en" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.address_en} />
        </div>
        <div>
            <label for="timezone" class="block mb-2 text-sm font-medium">{m.admin_businessSettings_timezone()}</label>
            <select id="timezone" name="timezone" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={businessSettings.timezone}>
                {#each timezoneOptions as tz}
                    <option value={tz}>{tz}</option>
                {/each}
            </select>
        </div>
    </div>
    {#if business_settings_success}
        <Alert color="green" class="mt-4">{m.admin_businessSettings_success()}</Alert>
    {/if}
    {#if business_settings_error}
        <Alert color="red" class="mt-4">{business_settings_error}</Alert>
    {/if}
    <div class="flex justify-end mt-6">
        <Button color="primary" type="submit">{m.admin_businessSettings_save()}</Button>
    </div>
</form>
