<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Button, Dropdown, DropdownItem } from '$lib/components/ui';
    import { Modal, Heading, Textarea, Select, Label, Card, Input } from '$lib/components/ui';
    import { Alert, Spinner } from '$lib/components/ui';
    import { ChevronDown } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import { Award, CircleCheck, Tag, UserMinus, UserPen } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { generateNametagPDF, generateBatchNametagPDF, generateCertificatePDF, loadKoreanFonts } from '$lib/pdfUtils.js';
    import { getCategoryLabel, downloadTsv } from '$lib/utils.js';
    import { PagedList } from '$lib/pagedList.svelte.js';
    import { languageTag } from '$lib/paraglide/runtime.js';

    import OnSiteRegistrationForm from '$lib/components/OnSiteRegistrationForm.svelte';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ConfirmModal from '$lib/components/ConfirmModal.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';
    import QRCode from 'qrcode';

    let { data } = $props();

    // Preload fonts on component mount
    $effect(() => {
        loadKoreanFonts();
    });

    // The walk-ins are paged and searched on the server, in id order.
    const list = new PagedList(() => `/api/event/${data.event.id}/onsite`);
    list.track(() => data);

    // Every walk-in, whatever the search box holds - the export, "email to
    // all" and "certificates to all" have always ignored the search.
    const fetchEveryAttendee = async () => {
        const response = await fetch(`${list.url}/export`, {
            headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error(`${response.status}`);
        return response.json();
    };

    // The headcount above the table is every walk-in, not the search's
    // matches: the server sends it with each page, so it is current after
    // every load - a search or a page turn as much as an add or a removal.
    // Null until a page has arrived.
    let totalAttendees = $derived(list.loaded ? (list.counts.all ?? 0) : null);

    // Shown when fetching rows for a whole-list or selection action fails,
    // which otherwise left the button doing nothing visible.
    let fetch_error = $state(false);
    // Shown when an action finds nobody to act on - everyone it would reach
    // has left since the tab loaded - rather than doing nothing visible.
    let nobody_left = $state(false);

    // A selection spans pages; put the fetched rows back in the order they
    // were ticked, as the batch name tags always came out.
    const fetchSelected = async () => {
        const asked = [...selectedAttendees];
        const rows = await list.fetchByIds(asked);
        const byId = new Map(rows.map(r => [r.id, r]));
        // A walk-in removed since being ticked leaves the selection too; with
        // nobody left the "selected" buttons disable. Only those asked about:
        // a row ticked meanwhile stays ticked.
        selectedAttendees = selectedAttendees.filter(id => !asked.includes(id) || byId.has(id));
        return asked.filter(id => byId.has(id)).map(id => byId.get(id));
    };

    // Each whole-list action fetches its rows first; these keep a second
    // click from fetching (and downloading, or opening) it all again.
    let csv_exporting = $state(false);
    let email_preparing = $state(false);
    let bulk_cert_preparing = $state(false);

    const exportAttendeesAsCSV = async () => {
        if (csv_exporting) return;
        csv_exporting = true;
        let rows;
        fetch_error = false;
        nobody_left = false;
        try {
            rows = await fetchEveryAttendee();
        } catch (e) {
            console.error('Failed to fetch on-site attendees for export:', e);
            fetch_error = true;
            return;
        } finally {
            csv_exporting = false;
        }
        downloadTsv([
            [   "ID",
                "Name",
                "Email",
                "Institute",
                "Job Title"
            ],
            ...rows.map(row => [
                row.id,
                row.name,
                row.email,
                row.institute,
                row.job_title
            ])
        ], 'onsite_attendees');
    };

    // Ticked rows, by id: the selection survives paging and searching.
    let selectedAttendees = $state([]);

    // The server's search fields, with the same names.
    const searchFields = [
        { value: 'name', name: m.search_name() },
        { value: 'email', name: m.search_email() },
        { value: 'institute', name: m.search_institute() },
        { value: 'category', name: m.search_category() },
        { value: 'job_title', name: m.search_jobTitle() },
        { value: 'id', name: m.search_id() },
    ];

    let pageAllSelected = $derived(
        list.items.length > 0 && list.items.every(a => selectedAttendees.includes(a.id))
    );

    let attendee_modal = $state(false);
    let remove_attendee_modal = $state(false);

    // The row the edit or remove modal is about. A plain copy: the
    // registration form writes into it as the admin types, and the table row
    // should change only once the save lands and the page reloads.
    let selected_attendee = $state.raw(null);
    const showAttenteeModal = (row) => {
        selected_attendee = $state.snapshot(row);
        attendee_modal = true;
    };

    const showRemoveAttenteeModal = (row) => {
        selected_attendee = $state.snapshot(row);
        remove_attendee_modal = true;
    };

    let message_update = $state({});
    const afterSuccessfulSubmit = () => {
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                await update({ reset: false });
                message_update = { type: 'success', message: m.onsiteAttendees_successMessage() };
            } else {
                message_update = { type: 'error', message: m.onsiteAttendees_errorMessage() };
            }
        };
    };

    const afterSuccessfulDeregistration = () => {
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                selectedAttendees = selectedAttendees.filter(id => id !== selected_attendee?.id);
                await update({ reset: false });
            }
            remove_attendee_modal = false;
        };
    };

    // A raw fetch that reloads nothing: the row on screen is flipped in place
    // once the server agrees. The bulk actions refetch their rows anyway.
    const toggleConfirm = async (row) => {
        const next = !row.is_confirmed;
        const formData = new FormData();
        formData.append('id', row.id);
        formData.append('is_confirmed', next.toString());
        const response = await fetch('?/confirm_onsite_attendee', {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            // Patch whichever copy of the row is on screen now, then reload
            // so a load already in flight cannot put the old value back.
            const shown = list.items.find(a => a.id === row.id);
            if (shown) shown.is_confirmed = next;
            list.load();
        }
    };

    // Per walk-in: their own category decides whether payment is outstanding.

    let nametag_modal = $state(false);
    let selected_nametag = $state('');
    let selected_nametag_row = $state.raw(null);
    let selected_role = $state('Participant');

    // Nametag paper settings from event (use $derived for reactive defaults, $state for local edits)
    let _nametag_defaults = $derived.by(() => ({
        w: data.event.nametag_paper_width ?? 90,
        h: data.event.nametag_paper_height ?? 100,
        o: data.event.nametag_orientation ?? 'portrait'
    }));
    let nametag_paper_width = $state(90);
    let nametag_paper_height = $state(100);
    let nametag_orientation = $state('portrait');
    $effect.pre(() => {
        nametag_paper_width = _nametag_defaults.w;
        nametag_paper_height = _nametag_defaults.h;
        nametag_orientation = _nametag_defaults.o;
    });

    const saveNametagSettings = async () => {
        try {
            const formData = new FormData();
            formData.append('nametag_paper_width', nametag_paper_width);
            formData.append('nametag_paper_height', nametag_paper_height);
            formData.append('nametag_orientation', nametag_orientation);
            const response = await fetch('?/save_nametag_settings', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                await invalidateAll();
            }
        } catch (e) {
            console.error('Failed to save nametag settings:', e);
        }
    };

    const regenerateNametag = async () => {
        if (selected_nametag_row !== null) {
            await generateNametag(selected_nametag_row, selected_role);
        }
    };

    const onPaperDimensionChange = async () => {
        await saveNametagSettings();
        await regenerateNametag();
    };

    const onOrientationChange = async (e) => {
        nametag_orientation = e.target.value;
        await saveNametagSettings();
        await regenerateNametag();
    };

    const generateNametag = async (p, role) => {
        selected_nametag = await generateNametagPDF({
            name: p.name,
            institute: p.institute,
            role,
            id: p.onsiteattendee_nametag_id,
            paperWidth: nametag_paper_width,
            paperHeight: nametag_paper_height,
            orientation: nametag_orientation
        });
    };

    const showNametagModal = async (row) => {
        selected_nametag_row = $state.snapshot(row);
        selected_role = 'Participant';
        await generateNametag(selected_nametag_row, selected_role);
        nametag_modal = true;
    };

    const onRoleChange = async (e) => {
        await generateNametag(selected_nametag_row, e.target.value);
    };

    // Batch nametag printing
    let batch_nametag_modal = $state(false);
    let batch_nametag_pdf = $state('');
    let batch_nametag_role = $state('Participant');
    let batch_nametag_generating = $state(false);
    // The selected rows, fetched once as the modal opens; changing the role
    // or the paper only redraws them.
    let batch_nametag_rows = [];

    const generateBatchNametags = async () => {
        if (batch_nametag_rows.length === 0) return;
        batch_nametag_generating = true;
        const attendees = batch_nametag_rows.map(a => (
            { name: a.name, institute: a.institute, id: a.onsiteattendee_nametag_id }
        ));
        batch_nametag_pdf = await generateBatchNametagPDF({
            attendees,
            role: batch_nametag_role,
            paperWidth: nametag_paper_width,
            paperHeight: nametag_paper_height,
            orientation: nametag_orientation
        });
        batch_nametag_generating = false;
    };

    const showBatchNametagModal = async () => {
        if (selectedAttendees.length === 0) return;
        batch_nametag_role = 'Participant';
        // Never show the previous batch while this one is drawn.
        batch_nametag_pdf = '';
        batch_nametag_generating = true;
        fetch_error = false;
        nobody_left = false;
        try {
            batch_nametag_rows = await fetchSelected();
        } catch (e) {
            console.error('Failed to fetch the selected on-site attendees:', e);
            fetch_error = true;
            return;
        } finally {
            batch_nametag_generating = false;
        }
        if (batch_nametag_rows.length === 0) {
            nobody_left = true;
            return;
        }
        batch_nametag_modal = true;
        await generateBatchNametags();
    };

    const onBatchRoleChange = async (e) => {
        batch_nametag_role = e.target.value;
        await generateBatchNametags();
    };

    let cert_modal = $state(false);
    let selected_cert = $state('');
    let cert_email = $state('');
    let cert_sending = $state(false);
    let cert_message = $state({});
    let selected_cert_row = $state.raw(null);

    // Bulk certificate sending
    let bulk_cert_sending = $state(false);
    let bulk_cert_message = $state({});
    let bulk_cert_confirm_modal = $state(false);
    // The rows to certify, fetched as the confirmation opens, so its
    // eligible/skipped figures and the send itself see the same rows. Only
    // confirmed walk-ins with an address are sent one.
    let cert_targets = $state.raw([]);
    const certEligible = (p) => p.email && p.is_confirmed;
    let certEligibleCount = $derived(cert_targets.filter(certEligible).length);
    let certSkippedCount = $derived(cert_targets.length - certEligibleCount);

    const openCertificatesConfirm = async (loadTargets) => {
        if (bulk_cert_preparing || bulk_cert_sending) return;
        bulk_cert_preparing = true;
        fetch_error = false;
        nobody_left = false;
        try {
            cert_targets = await loadTargets();
        } catch (e) {
            // Nothing was sent: the rows to send to could not be fetched.
            fetch_error = true;
            return;
        } finally {
            bulk_cert_preparing = false;
        }
        if (cert_targets.length === 0) {
            nobody_left = true;
            return;
        }
        bulk_cert_confirm_modal = true;
    };

    const showSendCertificatesConfirm = () => {
        if (selectedAttendees.length === 0) return;
        openCertificatesConfirm(fetchSelected);
    };

    const showSendCertificatesToAllConfirm = () => {
        openCertificatesConfirm(fetchEveryAttendee);
    };

    const sendCertificatesToSelected = async () => {
        bulk_cert_confirm_modal = false;
        const targets = cert_targets;
        if (targets.length === 0 || bulk_cert_sending) return;
        bulk_cert_sending = true;
        bulk_cert_message = {};
        try {
            for (const p of targets) {
                if (!certEligible(p)) continue;
                const pdfDataUri = await generateCertificatePDF({
                    attendee: { name: p.name, institute: p.institute },
                    event: data.event,
                    messages: {
                        certIssueDate: m.attendees_certIssueDate,
                        certTitle: m.attendees_certTitle,
                        certName: m.attendees_certName,
                        certInstitute: m.attendees_certInstitute,
                        certHasAttended: m.attendees_certHasAttended,
                        certOn: m.attendees_certOn,
                        certHeldAt: m.attendees_certHeldAt,
                        certAsParticipant: m.attendees_certAsParticipant,
                        certFooter: m.attendees_certFooter
                    },
                    outputFormat: 'datauristring'
                });
                const base64Pdf = pdfDataUri.split(',')[1];
                const formData = new FormData();
                formData.append('email', p.email);
                formData.append('pdf_base64', base64Pdf);
                formData.append('attendee_id', p.id);
                formData.append('attendee_type', 'onsite');
                await fetch('?/send_certificate', {
                    method: 'POST',
                    body: formData
                });
            }
            bulk_cert_message = { type: 'success', message: m.attendees_sendCertificatesComplete() };
        } catch (error) {
            bulk_cert_message = { type: 'error', message: m.attendees_sendCertificateError() };
        } finally {
            bulk_cert_sending = false;
        }
    };

    let qr_modal = $state(false);
    let qr_code_url = $state('');
    let registrationUrl = $derived(`${typeof window !== 'undefined' ? window.location.origin : ''}/event/${data.event.id}/onsite?code=${encodeURIComponent(data.event.onsite_code || '')}`);
    const showQRCodeModal = async () => {
        qr_code_url = await QRCode.toDataURL(registrationUrl, {
            width: 400,
            margin: 2
        });
        qr_modal = true;
    };

    const printQRCode = () => {
        const printWindow = window.open('', '', 'width=600,height=600');
        printWindow.document.write(`
            <html>
                <head>
                    <title>On-site Registration QR Code</title>
                    <style>
                        * {
                            margin: 0;
                            padding: 0;
                            box-sizing: border-box;
                        }
                        html, body {
                            height: 100%;
                            width: 100%;
                        }
                        body {
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            justify-content: center;
                            font-family: Arial, sans-serif;
                        }
                        img {
                            max-width: 400px;
                            margin-bottom: 20px;
                        }
                        p {
                            text-align: center;
                            font-size: 12px;
                            color: #666;
                            word-break: break-all;
                            max-width: 400px;
                        }
                    </style>
                </head>
                <body>
                    <img src="${qr_code_url}" alt="QR Code" />
                    <p>${registrationUrl}</p>
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.focus();
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
        }, 250);
    };

    const showCertificateModal = async (row) => {
        const p = $state.snapshot(row);
        selected_cert_row = p;
        cert_email = p.email || '';
        cert_message = {};
        selected_cert = await generateCertificatePDF({
            attendee: { name: p.name, institute: p.institute },
            event: data.event,
            messages: {
                certIssueDate: m.attendees_certIssueDate,
                certTitle: m.attendees_certTitle,
                certName: m.attendees_certName,
                certInstitute: m.attendees_certInstitute,
                certHasAttended: m.attendees_certHasAttended,
                certOn: m.attendees_certOn,
                certHeldAt: m.attendees_certHeldAt,
                certAsParticipant: m.attendees_certAsParticipant,
                certFooter: m.attendees_certFooter
            }
        });
        cert_modal = true;
    };

    const sendCertificate = async () => {
        if (!cert_email || cert_sending) return;
        cert_sending = true;
        cert_message = {};
        try {
            const p = selected_cert_row;
            const pdfDataUri = await generateCertificatePDF({
                attendee: { name: p.name, institute: p.institute },
                event: data.event,
                messages: {
                    certIssueDate: m.attendees_certIssueDate,
                    certTitle: m.attendees_certTitle,
                    certName: m.attendees_certName,
                    certInstitute: m.attendees_certInstitute,
                    certHasAttended: m.attendees_certHasAttended,
                    certOn: m.attendees_certOn,
                    certHeldAt: m.attendees_certHeldAt,
                    certAsParticipant: m.attendees_certAsParticipant,
                    certFooter: m.attendees_certFooter
                },
                outputFormat: 'datauristring'
            });
            // Extract base64 from data URI (format: data:application/pdf;filename=generated.pdf;base64,...)
            const base64Pdf = pdfDataUri.split(',')[1];
            const formData = new FormData();
            formData.append('email', cert_email);
            formData.append('pdf_base64', base64Pdf);
            formData.append('attendee_id', p.id);
            formData.append('attendee_type', 'onsite');
            const response = await fetch('?/send_certificate', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                cert_message = { type: 'success', message: m.attendees_sendCertificateSuccess() };
            } else {
                cert_message = { type: 'error', message: m.attendees_sendCertificateError() };
            }
        } catch (error) {
            cert_message = { type: 'error', message: m.attendees_sendCertificateError() };
        } finally {
            cert_sending = false;
        }
    };

    // Recipients are fetched as the modal is asked for: every walk-in, or
    // the ticked ones wherever they are paged.
    let send_email_modal = $state(false);
    let emailRecipients = $state('');
    const openEmailModal = async (loadRows) => {
        if (email_preparing) return;
        email_preparing = true;
        fetch_error = false;
        nobody_left = false;
        try {
            const rows = await loadRows();
            if (rows.length === 0) {
                nobody_left = true;
                return;
            }
            emailRecipients = rows.map(a => a.email).filter(Boolean).join("; ");
        } catch (e) {
            console.error('Failed to fetch on-site attendees for email:', e);
            fetch_error = true;
            return;
        } finally {
            email_preparing = false;
        }
        send_email_modal = true;
    };
    const showSendEmailModal = () => {
        if (selectedAttendees.length === 0) return;
        openEmailModal(fetchSelected);
    };
    const showSendEmailToAllModal = () => openEmailModal(fetchEveryAttendee);
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.onsiteAttendees_title()}</Heading>
<p class="font-light mb-6">{m.onsiteAttendees_description()}</p>

<div class="flex justify-end items-center gap-2 flex-wrap mb-4">
    <Button color="primary" size="sm">{m.attendees_emailActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailToAllModal} disabled={email_preparing || totalAttendees === 0}>{m.attendees_sendEmailToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailModal} disabled={selectedAttendees.length === 0 || email_preparing}>{m.attendees_sendEmailToSelected()}</DropdownItem>
    </Dropdown>

    <Button color="primary" size="sm" disabled={bulk_cert_sending}>{bulk_cert_sending ? m.attendees_sendingCertificates() : m.attendees_certificateActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesToAllConfirm} disabled={bulk_cert_sending || bulk_cert_preparing || totalAttendees === 0}>{m.attendees_sendCertificatesToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesConfirm} disabled={selectedAttendees.length === 0 || bulk_cert_sending || bulk_cert_preparing}>{m.attendees_sendCertificatesToSelected()}</DropdownItem>
    </Dropdown>

    <Button color="primary" size="sm" onclick={showBatchNametagModal} disabled={selectedAttendees.length === 0 || batch_nametag_generating}>
        {batch_nametag_generating ? '...' : m.attendees_printNametagsForSelected()}
    </Button>
    <Button color="primary" size="sm" onclick={showQRCodeModal}>{m.onsiteRegistration_qrCode()}</Button>
    <Button color="primary" size="sm" onclick={exportAttendeesAsCSV} disabled={csv_exporting}>{csv_exporting ? '...' : m.onsiteAttendees_exportCSV()}</Button>
</div>
{#if fetch_error || (list.error && list.items.length > 0)}
    <Alert type="error" color="red" class="mt-3">{m.common_error()}</Alert>
{/if}
{#if nobody_left}
    <Alert color="blue" class="mt-3">{m.onsiteAttendees_noRecords()}</Alert>
{/if}
{#if bulk_cert_message.type === 'success'}
    <Alert type="success" color="green" class="mt-3">{bulk_cert_message.message}</Alert>
{:else if bulk_cert_message.type === 'error'}
    <Alert type="error" color="red" class="mt-3">{bulk_cert_message.message}</Alert>
{/if}
{#if totalAttendees !== null}<p class="mt-5 mb-3 text-sm text-right">{totalAttendees} {m.onsiteAttendees_peopleRegistered()}</p>{/if}
<TableSearch placeholder={m.onsiteAttendees_searchPlaceholder()} hoverable={true} bind:inputValue={list.search} bind:field={list.field} fields={searchFields}>
    <TableHead>
        <!-- Ticks or clears the rows on this page; ticks elsewhere stay. -->
        <TableHeadCell class="w-1">
            <Checkbox
                checked={pageAllSelected}
                intermediate={selectedAttendees.length > 0 && !pageAllSelected}
                onclick={(e) => {
                    const pageIds = list.items.map(a => a.id);
                    selectedAttendees = e.target.checked
                        ? [...new Set([...selectedAttendees, ...pageIds])]
                        : selectedAttendees.filter(id => !pageIds.includes(id));
                }}
            />
        </TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_id()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.onsiteAttendees_confirmed()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_name()}</TableHeadCell>
        <TableHeadCell>{m.attendees_tier()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_email()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_institute()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_jobTitle()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.onsiteAttendees_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each list.items as row (row.id)}
            <TableBodyRow>
                <TableBodyCell><Checkbox checked={selectedAttendees.includes(row.id)} onclick={(e) => {
                    if (e.target.checked) {
                        selectedAttendees = [...selectedAttendees, row.id];
                    } else {
                        selectedAttendees = selectedAttendees.filter(a => a !== row.id);
                    }
                }} /></TableBodyCell>
                <TableBodyCell>{row.onsiteattendee_nametag_id}</TableBodyCell>
                <TableBodyCell>
                    <button onclick={() => toggleConfirm(row)} class="cursor-pointer">
                        <CircleCheck class="w-5 h-5 {row.is_confirmed ? 'text-green-500' : 'text-gray-300'}" />
                    </button>
                </TableBodyCell>
                <TableBodyCell>{row.name}</TableBodyCell>
                <TableBodyCell>{getCategoryLabel(row, languageTag())}</TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>{row.institute}</TableBodyCell>
                <TableBodyCell>{row.job_title}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.onsiteAttendees_nametag()}>
                            <Button color="none" size="none" onclick={() => showNametagModal(row)} disabled={!row.is_registration_complete}>
                                <Tag class="w-5 h-5 {row.is_registration_complete ? '' : 'opacity-30'}" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_certificate()}>
                            <Button color="none" size="none" onclick={() => showCertificateModal(row)} disabled={!row.is_confirmed}>
                                <Award class="w-5 h-5 {row.is_confirmed ? '' : 'opacity-30'}" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_detailsTitle()}>
                            <Button color="none" size="none" onclick={() => showAttenteeModal(row)}>
                                <UserPen class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_remove()}>
                            <Button color="none" size="none" onclick={() => showRemoveAttenteeModal(row)}>
                                <UserMinus class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if list.items.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="9" class="text-center">
                    {#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.onsiteAttendees_noRecords()}{/if}
                </TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={(p) => list.goto(p)} />

<Modal id="attendee_modal" size="xl" title={m.onsiteAttendees_detailsTitle()} bind:open={attendee_modal} outsideclose>
    <form method="post" action="?/update_onsite_attendee" use:enhance={afterSuccessfulSubmit}>
        <input type="hidden" name="id" value={selected_attendee?.id ?? ''} />
        <OnSiteRegistrationForm data={selected_attendee} />
        {#if message_update.type === 'success'}
            <Alert type="success" color="green">{message_update.message}</Alert>
        {:else if message_update.type === 'error'}
            <Alert type="error" color="red">{message_update.message}</Alert>
        {/if}
        <div class="flex justify-center mt-6">
            <Button color="primary" type="submit">{m.onsiteAttendees_updateAttendee()}</Button>
        </div>
    </form>
</Modal>

<Modal id="remove_attendee_modal" size="sm" title={m.onsiteAttendees_removeTitle()} bind:open={remove_attendee_modal} outsideclose>
    <form method="post" action="?/remove_onsite_attendee" use:enhance={afterSuccessfulDeregistration}>
        <input type="hidden" name="id" value={selected_attendee?.id ?? ''} />
        <p class="font-light mb-6">{m.onsiteAttendees_removeConfirm()}</p>
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.onsiteAttendees_remove()}</Button>
            <Button color="dark" onclick={() => remove_attendee_modal = false}>{m.onsiteAttendees_cancel()}</Button>
        </div>
    </form>
</Modal>

<Modal id="nametag_modal" size="lg" title={m.onsiteAttendees_nametag()} bind:open={nametag_modal} outsideclose>
    <div class="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="flex gap-2 items-center">
            <Label for="role" class="whitespace-nowrap">{m.nametag_role()}:</Label>
            <Select id="role" bind:value={selected_role} onchange={onRoleChange} items={[
                { value: 'Participant', name: 'Participant' },
                { value: 'Speaker', name: 'Speaker' },
                { value: 'Chair', name: 'Chair' },
                { value: 'Organizer', name: 'Organizer' },
                { value: 'Staff', name: 'Staff' },
                { value: 'Volunteer', name: 'Volunteer' }
            ]} class="flex-1" />
        </div>
        <div class="flex gap-2 items-center">
            <Label for="orientation" class="whitespace-nowrap">{m.nametag_orientation()}:</Label>
            <Select id="orientation" value={nametag_orientation} onchange={onOrientationChange} items={[
                { value: 'portrait', name: m.nametag_portrait() },
                { value: 'landscape', name: m.nametag_landscape() }
            ]} class="flex-1" />
        </div>
    </div>
    <div class="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="flex gap-2 items-center">
            <Label for="width" class="whitespace-nowrap">{m.nametag_width()}:</Label>
            <Input type="number" id="width" bind:value={nametag_paper_width} onchange={onPaperDimensionChange} min="30" max="300" step="1" class="w-24" />
            <span class="text-sm text-gray-500">mm</span>
        </div>
        <div class="flex gap-2 items-center">
            <Label for="height" class="whitespace-nowrap">{m.nametag_height()}:</Label>
            <Input type="number" id="height" bind:value={nametag_paper_height} onchange={onPaperDimensionChange} min="30" max="300" step="1" class="w-24" />
            <span class="text-sm text-gray-500">mm</span>
        </div>
    </div>
    <iframe id="nametag" class="w-full h-[500px]" src={selected_nametag} title="Nametag">
        {m.attendees_iframeNotSupported()}
    </iframe>
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={() => {
            const iframe = document.getElementById('nametag');
            if (iframe) {
                iframe.contentWindow.print();
            }
        }}>{m.onsiteAttendees_print()}</Button>
        <Button color="dark" onclick={() => nametag_modal = false}>{m.onsiteAttendees_close()}</Button>
    </div>
</Modal>

<Modal id="batch_nametag_modal" size="lg" title={m.attendees_batchNametag()} bind:open={batch_nametag_modal} outsideclose>
    <div class="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="flex gap-2 items-center">
            <Label for="batch_role" class="whitespace-nowrap">{m.nametag_role()}:</Label>
            <Select id="batch_role" bind:value={batch_nametag_role} onchange={onBatchRoleChange} items={[
                { value: 'Participant', name: 'Participant' },
                { value: 'Speaker', name: 'Speaker' },
                { value: 'Chair', name: 'Chair' },
                { value: 'Organizer', name: 'Organizer' },
                { value: 'Staff', name: 'Staff' },
                { value: 'Volunteer', name: 'Volunteer' }
            ]} class="flex-1" />
        </div>
        <div class="flex gap-2 items-center">
            <Label for="batch_orientation" class="whitespace-nowrap">{m.nametag_orientation()}:</Label>
            <Select id="batch_orientation" value={nametag_orientation} onchange={async (e) => { nametag_orientation = e.target.value; await saveNametagSettings(); await generateBatchNametags(); }} items={[
                { value: 'portrait', name: m.nametag_portrait() },
                { value: 'landscape', name: m.nametag_landscape() }
            ]} class="flex-1" />
        </div>
    </div>
    <div class="mb-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="flex gap-2 items-center">
            <Label for="batch_width" class="whitespace-nowrap">{m.nametag_width()}:</Label>
            <Input type="number" id="batch_width" bind:value={nametag_paper_width} onchange={async () => { await saveNametagSettings(); await generateBatchNametags(); }} min="30" max="300" step="1" class="w-24" />
            <span class="text-sm text-gray-500">mm</span>
        </div>
        <div class="flex gap-2 items-center">
            <Label for="batch_height" class="whitespace-nowrap">{m.nametag_height()}:</Label>
            <Input type="number" id="batch_height" bind:value={nametag_paper_height} onchange={async () => { await saveNametagSettings(); await generateBatchNametags(); }} min="30" max="300" step="1" class="w-24" />
            <span class="text-sm text-gray-500">mm</span>
        </div>
    </div>
    {#if batch_nametag_generating}
        <div class="flex justify-center items-center h-[500px]">
            <p class="text-gray-500">...</p>
        </div>
    {:else}
        <iframe id="batch_nametag" class="w-full h-[500px]" src={batch_nametag_pdf} title={m.attendees_batchNametag()}>
            {m.attendees_iframeNotSupported()}
        </iframe>
    {/if}
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={() => {
            const iframe = document.getElementById('batch_nametag');
            if (iframe) {
                iframe.contentWindow.print();
            }
        }}>{m.onsiteAttendees_print()}</Button>
        <Button color="dark" onclick={() => batch_nametag_modal = false}>{m.onsiteAttendees_close()}</Button>
    </div>
</Modal>

<Modal id="cert_modal" size="lg" title={m.onsiteAttendees_certificate()} bind:open={cert_modal} outsideclose>
    <div class="mb-4 flex gap-2 items-center">
        <Input type="email" bind:value={cert_email} placeholder={m.attendees_emailPlaceholder()} class="flex-1" />
        <Button color="primary" onclick={sendCertificate} disabled={cert_sending || !cert_email}>
            {cert_sending ? '...' : m.attendees_sendCertificate()}
        </Button>
    </div>
    {#if cert_message.type === 'success'}
        <Alert type="success" color="green" class="mb-4">{cert_message.message}</Alert>
    {:else if cert_message.type === 'error'}
        <Alert type="error" color="red" class="mb-4">{cert_message.message}</Alert>
    {/if}
    <iframe id="cert" class="w-full h-[500px]" src={selected_cert} title="Certificate">
        {m.common_iframeUnsupported()}
    </iframe>
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={() => {
            const iframe = document.getElementById('cert');
            if (iframe) {
                iframe.contentWindow.print();
            }
        }}>{m.onsiteAttendees_print()}</Button>
        <Button color="dark" onclick={() => cert_modal = false}>{m.onsiteAttendees_close()}</Button>
    </div>
</Modal>

<Modal id="qr_modal" size="md" title={m.onsiteRegistration_qrCodeTitle()} bind:open={qr_modal} outsideclose>
    <div class="flex flex-col items-center">
        {#if qr_code_url}
            <img src={qr_code_url} alt="QR Code" class="w-full max-w-md" />
        {/if}
        <p class="text-center text-xs text-gray-500 mt-4 break-all">{registrationUrl}</p>
    </div>
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={printQRCode}>{m.onsiteAttendees_print()}</Button>
        <Button color="dark" onclick={() => qr_modal = false}>{m.onsiteAttendees_close()}</Button>
    </div>
</Modal>

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />

<ConfirmModal
    bind:open={bulk_cert_confirm_modal}
    title={m.attendees_sendCertificatesConfirmTitle()}
    message={certSkippedCount > 0
        ? m.attendees_sendCertificatesConfirmWithSkip({ eligible: certEligibleCount, skipped: certSkippedCount })
        : m.attendees_sendCertificatesConfirmCount({ count: certEligibleCount })}
    confirmLabel={m.attendees_sendCertificatesConfirmButton()}
    onConfirm={sendCertificatesToSelected}
    loading={bulk_cert_sending}
/>
