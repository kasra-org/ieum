/**
 * NicePay (나이스페이) authenticated payment integration.
 * Reference: https://developers.nicepay.co.kr/manual-auth.php
 *
 * The payment window is opened by handing a form object to the global goPay()
 * provided by nicepay-pgweb.js. All parameters - including the SignData hash -
 * are produced by the backend, because signing requires the merchant key.
 *
 * On PC the window is a layer popup: once the payer authenticates, NicePay
 * appends the authentication result to our form and calls nicepaySubmit(),
 * which submits the form to its action (our backend callback). On mobile the
 * browser navigates away and NicePay POSTs the result to ReturnURL instead.
 * Either way the backend approves the payment and redirects to /payment/success
 * or /payment/fail, so this module never sees the result.
 */

const FORM_ID = 'nicepay-payment-form';

let sdkPromise = null;

/**
 * Load nicepay-pgweb.js once, exposing the global goPay().
 * @param {string} src - SDK URL supplied by the backend
 * @returns {Promise<void>}
 */
function loadSdk(src) {
    if (typeof window === 'undefined') {
        return Promise.reject(new Error('NicePay can only be loaded in the browser'));
    }
    if (window.goPay) return Promise.resolve();
    if (sdkPromise) return sdkPromise;

    sdkPromise = new Promise((resolve, reject) => {
        const existing = document.querySelector(`script[src="${src}"]`);
        if (existing) {
            existing.addEventListener('load', () => resolve());
            existing.addEventListener('error', () => reject(new Error('Failed to load the NicePay SDK')));
            return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => {
            sdkPromise = null;
            reject(new Error('Failed to load the NicePay SDK'));
        };
        document.head.appendChild(script);
    });

    return sdkPromise;
}

/**
 * Build (or rebuild) the hidden form goPay() operates on.
 *
 * The payment window is euc-kr, so the form declares accept-charset="euc-kr"
 * to make the browser encode Korean values (product name, buyer name) the way
 * NicePay expects.
 *
 * @param {Object} params - form fields from the backend
 * @param {string} action - URL the authentication result is submitted to
 * @returns {HTMLFormElement}
 */
function buildForm(params, action) {
    document.getElementById(FORM_ID)?.remove();

    const form = document.createElement('form');
    form.id = FORM_ID;
    form.name = FORM_ID;
    form.method = 'POST';
    form.action = action;
    form.acceptCharset = 'euc-kr';
    form.style.display = 'none';

    for (const [name, value] of Object.entries(params)) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value ?? '';
        form.appendChild(input);
    }

    document.body.appendChild(form);
    return form;
}

/**
 * Ask the backend to prepare a payment and open the NicePay payment window.
 *
 * Resolves once the window has been opened. The payment outcome is delivered
 * by a full-page redirect from the backend, not by this promise.
 *
 * @param {Object} options
 * @param {number} options.eventId - Event being paid for
 * @param {string} [options.payMethod] - CARD | BANK | VBANK | CELLPHONE
 * @param {Function} [options.onClose] - Called if the payer closes the window
 * @returns {Promise<void>}
 */
export async function requestNicePayPayment(options) {
    const response = await fetch('/api/payment/nicepay/prepare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            eventId: options.eventId,
            payMethod: options.payMethod || 'CARD',
        }),
    });

    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(result.message || 'Could not start the payment');
    }

    await loadSdk(result.jsSdkUrl);

    // The result is POSTed to the same backend endpoint in both flows: as the
    // form action on PC, and as ReturnURL on mobile.
    const form = buildForm(result.params, result.returnUrl);

    // NicePay calls these globals back from the payment window.
    window.nicepaySubmit = () => form.submit();
    window.nicepayClose = () => {
        if (typeof options.onClose === 'function') options.onClose();
    };

    if (typeof window.goPay !== 'function') {
        throw new Error('The NicePay SDK did not load correctly');
    }
    window.goPay(form);
}
