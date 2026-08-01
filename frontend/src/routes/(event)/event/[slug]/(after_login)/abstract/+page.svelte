<script>
    import { browser } from '$app/environment';
    import { A, List, Li, Card, Button, Label, Input, Dropzone, Checkbox, Alert, Radio } from '$lib/components/ui';
    import { Download } from '@lucide/svelte';
    import { createForm } from 'felte';
    import { validator } from '@felte/validator-yup';
    import * as yup from 'yup';
    import * as m from '$lib/paraglide/messages.js';
    import 'academicons';

    let { data } = $props();

    let event = data.event;
    let abstract = data.abstract;
    let me = data.user;

    // DOMPurify for XSS protection
    let DOMPurify = $state(null);
    $effect(() => {
        if (browser && !DOMPurify) {
            import('dompurify').then(module => {
                DOMPurify = module.default;
            });
        }
    });

    function sanitizeHtml(html) {
        if (!html) return '';
        if (browser && DOMPurify) {
            return DOMPurify.sanitize(html);
        }
        // DOMPurify is browser-only; never hand back unsanitized markup.
        return '';
    }

    const schema = yup.object({
        title: yup.string().required(m.abstractSubmission_titleRequired()),
    });

    let error_message = $state('');
    const { form: felteForm, data: formData, errors, isSubmitting } = createForm({
        initialValues: {
            type: 'poster',
            wants_short_talk: false,
        },
        onSubmit: async (data) => {
            const fd = new FormData();
            fd.append('title', data.title);
            fd.append('type', data.type);
            fd.append('wants_short_talk', data.type === 'poster' ? data.wants_short_talk : false);
            fd.append('file_name', abstract_file.file_name);
            fd.append('file_content', abstract_file.file_content);

            const response = await fetch('?/abstract',
                {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                    },
                    body: fd
                }
            );
            if (!response.ok || response.status !== 200) {
                const rtn = await response.json();
                throw rtn.error;
            }
            location.reload();
        },
        extend: validator({ schema }),
        onError: (errors) => {
            error_message = errors.message;
            return errors;
        }
    });

    let abstract_file = $state({
        file_name: '',
        file_content: '',
    });

    const set_file = (file) => {
        let ext = file.name.split('.').pop();
        if (ext !== 'docx' && ext !== 'odt') {
            error_message = m.abstractSubmission_invalidFileFormat();
            return;
        }
        if (file.size > 1048576) {
            error_message = m.abstractSubmission_fileSizeExceeds();
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            error_message = '';
            abstract_file.file_name = file.name;
            abstract_file.file_content = event.target.result;
            abstract_file = abstract_file;
        };
        reader.readAsDataURL(file);
    };

    const unset_file = () => {
        abstract_file.file_name = '';
        abstract_file.file_content = null;
        abstract_file = abstract_file;
    };

    const dropHandle = (event) => {
        unset_file();
        event.preventDefault();
        if (event.dataTransfer.items) {
            [...event.dataTransfer.items].forEach((item) => {
                if (item.kind === 'file') {
                    const file = item.getAsFile();
                    set_file(file);
                    return;
                }
            });
        } else {
            [...event.dataTransfer.files].forEach((file) => {
                set_file(file);
                return;
            });
        }
    };

    const handleChange = (event) => {
        const files = event.target.files;
        if (files.length > 0) {
            set_file(files[0]);
        }
    };
</script>

<svelte:head>
    <title>{m.abstractSubmission_title()} - {event.name} | {data.site_settings?.site_name ?? 'IEUM'}</title>
</svelte:head>

<div class="container mx-auto my-10 px-3 sm:px-7">
    <!-- Page Header Card -->
    <div class="relative rounded-lg shadow-sm py-16 px-8 mb-8 overflow-hidden" style="background-image: url('/bg-events.webp'); background-size: cover; background-position: center;">
        <div class="absolute inset-0 bg-slate-900 opacity-60"></div>
        <div class="relative z-10">
            <h1 class="text-3xl font-bold text-white">{m.abstractSubmission_title()}</h1>
            <p class="text-slate-200 mt-2">
                <a href="/event/{event.id}" class="hover:underline">{event.name}</a>
                <span class="mx-2">/</span>
                <span class="text-white font-medium">{m.abstractSubmission_title()}</span>
            </p>
        </div>
    </div>

    <!-- Main Content -->
    <div>
        {#if data.abstract_submitted}
            <!-- Abstract Preview -->
            <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
                <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-6">
                    <p class="text-sm">{m.abstractSubmission_thankYou()}</p>
                </div>
                <div class="text-center mb-6">
                    <h2 class="text-xl font-bold text-gray-900">{abstract.title}</h2>
                    <p class="text-sm text-gray-600 mt-2">
                        {m.abstractSubmission_presentedBy()} {me.first_name} {#if me.middle_initial}{me.middle_initial} {/if}{me.last_name}
                    </p>
                </div>
                <hr class="mb-6 border-gray-200" />
                <div class="prose prose-gray max-w-none">
                    {@html sanitizeHtml(abstract?.body)}
                </div>
                <hr class="my-6 border-gray-200" />
                <div class="flex flex-col sm:flex-row gap-4">
                    <Button href={abstract.link} color="primary" size="lg" class="flex-1">
                        <Download class="w-4 h-4 me-2" />
                        {m.abstractSubmission_downloadSubmission()}
                    </Button>
                    <Button href="/event/{event.id}" color="alternative" size="lg" class="flex-1">
                        {m.abstractSubmission_goBack()}
                    </Button>
                </div>
            </div>
        {:else}
            <!-- Submission Form -->
            <div class="bg-white border border-gray-200 rounded-lg shadow-sm p-8">
                <p class="text-gray-600 mb-6">{m.abstractSubmission_description()}</p>

                <form use:felteForm method="post" class="space-y-6">
                    <div>
                        <Label for="title" class="block mb-2">
                            {m.abstractSubmission_abstractTitle()} <span class="text-red-500">*</span>
                        </Label>
                        <Input id="title" name="title" type="text" bind:value={$formData.title} />
                        {#if $errors.title}
                            <Alert color="red" class="mt-3">
                                <p class="text-sm">{$errors.title}</p>
                            </Alert>
                        {/if}
                    </div>

                    <div>
                        <Label for="abstract" class="block mb-3">
                            {m.abstractSubmission_abstractFile()} <span class="text-red-500">*</span>
                        </Label>
                        <p class="mb-3 text-sm text-gray-600">{m.abstractSubmission_templateInstructions()}</p>
                        <List list="disc" class="mb-5 ms-4">
                            <Li class="mb-2">
                                <A href="/abstract/abstract_template.docx" class="font-medium text-sm text-blue-600 hover:underline">
                                    {m.abstractSubmission_downloadDocx()}
                                </A>
                            </Li>
                            <Li>
                                <A href="/abstract/abstract_template.odt" class="font-medium text-sm text-blue-600 hover:underline">
                                    {m.abstractSubmission_downloadOdt()}
                                </A>
                            </Li>
                        </List>
                        <Dropzone
                            id="dropzone"
                            accept=".docx,.odt"
                            onDrop={dropHandle}
                            onChange={handleChange}
                        >
                            <svg aria-hidden="true" class="mb-3 w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            {#if abstract_file.file_name !== ''}
                                <p class="text-sm font-medium text-gray-900">{abstract_file.file_name}</p>
                            {:else}
                                <p class="mb-2 text-sm text-gray-500">
                                    <span class="font-semibold">{m.abstractSubmission_clickToUpload()}</span> {m.abstractSubmission_dragAndDrop()}
                                </p>
                                <p class="text-xs text-gray-500">{m.abstractSubmission_fileFormats()}</p>
                            {/if}
                        </Dropzone>
                        {#if $errors.file}
                            <Alert color="red" class="mt-3">
                                <p class="text-sm">{$errors.file}</p>
                            </Alert>
                        {/if}
                    </div>

                    {#if error_message}
                        <Alert color="red">{error_message}</Alert>
                    {/if}

                    <div>
                        <Label class="block mb-3">{m.abstractSubmission_presentationType()} <span class="text-red-500">*</span></Label>
                        <div class="flex flex-col gap-3">
                            <Radio name="type" value="speaker" bind:group={$formData.type}>
                                {m.abstractType_speaker()}
                            </Radio>
                            <Radio name="type" value="poster" bind:group={$formData.type}>
                                {m.abstractType_poster()}
                            </Radio>
                        </div>
                    </div>

                    {#if $formData.type === 'poster'}
                        <div class="ml-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                            <Checkbox id="wants_short_talk" name="wants_short_talk" bind:checked={$formData.wants_short_talk}>
                                {m.abstractSubmission_wantsShortTalk()}
                            </Checkbox>
                            <p class="text-sm text-gray-500 mt-2 ml-6">{m.abstractSubmission_wantsShortTalkDescription()}</p>
                        </div>
                    {/if}

                    <div class="flex flex-col sm:flex-row gap-4 pt-4">
                        <Button type="submit" color="primary" size="lg" disabled={$isSubmitting} class="flex-1">
                            {m.abstractSubmission_submit()}
                        </Button>
                        <Button href="/event/{event.id}" color="alternative" size="lg" class="flex-1">
                            {m.abstractSubmission_goBack()}
                        </Button>
                    </div>
                </form>
            </div>
        {/if}
    </div>
</div>
