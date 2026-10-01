/**
 * Toss Payments Integration
 * Reference: https://docs.tosspayments.com/sdk/v2/js
 */

import { loadTossPayments } from '@tosspayments/tosspayments-sdk';

let tossPaymentsInstance = null;

/**
 * Get Toss client key from environment
 * @returns {string} Toss client key
 */
function getClientKey() {
    const clientKey = import.meta.env.TOSS_CLIENT_KEY;
    if (!clientKey) {
        throw new Error('TOSS_CLIENT_KEY is not configured');
    }
    return clientKey;
}

/**
 * Initialize Toss Payments SDK
 * @returns {Promise<TossPayments>} Toss Payments instance
 */
export async function initTossPayments() {
    if (!tossPaymentsInstance) {
        tossPaymentsInstance = await loadTossPayments(getClientKey());
    }
    return tossPaymentsInstance;
}

/**
 * Request a card payment
 * @param {Object} options - Payment options
 * @param {string} options.customerKey - Unique customer identifier (user ID or anonymous)
 * @param {number} options.amount - Payment amount in KRW
 * @param {string} options.orderId - Unique order ID
 * @param {string} options.orderName - Order description
 * @param {string} options.successUrl - Redirect URL on success
 * @param {string} options.failUrl - Redirect URL on failure
 * @param {string} [options.customerEmail] - Customer email
 * @param {string} [options.customerName] - Customer name
 * @param {string} [options.customerMobilePhone] - Customer phone number
 * @returns {Promise<void>}
 */
export async function requestCardPayment(options) {
    const tossPayments = await initTossPayments();

    const payment = tossPayments.payment({
        customerKey: options.customerKey,
    });

    await payment.requestPayment({
        method: 'CARD',
        amount: {
            currency: 'KRW',
            value: options.amount,
        },
        orderId: options.orderId,
        orderName: options.orderName,
        successUrl: options.successUrl,
        failUrl: options.failUrl,
        customerEmail: options.customerEmail,
        customerName: options.customerName,
        customerMobilePhone: options.customerMobilePhone,
        card: {
            useEscrow: false,
            flowMode: 'DEFAULT',
            useCardPoint: false,
            useAppCardOnly: false,
        },
    });
}

/**
 * Request an anonymous card payment (for non-logged-in users)
 * @param {Object} options - Payment options (same as requestCardPayment but without customerKey)
 * @returns {Promise<void>}
 */
export async function requestAnonymousCardPayment(options) {
    const tossPayments = await initTossPayments();

    const payment = tossPayments.payment({
        customerKey: tossPayments.ANONYMOUS,
    });

    await payment.requestPayment({
        method: 'CARD',
        amount: {
            currency: 'KRW',
            value: options.amount,
        },
        orderId: options.orderId,
        orderName: options.orderName,
        successUrl: options.successUrl,
        failUrl: options.failUrl,
        customerEmail: options.customerEmail,
        customerName: options.customerName,
        customerMobilePhone: options.customerMobilePhone,
        card: {
            useEscrow: false,
            flowMode: 'DEFAULT',
            useCardPoint: false,
            useAppCardOnly: false,
        },
    });
}

/**
 * Confirm payment on the server side
 * This should be called from the success callback page
 * @param {Object} params - Payment confirmation parameters from URL
 * @param {string} params.paymentKey - Payment key from Toss
 * @param {string} params.orderId - Order ID
 * @param {number} params.amount - Payment amount
 * @returns {Promise<Object>} Confirmed payment response
 */
export async function confirmPayment(params) {
    const response = await fetch('/api/payment/confirm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            paymentKey: params.paymentKey,
            orderId: params.orderId,
            amount: params.amount,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw Object.assign(new Error(error.message || 'Payment confirmation failed'), { code: error.code });
    }

    return response.json();
}
