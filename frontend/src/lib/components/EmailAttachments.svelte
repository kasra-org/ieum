<script>
    // Files sent alongside an email body, as opposed to the images the body
    // inlines - those are part of the body and the editor handles them. Upload
    // goes through the same endpoint, so both end up under media/editor.
    import { Button, Label, Alert, Spinner } from '$lib/components/ui';
    import { CircleX, Paperclip } from '@lucide/svelte';
    import { deserialize } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';

    let { value = $bindable([]), name = '', label = '' } = $props();

    let fileInput = $state(null);
    let uploading = $state(false);
    let uploadError = $state('');

    // Mirrors MAX_EDITOR_FILE_SIZE on the server; refusing here saves a round
    // trip and names the file the server would only describe generically.
    const MAX_BYTES = 5 * 1024 * 1024;

    function formatSize(bytes) {
        if (!bytes) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    async function upload(file) {
        const formData = new FormData();
        formData.append('file_name', file.name);
        formData.append('file_content', await fileToBase64(file));
        formData.append('file_type', 'attachment');

        const response = await fetch('?/upload_editor_file', { method: 'POST', body: formData });
        const result = deserialize(await response.text());
        if (result.type === 'success' && result.data?.url) {
            return { url: result.data.url, filename: result.data.filename || file.name, size: file.size };
        }
        throw new Error(result.data?.message || m.emailAttachments_uploadFailed());
    }

    async function handleFiles(event) {
        const files = Array.from(event.target.files || []);
        if (files.length === 0) return;

        uploading = true;
        uploadError = '';
        try {
            for (const file of files) {
                if (file.size > MAX_BYTES) {
                    uploadError = m.emailAttachments_tooLarge({ name: file.name });
                    continue;
                }
                value = [...value, await upload(file)];
            }
        } catch (e) {
            uploadError = e.message;
        } finally {
            uploading = false;
            // Clear the picker so re-choosing the same file still fires change.
            if (fileInput) fileInput.value = '';
        }
    }

    function remove(index) {
        value = value.filter((_, i) => i !== index);
    }
</script>

{#if label}
    <Label class="block mb-2">{label}</Label>
{/if}

<!-- The server reads this one field; the list above is only its editor. -->
<input type="hidden" {name} value={JSON.stringify(value)} />

<div class="flex flex-wrap items-center gap-2">
    {#each value as file, i}
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200">
            <Paperclip class="w-3 h-3 shrink-0" />
            <a href={file.url} target="_blank" rel="noopener" class="hover:underline">{file.filename}</a>
            {#if file.size}<span class="text-gray-500">{formatSize(file.size)}</span>{/if}
            <button type="button" class="ml-0.5 hover:text-red-500 cursor-pointer"
                aria-label={m.emailAttachments_remove()} onclick={() => remove(i)}>
                <CircleX class="w-3 h-3" />
            </button>
        </span>
    {/each}

    <Button type="button" color="light" size="xs" disabled={uploading} onclick={() => fileInput?.click()}>
        {#if uploading}
            <Spinner class="w-3 h-3 me-1.5" />
        {:else}
            <Paperclip class="w-3 h-3 me-1.5" />
        {/if}
        {m.emailAttachments_add()}
    </Button>
    <input type="file" multiple class="hidden" bind:this={fileInput} onchange={handleFiles} />
</div>

{#if uploadError}
    <Alert color="red" class="mt-2 text-sm">{uploadError}</Alert>
{/if}
