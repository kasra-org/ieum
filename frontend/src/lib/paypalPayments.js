/**
 * PayPal Payments Integration
 * Reference: https://developer.paypal.com/docs/checkout/standard/
 */

import { deserialize } from '$app/forms';

let paypalScriptLoaded = false;
let paypalScriptLoading = false;
let paypalScriptCallbacks = [];

/**
 * Get PayPal client ID from environment
 * @returns {string} PayPal client ID
 */
function getClientId() {
    const clientId = import.meta.env.PAYPAL_CLIENT_ID;
    if (!clientId) {
        throw new Error('PAYPAL_CLIENT_ID is not configured');
    }
    return clientId;
}

/**
 * Load PayPal SDK script dynamically
 * @returns {Promise<void>}
 */
export function loadPayPalScript() {
    return new Promise((resolve, reject) => {
        if (paypalScriptLoaded) {
            resolve();
            return;
        }

        if (paypalScriptLoading) {
            paypalScriptCallbacks.push({ resolve, reject });
            return;
        }

        paypalScriptLoading = true;

        const script = document.createElement('script');
        script.src = `https://www.paypal.com/sdk/js?client-id=${getClientId()}&currency=USD`;
        script.async = true;

        script.onload = () => {
            paypalScriptLoaded = true;
            paypalScriptLoading = false;
            resolve();
            paypalScriptCallbacks.forEach(cb => cb.resolve());
            paypalScriptCallbacks = [];
        };

        script.onerror = (error) => {
            paypalScriptLoading = false;
            reject(new Error('Failed to load PayPal SDK'));
            paypalScriptCallbacks.forEach(cb => cb.reject(error));
            paypalScriptCallbacks = [];
        };

        document.head.appendChild(script);
    });
}

/**
 * Create a PayPal order via form action
 * @param {Object} options - Order options
 * @param {number} options.amount - Payment amount in KRW
 * @param {string} options.actionUrl - The form action URL (e.g., '?/paypal_create_order')
 * @returns {Promise<string>} PayPal order ID
 */
export async function createPayPalOrder(options) {
    const formData = new FormData();
    formData.append('amount', options.amount.toString());

    const response = await fetch(options.actionUrl || '?/paypal_create_order', {
        method: 'POST',
        body: formData,
    });

    const result = deserialize(await response.text());

    if (result.type !== 'success' || !result.data?.success) {
        throw Object.assign(new Error(result.data?.error || 'Failed to create PayPal order'), { code: result.data?.code || 'paypal_error' });
    }

    return result.data.orderId;
}

/**
 * Capture a PayPal order after approval via form action
 * @param {Object} options - Capture options
 * @param {string} options.orderId - PayPal order ID
 * @param {string} options.actionUrl - The form action URL (e.g., '?/paypal_capture_order')
 * @returns {Promise<Object>} Payment result
 */
export async function capturePayPalOrder(options) {
    const formData = new FormData();
    formData.append('orderId', options.orderId);

    const response = await fetch(options.actionUrl || '?/paypal_capture_order', {
        method: 'POST',
        body: formData,
    });

    const result = deserialize(await response.text());

    if (result.type !== 'success' || !result.data?.success) {
        throw Object.assign(new Error(result.data?.error || 'Failed to capture PayPal payment'), { code: result.data?.code || 'paypal_error' });
    }

    return result.data.data;
}

/**
 * Render PayPal buttons
 * @param {Object} options - Button options
 * @param {string} options.containerId - ID of the container element
 * @param {number} options.amount - Payment amount in KRW
 * @param {function} options.onSuccess - Success callback
 * @param {function} options.onError - Error callback
 * @param {function} options.onCancel - Cancel callback
 * @returns {Promise<void>}
 */
export async function renderPayPalButtons(options) {
    await loadPayPalScript();

    if (!window.paypal) {
        throw new Error('PayPal SDK not available');
    }

    window.paypal.Buttons({
        style: {
            layout: 'vertical',
            color: 'blue',
            shape: 'rect',
            label: 'paypal',
        },
        createOrder: async () => {
            try {
                const orderId = await createPayPalOrder({
                    amount: options.amount,
                });
                return orderId;
            } catch (error) {
                options.onError?.(error);
                throw error;
            }
        },
        onApprove: async (data) => {
            try {
                const result = await capturePayPalOrder({
                    orderId: data.orderID,
                });
                options.onSuccess?.(result);
            } catch (error) {
                options.onError?.(error);
            }
        },
        onCancel: () => {
            options.onCancel?.();
        },
        onError: (error) => {
            console.error('PayPal error:', error);
            options.onError?.(error);
        },
    }).render(`#${options.containerId}`);
}
