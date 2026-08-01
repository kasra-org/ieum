import { get, post } from '$lib/fetch';
import { error, redirect } from '@sveltejs/kit';

const ADMIN_PAGE_NAME = process.env.ADMIN_PAGE_NAME || '/admin';

/** @type {import('./$types').PageServerLoad} */
export async function load({ parent, params, cookies }) {
    let data = await parent();
    let admin_page_name = params.admin_page_name;
    if (admin_page_name !== ADMIN_PAGE_NAME) {
        throw error(404, 'Not Found');
    }
    
    const get_data_or_404 = async (item) => {
        const response = await get(`api/admin/${item}`, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(404, "Not Found");
        }
    };

    data.admin = {
        events: await get_data_or_404('events'),
        users: await get_data_or_404('users'),
        institutions: await get_data_or_404('institutions')
    };

    // API keys are superuser-only; a non-superuser admin simply sees no panel.
    const apiKeysResponse = await get('api/admin/apikeys', cookies);
    data.admin.apiKeys = (apiKeysResponse.ok && apiKeysResponse.status === 200)
        ? apiKeysResponse.data : null;

    // Load site settings (public endpoint, doesn't require admin auth)
    const siteSettingsResponse = await get('api/site-settings', cookies);
    if (siteSettingsResponse.ok && siteSettingsResponse.status === 200) {
        data.admin.siteSettings = siteSettingsResponse.data;
    } else {
        data.admin.siteSettings = {
            site_name: 'IEUM',
            site_description: '',
            site_keywords: ''
        };
    }

    // Load payment settings (public endpoint, doesn't require admin auth)
    const paymentSettingsResponse = await get('api/payment-settings', cookies);
    data.admin.paymentSettings = (paymentSettingsResponse.ok && paymentSettingsResponse.status === 200)
        ? paymentSettingsResponse.data
        : { domestic_provider: 'toss', international_provider: 'paypal' };

    // Load business settings (public endpoint, doesn't require admin auth)
    const businessSettingsResponse = await get('api/business-settings', cookies);
    if (businessSettingsResponse.ok && businessSettingsResponse.status === 200) {
        data.admin.businessSettings = businessSettingsResponse.data;
    } else {
        data.admin.businessSettings = {
            business_name: '',
            business_registration_number: '',
            address: '',
            representative: '',
            phone: '',
            email: ''
        };
    }

    // Load account settings (admin only)
    const accountSettingsResponse = await get('api/admin/account-settings', cookies);
    if (accountSettingsResponse.ok && accountSettingsResponse.status === 200) {
        data.admin.accountSettings = accountSettingsResponse.data;
    } else {
        data.admin.accountSettings = {
            account_deletion_period: 3 * 365,
            account_warning_period: 7,
            attendee_retention_years: 5,
            payment_retention_years: 5,
            minimum_retention_years: 5
        };
    }

    // Load privacy policy (admin only)
    const privacyPolicyResponse = await get('api/admin/privacy-policy', cookies);
    if (privacyPolicyResponse.ok && privacyPolicyResponse.status === 200) {
        data.admin.privacyPolicy = privacyPolicyResponse.data;
    } else {
        data.admin.privacyPolicy = {
            content_en: '',
            content_ko: ''
        };
    }

    // Load terms of service (admin only)
    const termsOfServiceResponse = await get('api/admin/terms-of-service', cookies);
    if (termsOfServiceResponse.ok && termsOfServiceResponse.status === 200) {
        data.admin.termsOfService = termsOfServiceResponse.data;
    } else {
        data.admin.termsOfService = {
            content_en: '',
            content_ko: ''
        };
    }

    return data;
}

/** @type {import('./$types').PageServerActions} */
export const actions = {
    'create_api_key': async ({ cookies, request }) => {
        const formdata = await request.formData();
        const response = await post('api/admin/apikey/add', {
            name: formdata.get('name'),
            user_id: parseInt(formdata.get('user_id'))
        }, cookies);
        // On success the backend returns the plaintext secret in `message`;
        // it is shown once and never retrievable again.
        return response.ok
            ? { success: true, secret: response.data.message }
            : { success: false, error: response.data?.message || 'Failed to create key' };
    },
    'rotate_api_key': async ({ cookies, request }) => {
        const formdata = await request.formData();
        const response = await post(`api/admin/apikey/${formdata.get('key_id')}/rotate`, {}, cookies);
        return response.ok
            ? { success: true, secret: response.data.message }
            : { success: false, error: response.data?.message || 'Failed to rotate key' };
    },
    'revoke_api_key': async ({ cookies, request }) => {
        const formdata = await request.formData();
        const response = await post(`api/admin/apikey/${formdata.get('key_id')}/revoke`,
            { revoked: formdata.get('revoked') === 'true' }, cookies);
        return { success: response.ok };
    },
    'delete_api_key': async ({ cookies, request }) => {
        const formdata = await request.formData();
        const response = await post(`api/admin/apikey/${formdata.get('key_id')}/delete`, {}, cookies);
        return { success: response.ok };
    },
    'search_institutions': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const search = formdata.get('search') || '';

        const response = await get(`api/institutions?search=${encodeURIComponent(search)}`, cookies);
        if (response.ok) {
            return { success: true, institutions: response.data };
        } else {
            return { success: false, institutions: [] };
        }
    },
    'create_event': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const response = await post('api/admin/event/add', formdata, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'archive_event': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let id = formdata.get('id');
        const response = await post(`api/admin/event/${id}/archive`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'toggle_user_active': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let user_id = formdata.get('user_id');
        const response = await post(`api/admin/user/${user_id}/toggle-active`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'toggle_user_verified': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let user_id = formdata.get('user_id');
        const response = await post(`api/admin/user/${user_id}/toggle-verified`, {}, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'create_institution': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            name_en: formdata.get('name_en'),
            name_ko: formdata.get('name_ko') || ''
        };
        const response = await post('api/institutions', data, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, institution: response.data };
        } else {
            return { success: false, error: response.data?.error || 'Failed to create institution' };
        }
    },
    'update_institution': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let id = formdata.get('id');
        const data = {
            name_en: formdata.get('name_en'),
            name_ko: formdata.get('name_ko') || ''
        };
        const response = await post(`api/admin/institution/${id}/update`, data, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, ...response.data };
        } else {
            return { success: false, error: response.data?.message || 'Failed to update institution' };
        }
    },
    'delete_institution': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let id = formdata.get('id');
        const response = await post(`api/admin/institution/${id}/delete`, {}, cookies);
        if (response.ok && response.status === 200) {
            return { success: true, ...response.data };
        } else {
            return { success: false, error: response.data?.message || 'Failed to delete institution' };
        }
    },
    'update_user': async ({ cookies, request }) => {
        let formdata = await request.formData();
        let user_id = formdata.get('user_id');

        // Convert FormData to JSON object
        const data = {};
        for (const [key, value] of formdata.entries()) {
            if (key !== 'user_id') {
                data[key] = value;
            }
        }

        const response = await post(`api/admin/user/${user_id}/update`, data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_site_settings': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            site_name: formdata.get('site_name') || 'IEUM',
            site_description: formdata.get('site_description') || '',
            site_keywords: formdata.get('site_keywords') || ''
        };
        const response = await post('api/admin/site-settings', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'add_guest_user': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const institute = formdata.get('institute');
        const response = await post('api/admin/user/guest/add', {
            email: formdata.get('email'),
            password: formdata.get('password'),
            first_name: formdata.get('first_name'),
            last_name: formdata.get('last_name'),
            korean_name: formdata.get('korean_name') || '',
            job_title: formdata.get('job_title') || 'Guest',
            institute: institute ? parseInt(institute, 10) : null,
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_payment_settings': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            domestic_provider: formdata.get('domestic_provider') || 'toss',
            international_provider: formdata.get('international_provider') || 'paypal'
        };
        const response = await post('api/admin/payment-settings', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_business_settings': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            business_name: formdata.get('business_name') || '',
            business_registration_number: formdata.get('business_registration_number') || '',
            address: formdata.get('address') || '',
            representative: formdata.get('representative') || '',
            phone: formdata.get('phone') || '',
            email: formdata.get('email') || '',
            timezone: formdata.get('timezone') || 'Asia/Seoul',
            business_name_en: formdata.get('business_name_en') || '',
            address_en: formdata.get('address_en') || '',
            representative_en: formdata.get('representative_en') || ''
        };
        const response = await post('api/admin/business-settings', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_account_settings': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            account_deletion_period: parseInt(formdata.get('account_deletion_period')) || 3 * 365,
            account_warning_period: parseInt(formdata.get('account_warning_period')) || 7,
            attendee_retention_years: parseInt(formdata.get('attendee_retention_years')) || 5,
            payment_retention_years: parseInt(formdata.get('payment_retention_years')) || 5
        };
        const response = await post('api/admin/account-settings', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_privacy_policy': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            content_en: formdata.get('content_en') || '',
            content_ko: formdata.get('content_ko') || ''
        };
        const response = await post('api/admin/privacy-policy', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'update_terms_of_service': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const data = {
            content_en: formdata.get('content_en') || '',
            content_ko: formdata.get('content_ko') || ''
        };
        const response = await post('api/admin/terms-of-service', data, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    },
    'upload_editor_file': async ({ cookies, request }) => {
        let formdata = await request.formData();
        const response = await post('api/upload/editor-file', {
            file_name: formdata.get('file_name'),
            file_content: formdata.get('file_content'),
            file_type: formdata.get('file_type') || 'image',
        }, cookies);
        if (response.ok && response.status === 200) {
            return response.data;
        } else {
            throw error(response.status, response.data);
        }
    }
};