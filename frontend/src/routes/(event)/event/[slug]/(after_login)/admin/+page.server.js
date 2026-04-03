import { get, post } from '$lib/fetch';
import { error } from '@sveltejs/kit';
import { generateOrderId } from '$lib/utils';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies, request }) {
    let rtn = await parent();

    const get_data_or_404 = async (item) => {
        const response = await get(`api/${item}`, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(404, "Not Found");
        }
    }

    const get_data_or_404_event = async (item) => {
        return get_data_or_404(`event/${params.slug}/${item}`);
    }

    rtn.event = await get_data_or_404(`admin/event/${params.slug}`);

    // Superusers (staff) get access to full user list, event admins use attendees
    if (rtn.user?.is_staff) {
        rtn.users = await get_data_or_404('users');
    }

    rtn.attendees = await get_data_or_404_event('attendees?all=true');
    rtn.questions = await get_data_or_404_event('questions');
    rtn.speakers = await get_data_or_404_event('speakers');
    rtn.reviewers = await get_data_or_404_event('reviewers');
    rtn.abstracts = await get_data_or_404_event('abstracts');
    rtn.organizers = await get_data_or_404_event('organizers');
    rtn.eventadmins = await get_data_or_404_event('eventadmins');
    rtn.email_templates = await get_data_or_404_event('email_templates');
    rtn.onsite_attendees = await get_data_or_404_event('onsite');
    rtn.payments = await get_data_or_404_event('payments');

    return rtn;
}

/** @type {import('./$types').Actions} */
export const actions = {
    search_institutions: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const search = formdata.get('search') || '';

        const response = await get(`api/institutions?search=${encodeURIComponent(search)}`, cookies);
        if (response.ok) {
            return { success: true, institutions: response.data };
        } else {
            return { success: false, institutions: [] };
        }
    },
    create_institution: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            name_en: formdata.get('name_en'),
            name_ko: formdata.get('name_ko') || ''
        };
        const response = await post('api/institutions', data, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, institution: response.data };
        } else {
            throw error(response.status, response.data);
        }
    },
    toggle_published: async ({ cookies, params, request }) => {
        const response = await post(`api/event/${params.slug}/toggle_published`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_event: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/update`, formdata, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },  
    update_email_templates: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/emailtemplates`, {
            email_template_registration_subject: formdata.get('email_template_registration_subject'),
            email_template_registration_body: formdata.get('email_template_registration_body'),
            email_template_abstract_submission_subject: formdata.get('email_template_abstract_submission_subject'),
            email_template_abstract_submission_body: formdata.get('email_template_abstract_submission_body'),
            email_template_certificate_subject: formdata.get('email_template_certificate_subject'),
            email_template_certificate_body: formdata.get('email_template_certificate_body'),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_questions: async ({ cookies, params, request }) => {
        let formdata = await request.formData();

        // convert formdata to json
        let questions = [];
        for (let i = 0; i < formdata.getAll('question_id[]').length; i++) {
            let question = {
                type: formdata.getAll('question_type[]')[i],
                question: formdata.getAll('question_question[]')[i],
            };
            if (question.type === 'checkbox' || question.type === 'select') {
                question.options = formdata.getAll('question_options[]')[i].split('\n');
            }
            questions.push({
                id: parseInt(formdata.getAll('question_id[]')[i]),
                question: question,
            });
        }

        const response = await post(`api/event/${params.slug}/questions`, { questions }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    add_speaker: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/speaker/add`, {
            name: formdata.get('name'),
            korean_name: formdata.get('korean_name') || '',
            email: formdata.get('email'),
            affiliation: formdata.get('affiliation'),
            affiliation_ko: formdata.get('affiliation_ko') || '',
            is_domestic: formdata.get('is_domestic') === 'true',
            type: formdata.get('type'),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_speaker: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/speaker/${formdata.get('id')}/update`, {
            name: formdata.get('name'),
            korean_name: formdata.get('korean_name') || '',
            email: formdata.get('email'),
            affiliation: formdata.get('affiliation'),
            affiliation_ko: formdata.get('affiliation_ko') || '',
            is_domestic: formdata.get('is_domestic') === 'true',
            type: formdata.get('type'),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    remove_speaker: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/speaker/${formdata.get('id')}/delete`, {
            id: parseInt(formdata.get('id'))
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_attendee: async ({ cookies, params, request }) => {
        let formdata = await request.formData();

        const response = await post(`api/event/${params.slug}/attendee/${parseInt(formdata.get('id'))}/update`, {
            first_name: formdata.get('first_name'),
            middle_initial: formdata.get('middle_initial'),
            last_name: formdata.get('last_name'),
            korean_name: formdata.get('korean_name'),
            nationality: formdata.get('nationality'),
            institute: formdata.get('institute'),
            department: formdata.get('department'),
            job_title: formdata.get('job_title'),
            disability: formdata.get('disability'),
            dietary: formdata.get('dietary'),
        }, cookies);

        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    toggle_attended: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/attendee/${parseInt(formdata.get('id'))}/update`, {
            is_attended: formdata.get('is_attended') === 'true',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_answers: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        let answers = [];
        for (let i = 0; i < formdata.getAll('answer_reference_id[]').length; i++) {
            answers.push({
                reference_id: parseInt(formdata.getAll('answer_reference_id[]')[i]),
                question: formdata.getAll('answer_question[]')[i],
                answer: formdata.getAll('answer_answer[]')[i],
            });
        }
        const response = await post(`api/event/${params.slug}/attendee/${formdata.get('attendee_id')}/answers`, {
            answers: answers,
        }, cookies);

        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    deregister_attendee: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/attendee/${formdata.get('id')}/deregister`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    send_emails: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/send_emails`, {
            to: formdata.get('to'),
            cc: formdata.get('cc') || '',
            subject: formdata.get('subject'),
            body: formdata.get('body'),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    add_reviewer: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/reviewer/add`, {
            id: parseInt(formdata.get('id')),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    delete_reviewer: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/reviewer/${formdata.get('id')}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    get_abstract: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await get(`api/event/${params.slug}/abstract/${formdata.get('id')}`, cookies);
        if (response.ok && response.status === 200) {
            return JSON.stringify(response.data);
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_abstract: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/abstract/${formdata.get('id')}/update`, {
            title: formdata.get('title'),
            type: formdata.get('type'),
            wants_short_talk: formdata.get('wants_short_talk') === 'true',
        }, cookies);
        if (response.ok && response.status === 200) {
            return JSON.stringify(response.data);
        } else {
            error(response.status, response.data);
        }
        return;
    },
    delete_abstract: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/abstract/${formdata.get('id')}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return JSON.stringify(response.data);
        } else {
            error(response.status, response.data);
        }
        return;
    },
    add_eventadmin: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/eventadmin/add`, {
            id: parseInt(formdata.get('id')),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    delete_eventadmin: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/eventadmin/${formdata.get('id')}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    set_main_eventadmin: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/eventadmin/${formdata.get('id')}/set_main`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    add_organizer: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/organizer/add`, {
            name: formdata.get('name'),
            korean_name: formdata.get('korean_name') || '',
            email: formdata.get('email') || '',
            affiliation: formdata.get('affiliation') || '',
            affiliation_ko: formdata.get('affiliation_ko') || '',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_organizer: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/organizer/${formdata.get('id')}/update`, {
            name: formdata.get('name'),
            korean_name: formdata.get('korean_name') || '',
            email: formdata.get('email') || '',
            affiliation: formdata.get('affiliation') || '',
            affiliation_ko: formdata.get('affiliation_ko') || '',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    delete_organizer: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/organizer/${formdata.get('id')}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    reorder_organizers: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const order = JSON.parse(formdata.get('order') || '[]');
        const response = await post(`api/event/${params.slug}/organizers/reorder`, { order }, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, ...response.data };
        } else {
            return { success: false, error: response.data?.message || 'Failed to reorder organizers' };
        }
    },
    update_onsite_attendee: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/onsite/${formdata.get('id')}/update`, {
            name: formdata.get('name'),
            email: formdata.get('email'),
            institute: formdata.get('institute'),
            job_title: formdata.get('job_title'),
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    confirm_onsite_attendee: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/onsite/${formdata.get('id')}/update`, {
            is_confirmed: formdata.get('is_confirmed') === 'true',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    remove_onsite_attendee: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/onsite/${formdata.get('id')}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    send_certificate: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/send_certificate`, {
            email: formdata.get('email'),
            pdf_base64: formdata.get('pdf_base64'),
            attendee_id: formdata.get('attendee_id') ? parseInt(formdata.get('attendee_id')) : null,
            attendee_type: formdata.get('attendee_type') || 'attendee',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    create_payment: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const attendee_id = parseInt(formdata.get('attendee_id'));
        if (isNaN(attendee_id)) {
            error(400, { message: 'Attendee is required' });
        }
        const data = {
            attendee_id,
            amount: parseInt(formdata.get('amount')) || 0,
            order_id: generateOrderId(),
            payment_type: formdata.get('payment_type'),
            note: formdata.get('note') || '',
            // Common fields for all payment types
            supply_amount: parseInt(formdata.get('supply_amount')) || 0,
            vat: parseInt(formdata.get('vat')) || 0,
        };
        // Add card transaction fields if payment type is card
        if (data.payment_type === 'card') {
            data.card_type = formdata.get('card_type') || '';
            data.card_number = formdata.get('card_number') || '';
            data.approval_number = formdata.get('approval_number') || '';
            data.installment = formdata.get('installment') || 'single';
        }
        // Add transfer-specific fields
        if (data.payment_type === 'transfer') {
            data.transaction_datetime = formdata.get('transaction_datetime') || '';
            data.transaction_description = formdata.get('transaction_description') || '';
        }
        const response = await post(`api/event/${params.slug}/payment/add`, data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    cancel_payment: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/payment/${formdata.get('id')}/cancel`, {
            cancel_reason: formdata.get('cancel_reason') || '관리자 취소',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    update_payment_note: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/payment/${formdata.get('id')}/note`, {
            note: formdata.get('note') || '',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    save_nametag_settings: async ({ cookies, params, request }) => {
        let formdata = await request.formData();
        const response = await post(`api/event/${params.slug}/nametag_settings`, {
            nametag_paper_width: parseInt(formdata.get('nametag_paper_width')) || 90,
            nametag_paper_height: parseInt(formdata.get('nametag_paper_height')) || 100,
            nametag_orientation: formdata.get('nametag_orientation') || 'portrait',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    },
    upload_editor_file: async ({ cookies, request }) => {
        let formdata = await request.formData();
        const response = await post('api/upload/editor-file', {
            file_name: formdata.get('file_name'),
            file_content: formdata.get('file_content'),
            file_type: formdata.get('file_type') || 'image',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            error(response.status, response.data);
        }
        return;
    }
};