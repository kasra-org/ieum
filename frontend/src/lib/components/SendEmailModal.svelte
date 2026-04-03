<script>
    import { Modal, Button, Label, Textarea, Alert } from 'flowbite-svelte';
    import { CloseCircleSolid } from 'flowbite-svelte-icons';
    import { enhance } from '$app/forms';
    import * as m from '$lib/paraglide/messages.js';
    import { getDisplayName } from '$lib/utils.js';

    let { open = $bindable(false), recipients = '', action = '?/send_emails', eventadmins = [] } = $props();

    let message_error = $state('');
    let ccEmails = $state([]);
    let ccInput = $state('');
    let showSuggestions = $state(false);
    let inputEl = $state(null);
    let selectedBadge = $state(-1);
    let highlightedSuggestion = $state(-1);
    let successModal = $state(false);
    let sentCount = $state(0);

    let suggestions = $derived(
        ccInput.trim()
            ? eventadmins
                .filter(a => !ccEmails.includes(a.email))
                .filter(a =>
                    a.email.toLowerCase().includes(ccInput.toLowerCase()) ||
                    (a.name && a.name.toLowerCase().includes(ccInput.toLowerCase())) ||
                    (a.korean_name && a.korean_name.toLowerCase().includes(ccInput.toLowerCase()))
                )
            : []
    );

    function addEmail(email) {
        const trimmed = email.replace(/[,;\s]+/g, '').trim();
        if (trimmed && !ccEmails.includes(trimmed)) {
            ccEmails = [...ccEmails, trimmed];
        }
        ccInput = '';
        selectedBadge = -1;
        highlightedSuggestion = -1;
        showSuggestions = false;
    }

    function removeAtIndex(idx) {
        ccEmails = ccEmails.filter((_, i) => i !== idx);
        if (ccEmails.length === 0 || idx > ccEmails.length - 1) {
            selectedBadge = -1;
            inputEl?.focus();
        } else {
            selectedBadge = idx;
        }
    }

    function commitInput() {
        if (highlightedSuggestion >= 0 && highlightedSuggestion < suggestions.length) {
            addEmail(suggestions[highlightedSuggestion].email);
        } else if (suggestions.length > 0) {
            addEmail(suggestions[0].email);
        } else if (ccInput.trim()) {
            addEmail(ccInput);
        }
    }

    function handleKeydown(e) {
        if (selectedBadge >= 0) {
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                selectedBadge = Math.max(0, selectedBadge - 1);
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                if (selectedBadge >= ccEmails.length - 1) {
                    selectedBadge = -1;
                    inputEl?.focus();
                } else {
                    selectedBadge++;
                }
            } else if (e.key === 'Backspace' || e.key === 'Delete') {
                e.preventDefault();
                removeAtIndex(selectedBadge);
            } else if (e.key === 'Escape') {
                selectedBadge = -1;
                inputEl?.focus();
            }
            return;
        }

        if (e.key === 'ArrowDown' && showSuggestions && suggestions.length > 0) {
            e.preventDefault();
            highlightedSuggestion = Math.min(highlightedSuggestion + 1, suggestions.length - 1);
        } else if (e.key === 'ArrowUp' && showSuggestions && suggestions.length > 0) {
            e.preventDefault();
            highlightedSuggestion = Math.max(highlightedSuggestion - 1, -1);
        } else if (e.key === 'Escape' && showSuggestions) {
            e.preventDefault();
            showSuggestions = false;
            highlightedSuggestion = -1;
        } else if (e.key === 'Enter') {
            e.preventDefault();
            commitInput();
        } else if (e.key === 'Tab') {
            if (ccInput.trim() || (highlightedSuggestion >= 0 && suggestions.length > 0)) {
                e.preventDefault();
                commitInput();
            }
            // else: let default tab behavior move focus to next field
        } else if (e.key === 'ArrowLeft' && inputEl?.selectionStart === 0 && ccEmails.length > 0) {
            e.preventDefault();
            selectedBadge = ccEmails.length - 1;
        } else if (e.key === 'Backspace' && ccInput === '' && ccEmails.length > 0) {
            e.preventDefault();
            selectedBadge = ccEmails.length - 1;
        }
    }

    function handleInput(e) {
        const val = e.target.value;
        selectedBadge = -1;
        highlightedSuggestion = -1;
        if (/[,;]/.test(val)) {
            const parts = val.split(/[,;]+/).filter(s => s.trim());
            for (const part of parts) {
                addEmail(part);
            }
            ccInput = '';
            return;
        }
        if (val.endsWith(' ') && val.trim().includes('@')) {
            addEmail(val);
            return;
        }
        ccInput = val;
    }

    function handlePaste(e) {
        e.preventDefault();
        const text = e.clipboardData.getData('text');
        const emails = text.split(/[;,\s]+/).filter(s => s.trim());
        for (const email of emails) {
            addEmail(email);
        }
    }

    function handleBlur() {
        const val = ccInput.trim();
        if (val) addEmail(val);
        selectedBadge = -1;
        setTimeout(() => { showSuggestions = false; }, 200);
    }

    $effect(() => {
        if (!open) {
            ccEmails = [];
            ccInput = '';
            selectedBadge = -1;
            message_error = '';
        }
    });

    const afterSubmit = () => {
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                sentCount = recipients.split(';').filter(e => e.trim()).length;
                await update({ reset: false });
                open = false;
                message_error = '';
                successModal = true;
            } else {
                message_error = m.attendees_sendEmailError();
            }
        };
    };
</script>

<Modal id="send_email_modal" size="lg" title={m.attendees_sendEmails()} bind:open outsideclose>
    <form method="post" {action} use:enhance={afterSubmit}>
        <input type="hidden" name="to" value={recipients} />
        <input type="hidden" name="cc" value={ccEmails.join("; ")} />
        <div class="mb-6">
            <Label for="cc_input" class="block mb-2">{m.attendees_cc()}</Label>
            <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
            <div
                class="cc-container flex flex-wrap items-center gap-1 p-2.5 border border-gray-300 rounded-lg bg-gray-50 dark:bg-gray-700 dark:border-gray-600 min-h-[42px] cursor-text"
                onclick={() => { selectedBadge = -1; inputEl?.focus(); }}
                tabindex="-1"
            >
                {#each ccEmails as email, i}
                    <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
                    <span
                        role="option"
                        aria-selected={selectedBadge === i}
                        tabindex="-1"
                        class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-medium cursor-pointer select-none
                            {selectedBadge === i ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'}"
                        onclick={(e) => { e.stopPropagation(); selectedBadge = i; }}
                        onkeydown={(e) => { if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); removeAtIndex(i); } }}
                    >
                        {email}
                        <button type="button" class="ml-0.5 hover:text-red-500 cursor-pointer" onclick={(e) => { e.stopPropagation(); removeAtIndex(i); }}>
                            <CloseCircleSolid class="w-3 h-3" />
                        </button>
                    </span>
                {/each}
                <input
                    bind:this={inputEl}
                    id="cc_input"
                    type="text"
                    class="!flex-1 !min-w-[120px] !bg-transparent !p-0 !text-sm !border-none !shadow-none !outline-none !ring-0 focus:!ring-0 focus:!border-none focus:!outline-none"
                    style="box-shadow: none !important; caret-color: {selectedBadge >= 0 ? 'transparent' : 'auto'};"
                    placeholder={ccEmails.length === 0 ? m.attendees_ccPlaceholder() : ''}
                    value={ccInput}
                    onkeydown={handleKeydown}
                    oninput={handleInput}
                    onpaste={handlePaste}
                    onfocus={() => { showSuggestions = true; selectedBadge = -1; }}
                    onblur={handleBlur}
                />
            </div>
            {#if showSuggestions && suggestions.length > 0}
                <div class="absolute z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto dark:bg-gray-700 dark:border-gray-600">
                    {#each suggestions as admin, si}
                        <button
                            type="button"
                            class="w-full px-3 py-2 text-left text-sm cursor-pointer
                                {highlightedSuggestion === si ? 'bg-blue-100 dark:bg-blue-600' : 'hover:bg-gray-100 dark:hover:bg-gray-600'}"
                            onmousedown={() => addEmail(admin.email)}
                            onmouseenter={() => { highlightedSuggestion = si; }}
                        >
                            <span class="font-medium">{getDisplayName(admin)}</span>
                            <span class="text-gray-500 ml-2">{admin.email}</span>
                        </button>
                    {/each}
                </div>
            {/if}
        </div>
        <div class="mb-6">
            <Label for="subject" class="block mb-2">{m.attendees_subject()}</Label>
            <input id="subject" name="subject" type="text" class="block w-full border border-gray-300 rounded-lg bg-gray-50 p-2.5 text-sm focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600" />
        </div>
        <div class="mb-6">
            <Label for="body" class="block mb-2">{m.attendees_message()}</Label>
            <Textarea id="body" name="body" rows="10" class="w-full" />
        </div>
        {#if message_error}
            <Alert type="error" color="red" class="mb-6">{message_error}</Alert>
        {/if}
        <div class="flex justify-center gap-2">
            <Button color="primary" type="submit">{m.attendees_sendEmails()}</Button>
        </div>
    </form>
</Modal>

<Modal size="sm" bind:open={successModal} outsideclose>
    <div class="text-center p-4">
        <p class="text-lg mb-4">{m.attendees_emailSentSuccess({ count: sentCount })}</p>
        <Button color="primary" onclick={() => successModal = false}>{m.attendees_ok()}</Button>
    </div>
</Modal>

<style>
    .cc-container:focus-within {
        outline: none !important;
        --tw-ring-shadow: 0 0 0 1px var(--color-primary-500) !important;
        box-shadow: 0 0 0 1px var(--color-primary-500), 0 0 8px 2px rgba(33, 150, 243, 0.4) !important;
    }
</style>
