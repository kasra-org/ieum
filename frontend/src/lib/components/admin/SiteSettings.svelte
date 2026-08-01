<script>
    import { Button, Alert } from '$lib/components/ui';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { data } = $props();

    const defaultSettings = {
        site_name: 'IEUM',
        site_description: '',
        site_keywords: ''
    };

    const initialSettings = data.admin.siteSettings;
    let siteSettings = $state({ ...defaultSettings, ...initialSettings });
    let site_settings_success = $state(false);
    let site_settings_error = $state('');

    const afterSiteSettingsUpdate = () => {
        return async ({ result }) => {
            if (result.type === "success") {
                site_settings_success = true;
                site_settings_error = '';
                setTimeout(() => { site_settings_success = false; }, 3000);
            } else {
                site_settings_error = result.error?.message || 'An error occurred';
                site_settings_success = false;
            }
        }
    };
</script>

<h2 class="text-2xl font-bold mb-2">{m.admin_siteSettings_title()}</h2>
<p class="text-gray-600 mb-6">{m.admin_siteSettings_description()}</p>

<form method="post" action="?/update_site_settings" use:enhance={afterSiteSettingsUpdate}>
    <div class="grid grid-cols-1 gap-4">
        <div>
            <label for="site_name" class="block mb-2 text-sm font-medium">{m.admin_siteSettings_siteName()}</label>
            <input type="text" id="site_name" name="site_name" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={siteSettings.site_name} />
            <p class="mt-1 text-sm text-gray-500">{m.admin_siteSettings_siteNameHelp()}</p>
        </div>
        <div>
            <label for="site_description" class="block mb-2 text-sm font-medium">{m.admin_siteSettings_siteDescription()}</label>
            <textarea id="site_description" name="site_description" rows="3" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={siteSettings.site_description}></textarea>
            <p class="mt-1 text-sm text-gray-500">{m.admin_siteSettings_siteDescriptionHelp()}</p>
        </div>
        <div>
            <label for="site_keywords" class="block mb-2 text-sm font-medium">{m.admin_siteSettings_siteKeywords()}</label>
            <input type="text" id="site_keywords" name="site_keywords" class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5" bind:value={siteSettings.site_keywords} />
            <p class="mt-1 text-sm text-gray-500">{m.admin_siteSettings_siteKeywordsHelp()}</p>
        </div>
    </div>
    {#if site_settings_success}
        <Alert color="green" class="mt-4">{m.admin_siteSettings_success()}</Alert>
    {/if}
    {#if site_settings_error}
        <Alert color="red" class="mt-4">{site_settings_error}</Alert>
    {/if}
    <div class="flex justify-end mt-6">
        <Button color="primary" type="submit">{m.admin_siteSettings_save()}</Button>
    </div>
</form>
