/*
 * CCS Request Manager
 * Shared AJAX/request helper for CCS web applications.
 *
 * Goals:
 * - Add Django CSRF headers automatically.
 * - Normalize JSON/FormData/plain requests.
 * - Normalize success/error handling.
 * - Keep future Time Reporting and JobGrid AJAX calls consistent.
 */
(function (window, document) {
  'use strict';

  const CCS = window.CCS;

  if (!CCS) {
    throw new Error('CCS core must be loaded before request.js');
  }

  class RequestError extends Error {
    constructor(message, details) {
      super(message || 'Request failed.');
      this.name = 'CCSRequestError';
      Object.assign(this, details || {});
    }
  }

  function isPlainObject(value) {
    return Object.prototype.toString.call(value) === '[object Object]';
  }

  function mergeHeaders(baseHeaders, extraHeaders) {
    const headers = new Headers(baseHeaders || {});

    if (extraHeaders) {
      new Headers(extraHeaders).forEach(function (value, key) {
        headers.set(key, value);
      });
    }

    return headers;
  }

  function shouldParseJson(response) {
    const contentType = response.headers.get('content-type') || '';
    return contentType.toLowerCase().includes('application/json');
  }

  async function parseResponse(response) {
    if (response.status === 204) {
      return null;
    }

    if (shouldParseJson(response)) {
      return response.json();
    }

    return response.text();
  }

  function normalizeArgs(urlOrOptions, options) {
    if (typeof urlOrOptions === 'string') {
      return Object.assign({}, options || {}, { url: urlOrOptions });
    }

    return Object.assign({}, urlOrOptions || {});
  }

  function buildFetchOptions(settings) {
    const method = (settings.method || 'GET').toUpperCase();
    const headers = mergeHeaders({
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json, text/plain, */*',
    }, settings.headers);

    const csrfToken = CCS.getCsrfToken ? CCS.getCsrfToken() : '';
    if (csrfToken && !headers.has('X-CSRFToken')) {
      headers.set('X-CSRFToken', csrfToken);
    }

    const fetchOptions = {
      method: method,
      credentials: settings.credentials || 'same-origin',
      headers: headers,
    };

    if (settings.signal) {
      fetchOptions.signal = settings.signal;
    }

    const body = settings.body !== undefined ? settings.body : settings.data;

    if (body !== undefined && body !== null && method !== 'GET' && method !== 'HEAD') {
      if (body instanceof FormData || body instanceof URLSearchParams || typeof body === 'string') {
        fetchOptions.body = body;
      } else if (isPlainObject(body) || Array.isArray(body)) {
        if (!headers.has('Content-Type')) {
          headers.set('Content-Type', 'application/json');
        }
        fetchOptions.body = JSON.stringify(body);
      } else {
        fetchOptions.body = body;
      }
    }

    return fetchOptions;
  }

  function defaultErrorMessage(error) {
    if (error && error.data && isPlainObject(error.data)) {
      return error.data.error || error.data.message || error.message;
    }

    return error && error.message ? error.message : 'Request failed.';
  }

  async function request(urlOrOptions, options) {
    const settings = Object.assign({
      method: 'GET',
      toastErrors: false,
      throwOnError: true,
    }, normalizeArgs(urlOrOptions, options));

    if (!settings.url) {
      throw new Error('CCS.request requires a URL.');
    }

    if (typeof settings.onStart === 'function') {
      settings.onStart(settings);
    }

    const startedAt = window.performance && performance.now ? performance.now() : Date.now();

    try {
      const response = await window.fetch(settings.url, buildFetchOptions(settings));
      const data = await parseResponse(response);
      const elapsedMs = Math.round((window.performance && performance.now ? performance.now() : Date.now()) - startedAt);

      const result = {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        data: data,
        response: response,
        elapsedMs: elapsedMs,
      };

      if (!response.ok) {
        const message = (isPlainObject(data) && (data.error || data.message)) || response.statusText || 'Request failed.';
        const error = new RequestError(message, result);

        if (settings.toastErrors && CCS.toast && typeof CCS.toast.error === 'function') {
          CCS.toast.error(defaultErrorMessage(error));
        }

        if (settings.throwOnError) {
          throw error;
        }
      }

      return result;
    } catch (error) {
      if (!(error instanceof RequestError)) {
        const wrapped = new RequestError(error.message || 'Network request failed.', {
          originalError: error,
          status: 0,
          ok: false,
        });

        if (settings.toastErrors && CCS.toast && typeof CCS.toast.error === 'function') {
          CCS.toast.error(defaultErrorMessage(wrapped));
        }

        if (settings.throwOnError) {
          throw wrapped;
        }

        return wrapped;
      }

      throw error;
    } finally {
      if (typeof settings.onFinish === 'function') {
        settings.onFinish(settings);
      }
    }
  }

  request.get = function (url, options) {
    return request(url, Object.assign({}, options || {}, { method: 'GET' }));
  };

  request.post = function (url, data, options) {
    return request(url, Object.assign({}, options || {}, { method: 'POST', data: data }));
  };

  request.put = function (url, data, options) {
    return request(url, Object.assign({}, options || {}, { method: 'PUT', data: data }));
  };

  request.patch = function (url, data, options) {
    return request(url, Object.assign({}, options || {}, { method: 'PATCH', data: data }));
  };

  request.delete = function (url, options) {
    return request(url, Object.assign({}, options || {}, { method: 'DELETE' }));
  };

  request.RequestError = RequestError;

  CCS.register('request', request);
})(window, document);
