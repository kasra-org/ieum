import { env } from '$env/dynamic/private';

const BASE_URL = env.API_BASE_URL || 'http://backend:8080/';

async function send({ method, path, data, cookies, extraHeaders }) {
    const url = new URL(path, BASE_URL);

    let headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(extraHeaders ?? {}),
    }

    if (cookies) {
        let cookie_strings = [];
        cookies.getAll().forEach(cookie => {
            cookie_strings.push(`${cookie.name}=${cookie.value}`);
            if (cookie.name === 'csrftoken') {
                headers['X-CSRFToken'] = cookie.value;
            }
        });
        headers['Cookie'] = cookie_strings.join('; ');
    }

    const options = {
        method,
        headers,
    };

    if (data) {
        if (data.forEach) {
            // data is a FormData object
            var object = {};
            data.forEach((value, key) => object[key] = value);
            options.body = JSON.stringify(object);
        } else if (typeof data === 'object') {
            // data is an object
            options.body = JSON.stringify(data);
        }
    }

    try {
        const response = await fetch(url, options);
        const contentType = response.headers.get('content-type');
        
        let responseData;
        if (contentType && contentType.includes('application/json')) {
            responseData = await response.json();
        } else {
            responseData = await response.text();
        }

        let sessionid = null;
        if (response.headers.has('set-cookie')) {
            // parse the set-cookie header, find the sessionid cookie using a regex (sessionid=.*?;)
            // and extract the value
            const cookie = response.headers.get('set-cookie');
            const match = cookie.match(/sessionid=([0-9a-z]+?);/);
            if (match) {
                sessionid = match[1];
            }
        }

        return { ok: response.ok, status: response.status, data: responseData, sessionid: sessionid };
    } catch (error) {
        console.error('Fetch error:', error);
        return { ok: false, error: error.message };
    }
}

export function get(path, cookies, extraHeaders) {
    return send({ method: 'GET', path, cookies, extraHeaders });
}

export function del(path, cookies) {
    return send({ method: 'DELETE', path, cookies });
}

export function post(path, data, cookies, extraHeaders) {
    return send({ method: 'POST', path, data, cookies, extraHeaders });
}

export function put(path, data, cookies) {
    return send({ method: 'PUT', path, data, cookies });
}

export function patch(path, data, cookies) {
    return send({ method: 'PATCH', path, data, cookies });
}