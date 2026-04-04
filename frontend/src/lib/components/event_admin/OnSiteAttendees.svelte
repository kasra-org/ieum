<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Button, Dropdown, DropdownItem } from 'flowbite-svelte';
    import { Modal, Heading, Textarea, Select, Label, Card, Input } from 'flowbite-svelte';
    import { Alert } from 'flowbite-svelte';
    import { ChevronDownOutline } from 'flowbite-svelte-icons';
    import { enhance } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import { UserEditSolid, UserRemoveSolid, TagOutline, AwardOutline, CheckCircleSolid } from 'flowbite-svelte-icons';
    import * as m from '$lib/paraglide/messages.js';
    import { generateNametagPDF, generateBatchNametagPDF, generateCertificatePDF, loadKoreanFonts } from '$lib/pdfUtils.js';

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

    // Local overrides for optimistic UI updates (e.g., toggling confirmed)
    let localOverrides = $state({});

    // Create a sorted derived value for attendees, applying local overrides
    let sortedAttendees = $derived.by(() => {
        return [...data.onsite_attendees]
            .map(a => {
                const override = localOverrides[a.id];
                return override ? { ...a, ...override } : a;
            })
            .sort((a, b) => a.id - b.id);
    });

    const exportAttendeesAsCSV = () => {
        const csv = [
            [   "ID",
                "Name",
                "Email",
                "Institute",
                "Job Title"
            ],
            ...sortedAttendees.map(row => [
                row.id,
                row.name,
                row.email,
                row.institute,
                row.job_title
            ])
        ].map(row => row.join('\t')).join('\r\n');

        // Convert to UTF-16 LE with BOM for Excel compatibility
        const BOM = '\uFEFF';
        const csvWithBOM = BOM + csv;

        // Encode to UTF-16 LE
        const buffer = new ArrayBuffer(csvWithBOM.length * 2);
        const view = new Uint16Array(buffer);
        for (let i = 0; i < csvWithBOM.length; i++) {
            view[i] = csvWithBOM.charCodeAt(i);
        }

        const blob = new Blob([buffer], { type: 'text/csv;charset=utf-16le;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        // Get current timestamp in YYYY-MM-DD_HH-MM-SS format
        const timestamp = new Date().toISOString().replace(/T/, '_').replace(/\..+/, '').replace(/:/g, '-');
        a.href = url;
        a.download = `onsite_attendees_${timestamp}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    let searchTermAttendee = $state('');
    let selectedAttendees = $state([]);
    let currentPage = $state(1);
    const itemsPerPage = 10;

    let filteredAttendees = $derived(
        sortedAttendees.filter((item) => item.name.toLowerCase().includes(searchTermAttendee.toLowerCase()))
    );

    // Reset to page 1 when search changes
    $effect(() => {
        searchTermAttendee;
        currentPage = 1;
    });

    let totalPages = $derived(Math.ceil(filteredAttendees.length / itemsPerPage));
    let paginatedAttendees = $derived(
        filteredAttendees.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
    );

    function handlePageChange(page) {
        currentPage = page;
    }

    let attendee_modal = $state(false);
    let remove_attendee_modal = $state(false);

    let selected_idx = $state(null);
    const showAttenteeModal = (id) => {
        selected_idx = sortedAttendees.findIndex(item => item.id === id);
        attendee_modal = true;
    };

    const showRemoveAttenteeModal = (id) => {
        selected_idx = sortedAttendees.findIndex(item => item.id === id);
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
                await update({ reset: false });
            }
            remove_attendee_modal = false;
        };
    };

    const toggleConfirm = async (id, currentValue) => {
        const formData = new FormData();
        formData.append('id', id);
        formData.append('is_confirmed', (!currentValue).toString());
        const response = await fetch('?/confirm_onsite_attendee', {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            localOverrides = { ...localOverrides, [id]: { is_confirmed: !currentValue } };
        }
    };

    let nametag_modal = $state(false);
    let selected_nametag = $state('');
    let selected_nametag_id = $state(null);
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
        if (selected_nametag_id !== null) {
            await generateNametag(selected_nametag_id, selected_role);
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

    const generateNametag = async (id, role) => {
        const p = sortedAttendees.find(a => a.id === id);
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

    const showNametagModal = async (id) => {
        selected_nametag_id = id;
        selected_role = 'Participant';
        await generateNametag(id, selected_role);
        nametag_modal = true;
    };

    const onRoleChange = async (e) => {
        await generateNametag(selected_nametag_id, e.target.value);
    };

    // Batch nametag printing
    let batch_nametag_modal = $state(false);
    let batch_nametag_pdf = $state('');
    let batch_nametag_role = $state('Participant');
    let batch_nametag_generating = $state(false);

    const generateBatchNametags = async () => {
        if (selectedAttendees.length === 0) return;
        batch_nametag_generating = true;
        const attendees = selectedAttendees.map(id => {
            const a = sortedAttendees.find(att => att.id === id);
            return { name: a.name, institute: a.institute, id: a.onsiteattendee_nametag_id };
        });
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
        batch_nametag_role = 'Participant';
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
    let selected_cert_onsite_id = $state(null);

    // Bulk certificate sending
    let bulk_cert_sending = $state(false);
    let bulk_cert_message = $state({});
    let bulk_cert_confirm_modal = $state(false);
    let cert_send_all = $state(false);

    let certTargetIds = $derived(cert_send_all ? sortedAttendees.map(a => a.id) : selectedAttendees);
    let certEligibleCount = $derived(
        certTargetIds.filter(id => {
            const p = sortedAttendees.find(a => a.id === id);
            return p && p.email && p.is_confirmed;
        }).length
    );
    let certSkippedCount = $derived(certTargetIds.length - certEligibleCount);

    const showSendCertificatesConfirm = () => {
        if (selectedAttendees.length === 0) return;
        cert_send_all = false;
        bulk_cert_confirm_modal = true;
    };

    const showSendCertificatesToAllConfirm = () => {
        cert_send_all = true;
        bulk_cert_confirm_modal = true;
    };

    const sendCertificatesToSelected = async () => {
        bulk_cert_confirm_modal = false;
        const targetIds = cert_send_all ? sortedAttendees.map(a => a.id) : selectedAttendees;
        if (targetIds.length === 0 || bulk_cert_sending) return;
        bulk_cert_sending = true;
        bulk_cert_message = {};
        try {
            for (const id of targetIds) {
                const p = sortedAttendees.find(a => a.id === id);
                if (!p.email || !p.is_confirmed) continue;
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
                formData.append('attendee_id', id);
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

    const showCertificateModal = async (id) => {
        const p = sortedAttendees.find(a => a.id === id);
        selected_cert_onsite_id = id;
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
            const p = sortedAttendees.find(a => a.id === selected_cert_onsite_id);
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
            formData.append('attendee_id', selected_cert_onsite_id);
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

    let send_email_modal = $state(false);
    let send_email_to_all = $state(false);
    const showSendEmailModal = () => {
        send_email_to_all = false;
        send_email_modal = true;
    };
    const showSendEmailToAllModal = () => {
        send_email_to_all = true;
        send_email_modal = true;
    };
    let emailRecipients = $derived(
        send_email_to_all
            ? sortedAttendees.map(a => a.email).filter(Boolean).join("; ")
            : selectedAttendees.map(id => sortedAttendees.find(a => a.id === id)?.email).filter(Boolean).join("; ")
    );
</script>

<Heading tag="h2" class="text-xl font-bold mb-3">{m.onsiteAttendees_title()}</Heading>
<p class="font-light mb-6">{m.onsiteAttendees_description()}</p>

<div class="flex justify-end items-center gap-2 flex-wrap mb-4">
    <Button color="primary" size="sm">{m.attendees_emailActions()}<ChevronDownOutline class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailToAllModal}>{m.attendees_sendEmailToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailModal} disabled={selectedAttendees.length === 0}>{m.attendees_sendEmailToSelected()}</DropdownItem>
    </Dropdown>

    <Button color="primary" size="sm" disabled={bulk_cert_sending}>{bulk_cert_sending ? m.attendees_sendingCertificates() : m.attendees_certificateActions()}<ChevronDownOutline class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesToAllConfirm} disabled={bulk_cert_sending}>{m.attendees_sendCertificatesToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesConfirm} disabled={selectedAttendees.length === 0 || bulk_cert_sending}>{m.attendees_sendCertificatesToSelected()}</DropdownItem>
    </Dropdown>

    <Button color="primary" size="sm" onclick={showBatchNametagModal} disabled={selectedAttendees.length === 0 || batch_nametag_generating}>
        {batch_nametag_generating ? '...' : m.attendees_printNametagsForSelected()}
    </Button>
    <Button color="primary" size="sm" onclick={showQRCodeModal}>{m.onsiteRegistration_qrCode()}</Button>
    <Button color="primary" size="sm" onclick={exportAttendeesAsCSV}>{m.onsiteAttendees_exportCSV()}</Button>
</div>
{#if bulk_cert_message.type === 'success'}
    <Alert type="success" color="green" class="mt-3">{bulk_cert_message.message}</Alert>
{:else if bulk_cert_message.type === 'error'}
    <Alert type="error" color="red" class="mt-3">{bulk_cert_message.message}</Alert>
{/if}
<p class="mt-5 mb-3 text-sm text-right">{sortedAttendees.length} {m.onsiteAttendees_peopleRegistered()}</p>
<TableSearch placeholder={m.onsiteAttendees_searchPlaceholder()} hoverable={true} bind:inputValue={searchTermAttendee}>
    <TableHead>
        <TableHeadCell class="w-1">
            <Checkbox
                checked={selectedAttendees.length > 0 && selectedAttendees.length === sortedAttendees.length}
                intermediate={
                    selectedAttendees.length > 0 && (selectedAttendees.length < sortedAttendees.length)
                }
                onclick={(e) => {
                    if (e.target.checked) {
                        selectedAttendees = filteredAttendees.map(a => a.id);
                    } else {
                        selectedAttendees = [];
                    }
                }}
            />
        </TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_id()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.onsiteAttendees_confirmed()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_name()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_email()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_institute()}</TableHeadCell>
        <TableHeadCell>{m.onsiteAttendees_jobTitle()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.onsiteAttendees_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each paginatedAttendees as row}
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
                    <button onclick={() => toggleConfirm(row.id, row.is_confirmed)} class="cursor-pointer">
                        <CheckCircleSolid class="w-5 h-5 {row.is_confirmed ? 'text-green-500' : 'text-gray-300'}" />
                    </button>
                </TableBodyCell>
                <TableBodyCell>{row.name}</TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>{row.institute}</TableBodyCell>
                <TableBodyCell>{row.job_title}</TableBodyCell>
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.onsiteAttendees_nametag()}>
                            <Button color="none" size="none" onclick={() => showNametagModal(row.id)}>
                                <TagOutline class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_certificate()}>
                            <Button color="none" size="none" onclick={() => showCertificateModal(row.id)} disabled={!row.is_confirmed}>
                                <AwardOutline class="w-5 h-5 {row.is_confirmed ? '' : 'opacity-30'}" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_detailsTitle()}>
                            <Button color="none" size="none" onclick={() => showAttenteeModal(row.id)}>
                                <UserEditSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.onsiteAttendees_remove()}>
                            <Button color="none" size="none" onclick={() => showRemoveAttenteeModal(row.id)}>
                                <UserRemoveSolid class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if filteredAttendees.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan="8" class="text-center">{m.onsiteAttendees_noRecords()}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination {currentPage} {totalPages} onPageChange={handlePageChange} />

<Modal id="attendee_modal" size="xl" title={m.onsiteAttendees_detailsTitle()} bind:open={attendee_modal} outsideclose>
    <form method="post" action="?/update_onsite_attendee" use:enhance={afterSuccessfulSubmit}>
        <input type="hidden" name="id" value={sortedAttendees[selected_idx].id} />
        <OnSiteRegistrationForm data={sortedAttendees[selected_idx]} />
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
        <input type="hidden" name="id" value={sortedAttendees[selected_idx].id} />
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
        Your browser does not support iframes.
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
