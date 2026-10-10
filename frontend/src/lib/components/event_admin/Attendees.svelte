<script>
    import { TableSearch, TableHead, TableHeadCell, TableBody, TableBodyRow, TableBodyCell, Checkbox, Button, Dropdown, DropdownItem } from '$lib/components/ui';
    import { Modal, Heading, Textarea, Select, Label, Card, Input, Spinner } from '$lib/components/ui';
    import { Alert } from '$lib/components/ui';
    import { ChevronDown } from '@lucide/svelte';
    import { enhance } from '$app/forms';
    import { invalidateAll } from '$app/navigation';
    import { Award, CircleCheck, Tag, UserMinus, UserPen } from '@lucide/svelte';
    import * as m from '$lib/paraglide/messages.js';
    import { apiMessage } from '$lib/apiMessages.js';
    import { languageTag } from '$lib/paraglide/runtime.js';
    import { generateNametagPDF, generateBatchNametagPDF, generateCertificatePDF, loadKoreanFonts } from '$lib/pdfUtils.js';
    import { getCategoryLabel, downloadTsv } from '$lib/utils.js';
    import { PagedList } from '$lib/pagedList.svelte.js';

    import RegistrationForm from '$lib/components/RegistrationForm.svelte';
    import TablePagination from '$lib/components/TablePagination.svelte';
    import ConfirmModal from '$lib/components/ConfirmModal.svelte';
    import ActionTooltip from '$lib/components/ActionTooltip.svelte';
    import SendEmailModal from '$lib/components/SendEmailModal.svelte';
    import InviteModal from '$lib/components/InviteModal.svelte';

    let { data } = $props();

    // Preload fonts on component mount
    $effect(() => {
        loadKoreanFonts();
    });

    // Registrations awaiting payment live on their own tab, so this list is
    // the confirmed roster: 'registered' is the server's name for free or paid.
    const list = new PagedList(() => `/api/event/${data.event.id}/attendees`, { filters: { status: 'registered' } });
    list.track(() => data);

    // The whole roster (or part of it) for the actions that work beyond the
    // page on screen. Deliberately not list.exportAll(): those actions always
    // covered every registrant, whatever was typed in the search box.
    async function fetchRoster(extra = {}) {
        const params = new URLSearchParams({ status: 'registered', ...extra });
        const response = await fetch(`${list.url}/export?${params}`, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error(`${response.status}`);
        return response.json();
    }

    // The selected rows, in the order they were picked, wherever they are
    // paged - and only those still on the roster: someone who has since come
    // to owe money is on the unpaid tab, not emailed or badged from here.
    async function fetchSelectedRows() {
        const asked = [...selectedAttendees];
        const rows = await list.fetchByIds(asked, { status: 'registered' });
        // Whoever is gone (deregistered, or moved to the unpaid tab) leaves
        // the selection too; with nobody left the "selected" buttons disable.
        // Only those asked about: a row ticked meanwhile stays ticked.
        const found = new Set(rows.map(a => a.id));
        selectedAttendees = selectedAttendees.filter(id => !asked.includes(id) || found.has(id));
        return asked
            .map(id => rows.find(a => a.id === id))
            .filter(Boolean)
            .map(item => attendeeRow(item, []));
    }

    // Shown when fetching rows for a whole-list or selection action fails.
    let fetch_error = $state(false);
    // Shown when an action finds nobody to act on - everyone it would reach
    // has left since the tab loaded - rather than doing nothing visible.
    let nobody_left = $state(false);

    function getDisplayName(item) {
        // Display name based on UI language
        const currentLang = languageTag();
        if (currentLang === 'ko') {
            // If UI is Korean, prefer Korean name
            return item.korean_name || item.name;
        }
        // If UI is English or default, show English name
        return item.name;
    }

    function getDisplayInstitute(item) {
        // Display institute based on UI language
        const currentLang = languageTag();
        if (currentLang === 'ko' && item.institute_ko) {
            return item.institute_ko;
        }
        return item.institute;
    }

    // The roles an admin gave, plus speaker and chair as the speaker list has
    // them - the same address the fee exemption matches - in this order;
    // none is a general participant. Each label takes the language, so the
    // CSV can carry both whatever the page is shown in.
    const ROLES = ['organizer', 'chair', 'speaker', 'staff'];
    const ROLE_LABELS = {
        organizer: (languageTag) => m.attendees_roleOrganizer({}, { languageTag }),
        chair: (languageTag) => m.speakers_roleChair({}, { languageTag }),
        speaker: (languageTag) => m.speakers_roleSpeaker({}, { languageTag }),
        staff: (languageTag) => m.attendees_roleStaff({}, { languageTag }),
    };
    // A role the speaker list gives: shown ticked in the modal, and changed
    // there rather than here.
    const listedRole = (item, role) =>
        (role === 'speaker' && item.is_speaker) || (role === 'chair' && item.is_chair);
    const rolesOf = (item) => ROLES.filter(r => (item.roles ?? []).includes(r) || listedRole(item, r));
    const roleLabel = (item, lang) =>
        rolesOf(item).map(r => ROLE_LABELS[r](lang)).join('/') || m.attendees_roleGeneral({}, { languageTag: lang });
    // What this registration is charged: exempt (speaker list or a waiver),
    // free (a free category), or the category's fee.
    const feeLabel = (item) => {
        if (item.is_fee_exempt) return m.attendees_feeExempt();
        if (!item.registration_fee) return m.attendees_feeFree();
        const amount = item.registration_fee.toLocaleString('ko-KR');
        return languageTag() === 'ko' ? `${amount} 원` : `KRW ${amount}`;
    };
    const abstractMark = (item) => item.has_abstract ? 'O' : 'X';

    // The server hands rows over ordered by id already.
    function transformToTableFormat(attendees) {
        // Extract all unique questions object
        let unique_questions = new Set();
        data.questions.forEach(item => {
            unique_questions.add(item.question.question);
        });
        attendees.forEach(item => {
            item.custom_answers.forEach(answerObj => {
                unique_questions.add(answerObj.question);
            });
        });
        const custom_headers = [...unique_questions];
        const table_data = attendees.map(item => attendeeRow(item, custom_headers));

        return {
            custom_headers,
            table_data
        };
    }

    // One table row, its answers laid out in the order of `custom_headers`.
    function attendeeRow(item, custom_headers) {
            // Create a row with empty strings for each question
            const row = {
                id: item.id,
                attendee_nametag_id: item.attendee_nametag_id,
                category: item.category,
                category_name: item.category_name,
                category_name_ko: item.category_name_ko,
                role: roleLabel(item, languageTag()),
                role_ko: roleLabel(item, 'ko'),
                role_en: roleLabel(item, 'en'),
                roles: item.roles,
                fee: feeLabel(item),
                abstract: abstractMark(item),
                is_speaker: item.is_speaker,
                is_chair: item.is_chair,
                name: getDisplayName(item),
                first_name: item.first_name,
                middle_initial: item.middle_initial,
                last_name: item.last_name,
                korean_name: item.korean_name,
                email: item.user?.email || item.user_email || '',
                nationality: item.nationality.toString(),
                institute: getDisplayInstitute(item),
                institute_en: item.institute,
                institute_ko: item.institute_ko,
                department: item.department,
                job_title: item.job_title,
                disability: item.disability,
                dietary: item.dietary,
                is_attended: item.is_attended,
                custom_answers: []
            }

            // Fill in the answers for each question
            custom_headers.forEach(question => {
                const answerObj = item.custom_answers.find(answer => answer.question === question);
                if (answerObj) {
                    row.custom_answers.push(answerObj);
                } else {
                    let empty_answer = {
                        id: undefined,
                        reference: data.questions.find(q => q.question.question === question),
                        question: question,
                        answer: ''
                    }
                    row.custom_answers.push(empty_answer);
                }
            });

            return row;
    }

    // The page on screen. Its answer columns are the event's questions plus
    // any older ones this page's registrants answered; the CSV export works
    // its own columns out from every row it exports.
    let page_table = $derived(transformToTableFormat(list.items));
    let custom_headers_attendees = $derived(page_table.custom_headers);
    let table_data_attendees = $derived(page_table.table_data);

    let csv_exporting = $state(false);
    const exportAttendeesAsCSV = async () => {
        if (csv_exporting) return;
        csv_exporting = true;
        fetch_error = false;
        nobody_left = false;
        let custom_headers, table_data;
        try {
            ({ custom_headers, table_data } = transformToTableFormat(await fetchRoster()));
        } catch (e) {
            fetch_error = true;
            return;
        } finally {
            csv_exporting = false;
        }

        // Both languages, whatever the page is shown in: the list goes to
        // name tags, programmes and reports in either, and a Korean-only
        // export left the English names to be typed back in by hand.
        const headers = [
            m.attendees_id(),
            m.attendees_roleKo(), m.attendees_roleEn(),
            m.attendees_fee(),
            m.attendees_abstractSubmitted(),
            m.attendees_firstName(), m.attendees_middleInitial(), m.attendees_lastName(),
            m.attendees_koreanName(),
            m.attendees_email(),
            m.attendees_nationality(),
            m.attendees_instituteEn(), m.attendees_instituteKo(),
            m.attendees_department(),
            m.attendees_jobTitle(),
            m.attendees_disability(),
            m.attendees_dietary(),
            ...custom_headers.map(q => q.replace(/\n/, ' ').replace(/\s+/g, ' '))
        ];

        const dataRows = table_data.map(row => [
            row.id,
            row.role_ko, row.role_en,
            row.fee,
            row.abstract,
            row.first_name, row.middle_initial, row.last_name,
            row.korean_name,
            row.email,
            stringify_nationality(row.nationality),
            row.institute_en, row.institute_ko,
            row.department,
            row.job_title,
            row.disability,
            row.dietary,
            ...row.custom_answers.map(answer => answer ? answer.answer.replace(/^- /, '').replace(/\n- /g, '; ') : "")
        ]);

        downloadTsv([headers, ...dataRows], 'attendees');
    };

    // Selection is by id, so it survives paging and searching.
    let selectedAttendees = $state([]);

    // The values double as the server's search fields.
    const searchFields = [
        { value: 'name', name: m.search_name() },
        { value: 'email', name: m.search_email() },
        { value: 'institute', name: m.search_institute() },
        { value: 'category', name: m.search_category() },
        { value: 'job_title', name: m.search_jobTitle() },
        { value: 'id', name: m.search_id() },
    ];

    // The header checkbox works on the page on screen; picks on other pages stay.
    let pageIds = $derived(table_data_attendees.map(a => a.id));
    let pageAllSelected = $derived(pageIds.length > 0 && pageIds.every(id => selectedAttendees.includes(id)));

    let attendee_modal = $state(false);
    let remove_attendee_modal = $state(false);

    // What the category select offers: everything on offer, plus the row's
    // own category when it has since been retired, so the select can show
    // it rather than silently switching the person to something else.
    function categoryOptions(row) {
        const lang = languageTag();
        const items = (data.event.registration_categories ?? []).map(c => ({ value: c.id, name: getCategoryLabel(c, lang) }));
        if (row?.category && !items.some(i => i.value === row.category)) {
            items.unshift({ value: row.category, name: getCategoryLabel(row, lang) });
        }
        if (!row?.category) items.unshift({ value: '', name: '—' });
        return items;
    }

    // The row the edit/remove modals work on, followed by id so a reload of
    // the page shows its fresh copy. Should a reload drop it from the page
    // while a modal is open, the copy taken on opening keeps the modal intact.
    let selected_id = $state(null);
    let selected_snapshot = $state(null);
    let selected_row = $derived(table_data_attendees.find(a => a.id === selected_id) ?? selected_snapshot);
    const selectRow = (id) => {
        selected_id = id;
        selected_snapshot = table_data_attendees.find(a => a.id === id) ?? null;
    };

    const showAttenteeModal = (id) => {
        selectRow(id);
        resetCustomAnswerChanges();
        message_custom_answer_changes = {};
        message_default_answer_changes = {};
        attendee_modal = true;
    };

    const showRemoveAttenteeModal = (id) => {
        selectRow(id);
        remove_attendee_modal = true;
    };

    let expand_attendees = $state(false);


    let custom_answers = $state([]);
    const addNewCustomAnswer = () => {
        custom_answers = [...custom_answers, {
            id: undefined,
            reference: {
                id: undefined,
                question: ''
            },
            question: '',
            answer: ''
        }];
    };

    const resetCustomAnswerChanges = () => {
        if (!selected_row) {
            return;
        }
        custom_answers = selected_row.custom_answers.map(a => {
            return a?{
                id: a.id,
                reference: a.reference,
                question: a.question,
                answer: a.answer
            }:{
                id: -1,
                reference: null,
                question: '',
                answer: ''
            };
        });
    };

    let message_custom_answer_changes = $state({});
    const afterSuccessfulSubmitCustomAnswerChanges = ({ formData, cancel }) => {
        if (formData.getAll('answer_reference_id[]').length !== custom_answers.length) {
            message_custom_answer_changes = { type: 'error', message: m.attendees_errorSelectReference() };
            cancel();
            return;
        }
        if (formData.getAll('answer_question[]').length !== custom_answers.length) {
            message_custom_answer_changes = { type: 'error', message: m.attendees_errorEnterQuestion() };
            cancel();
            return;
        }
        if (formData.getAll('answer_answer[]').length !== custom_answers.length) {
            message_custom_answer_changes = { type: 'error', message: m.attendees_errorEnterAnswer() };
            cancel();
            return;
        }
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                await update({ reset: false });
                message_custom_answer_changes = { type: 'success', message: m.attendees_successCustomAnswers() };
            } else {
                message_custom_answer_changes = { type: 'error', message: apiMessage(result.error) };
            }
            // scroll attendee_modal to bottom
            const modalContent = document.querySelector('#attendee_modal [role="document"]');
            if (modalContent) {
                modalContent.scrollTo({ top: modalContent.scrollHeight, behavior: 'smooth' });
            }
        };
    };

    let message_default_answer_changes = $state({});
    const afterSuccessfulSubmitDefaultAnswerChanges = () => {
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                // The save answers with the saved attendee, so the row is
                // shown changed at once; reloading every tab's data first is
                // what made each save take a second. A category change can
                // make the person owe money, and unpaid registrations live on
                // their own tab, so they leave this list then.
                const saved = result.data?.attendee;
                if (saved?.payment_status === 'pending') {
                    attendee_modal = false;
                    list.items = list.items.filter(a => a.id !== saved.id);
                    selectedAttendees = selectedAttendees.filter(id => id !== saved.id);
                } else if (saved) {
                    list.items = list.items.map(a => a.id === saved.id ? saved : a);
                }
                message_default_answer_changes = { type: 'success', message: m.attendees_successUpdate() };
                // The other tabs still read the change through the page data,
                // so that refreshes too - just without anyone waiting on it -
                // and with it this page and the roster count.
                invalidateAll();
            } else {
                message_default_answer_changes = { type: 'error', message: m.attendees_errorUpdate() };
            }
        };
    };

    const afterSuccessfulDeregistration = () => {
        return async ({ result, action, update }) => {
            if (result.type === 'success') {
                selectedAttendees = selectedAttendees.filter(id => id !== selected_row?.id);
                await update({ reset: false });
            }
            remove_attendee_modal = false;
        };
    };

    const toggleAttended = async (id, currentValue) => {
        const formData = new FormData();
        formData.append('id', id);
        formData.append('is_attended', (!currentValue).toString());
        const response = await fetch('?/toggle_attended', {
            method: 'POST',
            body: formData
        });
        if (response.ok) {
            // A raw fetch re-runs no loader; patch the row where it sits, then
            // reload the page so a load already in flight cannot put the old
            // value back.
            const item = list.items.find(a => a.id === id);
            if (item) item.is_attended = !currentValue;
            list.load();
        }
    };

    let form_config = {
        hide_login_info: true,
        show_english_name: true,
        show_korean_name: true,
    };

    let edit_institution_resolved = $derived(selected_row ? {
        name_en: selected_row.institute_en,
        name_ko: selected_row.institute_ko,
    } : null);

    const stringify_nationality = (value) => {
        if (value === '1') {
            return m.nationality_korean();
        } else if (value === '2') {
            return m.nationality_nonKorean();
        }
        return m.nationality_notSpecified();
    };

    let invite_modal = $state(false);
    let send_email_modal = $state(false);
    let emailRecipients = $state('');
    let email_preparing = $state(false);
    // The addresses are fetched when the modal is asked for: "all" is the
    // whole roster whatever the search, "selected" may span pages.
    const openSendEmailModal = async (loadRows) => {
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
            send_email_modal = true;
        } catch (e) {
            fetch_error = true;
        } finally {
            email_preparing = false;
        }
    };
    const showSendEmailModal = () => openSendEmailModal(fetchSelectedRows);
    const showSendEmailToAllModal = () =>
        openSendEmailModal(async () => (await fetchRoster()).map(item => attendeeRow(item, [])));

    let nametag_modal = $state(false);
    let selected_nametag = $state('');
    let selected_nametag_row = $state(null);
    let selected_role = $state('Participant');

    // Nametag paper settings from event
    let nametag_paper_width = $state(data.event.nametag_paper_width ?? 90);
    let nametag_paper_height = $state(data.event.nametag_paper_height ?? 100);
    let nametag_orientation = $state(data.event.nametag_orientation ?? 'portrait');

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
            id: p.attendee_nametag_id,
            paperWidth: nametag_paper_width,
            paperHeight: nametag_paper_height,
            orientation: nametag_orientation
        });
    };

    // The row is kept, not looked up again: saving the paper settings reloads
    // the page data, and with it the table.
    const showNametagModal = async (id) => {
        selected_nametag_row = table_data_attendees.find(a => a.id === id);
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
    // Fetched once when the modal opens; changing the role or paper only redraws.
    let batch_nametag_rows = $state([]);

    const generateBatchNametags = async () => {
        if (batch_nametag_rows.length === 0) return;
        batch_nametag_generating = true;
        const attendees = batch_nametag_rows.map(a => ({ name: a.name, institute: a.institute, id: a.attendee_nametag_id }));
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
            batch_nametag_rows = await fetchSelectedRows();
        } catch (e) {
            batch_nametag_generating = false;
            fetch_error = true;
            return;
        }
        if (batch_nametag_rows.length === 0) {
            batch_nametag_generating = false;
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
    let selected_cert_row = $state(null);

    // Bulk certificate sending
    let bulk_cert_sending = $state(false);
    let bulk_cert_preparing = $state(false);
    let bulk_cert_message = $state({});
    let bulk_cert_confirm_modal = $state(false);

    // Fetched when the confirm opens, so its numbers are those the send uses:
    // a certificate goes to whoever attended and has an address; the rest of
    // the chosen people are counted as skipped.
    let cert_targets = $state([]);
    let certEligibleCount = $derived(cert_targets.length);
    let certSkippedCount = $state(0);

    const openCertificatesConfirm = async (loadRows) => {
        if (bulk_cert_preparing || bulk_cert_sending) return;
        bulk_cert_preparing = true;
        fetch_error = false;
        nobody_left = false;
        try {
            const { rows, total } = await loadRows();
            if (total === 0) {
                nobody_left = true;
                return;
            }
            cert_targets = rows.filter(p => p.email && p.is_attended);
            certSkippedCount = Math.max(0, total - cert_targets.length);
            bulk_cert_confirm_modal = true;
        } catch (e) {
            fetch_error = true;
        } finally {
            bulk_cert_preparing = false;
        }
    };

    const showSendCertificatesConfirm = () => {
        if (selectedAttendees.length === 0) return;
        openCertificatesConfirm(async () => {
            // Counted from the rows fetched: a row ticked while they were
            // fetched is not part of this send.
            const rows = await fetchSelectedRows();
            return { rows, total: rows.length };
        });
    };

    // Only the attended are fetched; the roster size comes from the counts
    // the table already has, which ignore the search as this action does.
    const showSendCertificatesToAllConfirm = () =>
        openCertificatesConfirm(async () => {
            const rows = (await fetchRoster({ attended: 'true' })).map(item => attendeeRow(item, []));
            // The roster size, for the skipped count: the table's, or asked
            // for here when its page never loaded.
            let registered = list.counts.registered;
            if (registered === undefined) {
                const response = await fetch(`${list.url}?status=registered&limit=1`, { headers: { Accept: 'application/json' } });
                if (!response.ok) throw new Error(`${response.status}`);
                registered = (await response.json()).total ?? 0;
            }
            return { rows, total: Math.max(registered, rows.length) };
        });

    const sendCertificatesToSelected = async () => {
        bulk_cert_confirm_modal = false;
        const targets = cert_targets;
        if (targets.length === 0 || bulk_cert_sending) return;
        bulk_cert_sending = true;
        bulk_cert_message = {};
        try {
            for (const p of targets) {
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
                formData.append('attendee_type', 'attendee');
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

    const showCertificateModal = async (id) => {
        const p = table_data_attendees.find(a => a.id === id);
        selected_cert_row = p;
        cert_email = p.email;
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
            formData.append('attendee_type', 'attendee');
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
</script>

{#snippet process_spaces(text)}
    <!-- Attendee-supplied text. Rendered as text with whitespace preserved by
         CSS; it must never go through {@html}, which let any registrant run
         script in an event admin's browser. -->
    <span class="whitespace-pre-wrap">{text}</span>
{/snippet}

<Heading tag="h2" class="text-xl font-bold mb-3">{m.attendees_title()}</Heading>
<p class="font-light mb-6">{m.attendees_description()}</p>
<div class="flex justify-end items-center gap-2 flex-wrap">
    <Button color="primary" size="sm">{m.attendees_emailActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailToAllModal} disabled={email_preparing || list.counts.registered === 0}>{m.attendees_sendEmailToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendEmailModal} disabled={selectedAttendees.length === 0 || email_preparing}>{m.attendees_sendEmailToSelected()}</DropdownItem>
    </Dropdown>
    <Button color="primary" size="sm" onclick={() => invite_modal = true}>{m.attendees_inviteByEmail()}</Button>

    <Button color="primary" size="sm" disabled={bulk_cert_sending || bulk_cert_preparing}>{bulk_cert_sending ? m.attendees_sendingCertificates() : m.attendees_certificateActions()}<ChevronDown class="w-3 h-3 ms-1" /></Button>
    <Dropdown class="w-auto list-none p-1">
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesToAllConfirm} disabled={bulk_cert_sending || bulk_cert_preparing || list.counts.registered === 0}>{m.attendees_sendCertificatesToAll()}</DropdownItem>
        <DropdownItem class="text-sm whitespace-nowrap" onclick={showSendCertificatesConfirm} disabled={selectedAttendees.length === 0 || bulk_cert_sending || bulk_cert_preparing}>{m.attendees_sendCertificatesToSelected()}</DropdownItem>
    </Dropdown>

    <Button color="primary" size="sm" onclick={showBatchNametagModal} disabled={selectedAttendees.length === 0 || batch_nametag_generating}>
        {batch_nametag_generating ? '...' : m.attendees_printNametagsForSelected()}
    </Button>
    <Button color="primary" size="sm" onclick={() => expand_attendees = !expand_attendees}>{expand_attendees ? m.attendees_collapseHeaders() : m.attendees_expandHeaders()}</Button>
    <Button color="primary" size="sm" onclick={exportAttendeesAsCSV} disabled={csv_exporting}>{csv_exporting ? '...' : m.attendees_exportCSV()}</Button>
</div>
{#if fetch_error || (list.error && list.items.length > 0)}
    <Alert type="error" color="red" class="mt-3">{m.common_error()}</Alert>
{/if}
{#if nobody_left}
    <Alert color="blue" class="mt-3">{m.attendees_noRecords()}</Alert>
{/if}
{#if bulk_cert_message.type === 'success'}
    <Alert type="success" color="green" class="mt-3">{bulk_cert_message.message}</Alert>
{:else if bulk_cert_message.type === 'error'}
    <Alert type="error" color="red" class="mt-3">{bulk_cert_message.message}</Alert>
{/if}
<!-- The whole roster, whatever the search; blank until the first page arrives. -->
<p class="mt-5 mb-3 text-sm text-right">
    {#if list.counts.registered !== undefined}{list.counts.registered}{:else if list.error && !list.loading}–{:else}<Spinner size="4" />{/if} {m.attendees_peopleRegistered()}
</p>
<TableSearch placeholder={m.attendees_searchPlaceholder()} hoverable={true} bind:inputValue={list.search} bind:field={list.field} fields={searchFields}>
    <TableHead>
        <TableHeadCell class="w-1">
            <Checkbox
                checked={pageAllSelected}
                intermediate={selectedAttendees.length > 0 && !pageAllSelected}
                onclick={(e) => {
                    if (e.target.checked) {
                        selectedAttendees = [...selectedAttendees, ...pageIds.filter(id => !selectedAttendees.includes(id))];
                    } else {
                        selectedAttendees = selectedAttendees.filter(id => !pageIds.includes(id));
                    }
                }}
            />
        </TableHeadCell>
        <TableHeadCell>{m.attendees_id()}</TableHeadCell>
        <TableHeadCell class="w-1">{m.attendees_attended()}</TableHeadCell>
        <TableHeadCell>{m.attendees_role()}</TableHeadCell>
        <TableHeadCell>{m.attendees_name()}</TableHeadCell>
        <TableHeadCell>{m.attendees_tier()}</TableHeadCell>
        <TableHeadCell>{m.attendees_fee()}</TableHeadCell>
        <TableHeadCell class="w-1 whitespace-nowrap">{m.attendees_abstractSubmitted()}</TableHeadCell>
        <TableHeadCell>{m.attendees_email()}</TableHeadCell>
        <TableHeadCell>{m.attendees_nationality()}</TableHeadCell>
        <TableHeadCell>{m.attendees_institute()}</TableHeadCell>
        {#if expand_attendees}
            <TableHeadCell>{m.attendees_koreanName()}</TableHeadCell>
            <TableHeadCell>{m.attendees_department()}</TableHeadCell>
            <TableHeadCell>{m.attendees_jobTitle()}</TableHeadCell>
            <TableHeadCell>{m.attendees_disability()}</TableHeadCell>
            <TableHeadCell>{m.attendees_dietary()}</TableHeadCell>
            {#each custom_headers_attendees as header}
                <TableHeadCell>{@render process_spaces(header)}</TableHeadCell>
            {/each}
        {/if}
        <TableHeadCell class="w-1">{m.attendees_actions()}</TableHeadCell>
    </TableHead>
    <TableBody tableBodyClass="divide-y">
        {#each table_data_attendees as row}
            <TableBodyRow>
                <TableBodyCell><Checkbox checked={selectedAttendees.includes(row.id)} onclick={(e) => {
                    if (e.target.checked) {
                        selectedAttendees = [...selectedAttendees, row.id];
                    } else {
                        selectedAttendees = selectedAttendees.filter(a => a !== row.id);
                    }
                }} /></TableBodyCell>
                <TableBodyCell>{row.attendee_nametag_id}</TableBodyCell>
                <TableBodyCell>
                    <button onclick={() => toggleAttended(row.id, row.is_attended)} class="cursor-pointer">
                        <CircleCheck class="w-5 h-5 {row.is_attended ? 'text-green-500' : 'text-gray-300'}" />
                    </button>
                </TableBodyCell>
                <TableBodyCell class="whitespace-nowrap">{row.role}</TableBodyCell>
                <TableBodyCell>{row.name}</TableBodyCell>
                <TableBodyCell>{getCategoryLabel(row, languageTag())}</TableBodyCell>
                <TableBodyCell class="whitespace-nowrap">{row.fee}</TableBodyCell>
                <TableBodyCell class="text-center">{row.abstract}</TableBodyCell>
                <TableBodyCell>{row.email}</TableBodyCell>
                <TableBodyCell>{stringify_nationality(row.nationality)}</TableBodyCell>
                <TableBodyCell>{row.institute}</TableBodyCell>
                {#if expand_attendees}
                    <TableBodyCell>{row.korean_name}</TableBodyCell>
                    <TableBodyCell>{row.department}</TableBodyCell>
                    <TableBodyCell>{row.job_title}</TableBodyCell>
                    <TableBodyCell>{row.disability}</TableBodyCell>
                    <TableBodyCell>{row.dietary}</TableBodyCell>
                    {#each row.custom_answers as a}
                        <TableBodyCell>{@render process_spaces(a?a.answer:"")}</TableBodyCell>
                    {/each}
                {/if}
                <TableBodyCell>
                    <div class="flex justify-center gap-2">
                        <ActionTooltip text={m.attendees_nametag()}>
                            <Button color="none" size="none" onclick={() => showNametagModal(row.id)}>
                                <Tag class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.attendees_certificate()}>
                            <Button color="none" size="none" onclick={() => showCertificateModal(row.id)} disabled={!row.is_attended}>
                                <Award class="w-5 h-5 {row.is_attended ? '' : 'opacity-30'}" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.attendees_detailsTitle()}>
                            <Button color="none" size="none" onclick={() => showAttenteeModal(row.id)}>
                                <UserPen class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                        <ActionTooltip text={m.attendees_removeTitle()}>
                            <Button color="none" size="none" onclick={() => showRemoveAttenteeModal(row.id)}>
                                <UserMinus class="w-5 h-5" />
                            </Button>
                        </ActionTooltip>
                    </div>
                </TableBodyCell>
            </TableBodyRow>
        {/each}
        {#if table_data_attendees.length === 0}
            <TableBodyRow>
                <TableBodyCell colspan={
                    expand_attendees ? custom_headers_attendees.length + 17 : 12
                } class="text-center">{#if list.loading}<Spinner size="6" />{:else if list.error}{m.common_error()}{:else}{m.attendees_noRecords()}{/if}</TableBodyCell>
            </TableBodyRow>
        {/if}
    </TableBody>
</TableSearch>

<TablePagination currentPage={list.page} totalPages={list.totalPages} onPageChange={p => list.goto(p)} />

<Modal id="attendee_modal" size="xl" title={m.attendees_detailsTitle()} bind:open={attendee_modal} outsideclose>
    <form method="post" action="?/update_attendee" use:enhance={afterSuccessfulSubmitDefaultAnswerChanges}>
        <input type="hidden" name="id" value={selected_row.id} />
        <Heading tag="h2" class="text-lg font-bold pt-3 mb-6">{m.attendees_basicInformation()}</Heading>
        <div class="grid gap-6 mb-6 md:grid-cols-2">
            <div>
                <Label for="attendee_category" class="block mb-2">{m.attendees_tier()}</Label>
                <Select id="attendee_category" name="category" value={selected_row.category ?? ''} items={categoryOptions(selected_row)} />
            </div>
            <div>
                <Label class="block mb-2">{m.attendees_role()}</Label>
                <input type="hidden" name="roles_present" value="1" />
                <div class="flex flex-wrap gap-x-6 gap-y-2 pt-2">
                    {#each ROLES as role (role)}
                        {#if listedRole(selected_row, role)}
                            <!-- From the speaker list: a disabled box sends nothing,
                                 so a role also given here is kept as it was. -->
                            <Checkbox checked disabled>{ROLE_LABELS[role](languageTag())}</Checkbox>
                            {#if selected_row.roles?.includes(role)}<input type="hidden" name="roles" value={role} />{/if}
                        {:else}
                            <Checkbox name="roles" value={role} checked={selected_row.roles?.includes(role) ?? false}>{ROLE_LABELS[role](languageTag())}</Checkbox>
                        {/if}
                    {/each}
                </div>
                {#if listedRole(selected_row, 'speaker') || listedRole(selected_row, 'chair')}
                    <p class="mt-2 text-xs text-gray-500">{m.attendees_roleFromSpeakerList()}</p>
                {/if}
            </div>
        </div>
        <RegistrationForm data={selected_row} config={form_config} institution_resolved={edit_institution_resolved} />
        {#if message_default_answer_changes.type === 'success'}
            <Alert type="success" color="green">{message_default_answer_changes.message}</Alert>
        {:else if message_default_answer_changes.type === 'error'}
            <Alert type="error" color="red">{message_default_answer_changes.message}</Alert>
        {/if}
        <div class="flex justify-center mt-6">
            <Button color="primary" type="submit">{m.attendees_updateAttendee()}</Button>
        </div>
    </form>
    <Heading tag="h2" class="text-lg font-bold pt-3 mb-6">{m.attendees_answersTitle()}</Heading>
    <form method="post" action="?/update_answers" use:enhance={afterSuccessfulSubmitCustomAnswerChanges}>
        <div class="flex justify-center gap-2 mb-6">
            <Button color="primary" onclick={resetCustomAnswerChanges}>{m.attendees_resetChanges()}</Button>
            <Button type="submit" color="primary">{m.attendees_applyChanges()}</Button>
        </div>
        <input type="hidden" name="attendee_id" value={selected_row.id} />
        {#if custom_answers.length > 0}
            {#each custom_answers as answer, idx}
                <Card size="xl" class="mb-6 p-6">
                    <div class="mb-6">
                        <Label for={`answer_reference_id_${idx}`} class="block mb-2">{m.attendees_referenceQuestion()}</Label>
                        <Select id={`answer_reference_id_${idx}`} name="answer_reference_id[]" items={data.questions.map(q => ({
                            value: q.id,
                            name: q.question.question
                        }))} onchange={(e) => {
                            const q_id = parseInt(e.target.value);
                            const q = data.questions.find(q => q.id === q_id);
                            custom_answers[idx].reference = q;
                            custom_answers[idx].question = q.question.question;
                            custom_answers[idx].answer = '';
                        }} value={answer.reference.id} />
                    </div>
                    <div class="mb-6">
                        <Label for={`answer_question_${idx}`} class="block mb-2">{m.attendees_question()}</Label>
                        <Textarea class="mb-2 w-full" id={`answer_question_${idx}`} name="answer_question[]" bind:value={answer.question} readonly={answer.reference.question !== ""} />
                    </div>
                    <div class="mb-6">
                        <Label for={`answer_answer_${idx}`} class="block mb-2">{m.attendees_answer()}</Label>
                        {#if answer.reference?.question?.type === 'checkbox' && answer.reference?.question?.options}
                            {@const options = Array.isArray(answer.reference.question.options) ? answer.reference.question.options : answer.reference.question.options.split('\n').filter(o => o.trim())}
                            {@const parsedAnswers = answer.answer.split(/\r?\n/).reduce((acc, line) => {
                                const match = line.trim().match(/^-\s*(.+?):\s*(.+)$/);
                                if (match) acc[match[1].trim()] = match[2].trim() === 'on' || match[2].trim() === 'true' || match[2].trim() === 'checked';
                                return acc;
                            }, {})}
                            <div class="space-y-2">
                                {#each options as option, oidx}
                                    <Checkbox
                                        id={`answer_checkbox_${idx}_${oidx}`}
                                        checked={parsedAnswers[option] ?? false}
                                        onchange={(e) => {
                                            const currentParsed = answer.answer.split(/\r?\n/).reduce((acc, line) => {
                                                const match = line.trim().match(/^-\s*(.+?):\s*(.+)$/);
                                                if (match) acc[match[1].trim()] = match[2].trim();
                                                return acc;
                                            }, {});
                                            currentParsed[option] = e.target.checked ? 'on' : 'off';
                                            custom_answers[idx].answer = options.map(o => `- ${o}: ${currentParsed[o] || 'off'}`).join('\n');
                                        }}
                                    >{option}</Checkbox>
                                {/each}
                            </div>
                            <input type="hidden" name="answer_answer[]" value={answer.answer} />
                        {:else if answer.reference?.question?.type === 'select' && answer.reference?.question?.options}
                            {@const options = Array.isArray(answer.reference.question.options) ? answer.reference.question.options : answer.reference.question.options.split('\n').filter(o => o.trim())}
                            <Select id={`answer_answer_${idx}`} bind:value={custom_answers[idx].answer} items={options.map(o => ({ value: o, name: o }))} />
                            <input type="hidden" name="answer_answer[]" value={answer.answer} />
                        {:else}
                            <Textarea id={`answer_answer_${idx}`} name="answer_answer[]" bind:value={answer.answer} class="w-full" />
                        {/if}
                    </div>
                    <div class="flex justify-center gap-2">
                        <Button color="red" onclick={
                            () => custom_answers = custom_answers.filter((a, i) => i !== idx)
                        }>{m.attendees_deleteAnswer()}</Button>
                    </div>
                </Card>
            {/each}
        {:else}
            <p class="text-center mb-6">{m.attendees_noAnswers()}</p>
        {/if}
        <div class="flex justify-center gap-2 mb-6">
            <Button color="dark" onclick={addNewCustomAnswer}>+</Button>
        </div>
        <div class="mb-6">
            {#if message_custom_answer_changes.type === 'success'}
                <Alert type="success" color="green">{message_custom_answer_changes.message}</Alert>
            {:else if message_custom_answer_changes.type === 'error'}
                <Alert type="error" color="red">{message_custom_answer_changes.message}</Alert>
            {/if}
        </div>
        <div class="flex justify-center gap-2">
            <Button color="primary" onclick={resetCustomAnswerChanges}>{m.attendees_resetChanges()}</Button>
            <Button type="submit" color="primary">{m.attendees_applyChanges()}</Button>
        </div>
    </form>
</Modal>

<Modal id="remove_attendee_modal" size="sm" title={m.attendees_removeTitle()} bind:open={remove_attendee_modal} outsideclose>
    <form method="post" action="?/deregister_attendee" use:enhance={afterSuccessfulDeregistration}>
        <input type="hidden" name="id" value={selected_row.id} />
        <p class="font-light mb-6">{m.attendees_removeConfirm()}</p>
        <div class="flex justify-center gap-2">
            <Button color="red" type="submit">{m.attendees_deregister()}</Button>
            <Button color="dark" onclick={() => remove_attendee_modal = false}>{m.attendees_cancel()}</Button>
        </div>
    </form>
</Modal>

<SendEmailModal bind:open={send_email_modal} recipients={emailRecipients} eventadmins={data.eventadmins} />
<InviteModal bind:open={invite_modal} template={data.email_templates?.invitation} />

<Modal id="nametag_modal" size="lg" title={m.attendees_nametag()} bind:open={nametag_modal} outsideclose>
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
    <iframe id="nametag" class="w-full h-[500px]" src={selected_nametag} title={m.attendees_nametag()}>
        {m.attendees_iframeNotSupported()}
    </iframe>
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={() => {
            const iframe = document.getElementById('nametag');
            if (iframe) {
                iframe.contentWindow.print();
            }
        }}>{m.attendees_print()}</Button>
        <Button color="dark" onclick={() => nametag_modal = false}>{m.attendees_close()}</Button>
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
        }}>{m.attendees_print()}</Button>
        <Button color="dark" onclick={() => batch_nametag_modal = false}>{m.attendees_close()}</Button>
    </div>
</Modal>

<Modal id="cert_modal" size="lg" title={m.attendees_certificate()} bind:open={cert_modal} outsideclose>
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
    <iframe id="cert" class="w-full h-[500px]" src={selected_cert} title={m.attendees_certificate()}>
        {m.attendees_iframeNotSupported()}
    </iframe>
    <div class="flex justify-center mt-6 gap-2">
        <Button color="primary" onclick={() => {
            const iframe = document.getElementById('cert');
            if (iframe) {
                iframe.contentWindow.print();
            }
        }}>{m.attendees_print()}</Button>
        <Button color="dark" onclick={() => cert_modal = false}>{m.attendees_close()}</Button>
    </div>
</Modal>

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
