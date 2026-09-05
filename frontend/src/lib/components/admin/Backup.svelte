<script>
    import { Button, Alert } from '$lib/components/ui';
    import { Download, Upload, DatabaseBackup, TriangleAlert } from '@lucide/svelte';
    import { page } from '$app/stores';
    import { invalidateAll } from '$app/navigation';
    import * as m from '$lib/paraglide/messages.js';

    // Everything here is under /[admin_page_name]; build the proxy URLs from the
    // segment this admin page was reached on.
    const base = $derived(`/${$page.params.admin_page_name}`);

    let file = $state(null);
    let confirmed = $state(false);
    let restoring = $state(false);
    let result = $state(null); // { ok: boolean, message: string }

    const REQUIRED = 'RESTORE';
    let typed = $state('');

    function onFile(e) {
        file = e.target.files?.[0] ?? null;
        result = null;
    }

    async function restore() {
        if (!file || !confirmed || typed !== REQUIRED) return;
        restoring = true;
        result = null;
        try {
            const form = new FormData();
            form.append('file', file);
            const res = await fetch(`${base}/restore`, { method: 'POST', body: form });
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                result = { ok: true, message: data.message || m.backup_restoreSuccess() };
                // The restore replaced the session table; reload so the app
                // reflects the restored state (and a fresh login if needed).
                await invalidateAll();
            } else {
                result = { ok: false, message: data.message || m.backup_restoreFailed() };
            }
        } catch (err) {
            result = { ok: false, message: m.backup_restoreFailed() };
        } finally {
            restoring = false;
        }
    }
</script>

<div class="flex items-center gap-2 mb-2">
    <DatabaseBackup class="w-6 h-6 text-gray-700" />
    <h2 class="text-2xl font-bold text-gray-900">{m.admin_backup_title()}</h2>
</div>
<p class="text-gray-600 mb-6">{m.backup_description()}</p>

<!-- Backup -->
<div class="rounded-lg border border-gray-200 p-5 mb-8">
    <h3 class="text-lg font-semibold text-gray-900 mb-1">{m.backup_downloadTitle()}</h3>
    <p class="text-sm text-gray-600 mb-4">{m.backup_downloadHelp()}</p>
    <Button href="{base}/backup" color="primary">
        <Download class="w-4 h-4 me-2" />{m.backup_downloadButton()}
    </Button>
</div>

<!-- Restore -->
<div class="rounded-lg border border-red-200 bg-red-50 p-5">
    <div class="flex items-center gap-2 mb-1">
        <TriangleAlert class="w-5 h-5 text-red-600" />
        <h3 class="text-lg font-semibold text-red-900">{m.backup_restoreTitle()}</h3>
    </div>
    <p class="text-sm text-red-800 mb-4">{m.backup_restoreWarning()}</p>

    <input type="file" accept=".gz,.tgz,application/gzip"
        onchange={onFile}
        class="block w-full text-sm text-gray-700 file:mr-3 file:rounded-md file:border-0 file:bg-gray-200 file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-gray-300 mb-4 cursor-pointer" />

    <label class="flex items-start gap-2 mb-3 cursor-pointer">
        <input type="checkbox" bind:checked={confirmed}
            class="mt-1 h-4 w-4 rounded border-gray-300 text-red-600 focus:ring-red-500" />
        <span class="text-sm text-red-800">{m.backup_restoreConfirm()}</span>
    </label>

    <label class="block text-sm text-red-800 mb-4">
        {m.backup_restoreType({ word: REQUIRED })}
        <input type="text" bind:value={typed} autocomplete="off"
            class="mt-1 block w-40 rounded-md border-gray-300 text-sm shadow-sm focus:border-red-500 focus:ring-red-500" />
    </label>

    <Button color="red" onclick={restore}
        disabled={!file || !confirmed || typed !== REQUIRED || restoring}>
        <Upload class="w-4 h-4 me-2" />
        {restoring ? m.backup_restoring() : m.backup_restoreButton()}
    </Button>

    {#if result}
        <Alert color={result.ok ? 'green' : 'red'} class="mt-4">{result.message}</Alert>
    {/if}
</div>
