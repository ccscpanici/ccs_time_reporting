/*
 * CCS Toast Notifications
 * Reusable lightweight notifications for CCS web applications.
 */
(function (window, document) {
  'use strict';

  const CCS = window.CCS;

  if (!CCS) {
    throw new Error('CCS core must be loaded before toast.js');
  }

  const DEFAULT_TIMEOUT = 4000;
  let container = null;

  function getContainer() {
    if (container) {
      return container;
    }

    container = document.querySelector('[data-ccs-toast-container]');

    if (!container) {
      container = document.createElement('div');
      container.className = 'ccs-toast-container';
      container.setAttribute('data-ccs-toast-container', '');
      container.setAttribute('aria-live', 'polite');
      container.setAttribute('aria-atomic', 'true');
      document.body.appendChild(container);
    }

    return container;
  }

  function normalizeOptions(options) {
    if (typeof options === 'number') {
      return { timeout: options };
    }

    return options || {};
  }

  function show(message, options) {
    const settings = Object.assign({
      type: 'info',
      timeout: DEFAULT_TIMEOUT,
      dismissible: true,
    }, normalizeOptions(options));

    const toast = document.createElement('div');
    toast.className = `ccs-toast ccs-toast-${settings.type}`;
    toast.setAttribute('role', settings.type === 'error' ? 'alert' : 'status');

    const content = document.createElement('div');
    content.className = 'ccs-toast-message';
    content.textContent = message || '';
    toast.appendChild(content);

    if (settings.dismissible) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'ccs-toast-close';
      button.setAttribute('aria-label', 'Dismiss notification');
      button.innerHTML = '&times;';
      button.addEventListener('click', function () {
        dismiss(toast);
      });
      toast.appendChild(button);
    }

    getContainer().appendChild(toast);

    window.requestAnimationFrame(function () {
      toast.classList.add('is-visible');
    });

    if (settings.timeout && settings.timeout > 0) {
      window.setTimeout(function () {
        dismiss(toast);
      }, settings.timeout);
    }

    return toast;
  }

  function dismiss(toast) {
    if (!toast || toast.dataset.dismissed === 'true') {
      return;
    }

    toast.dataset.dismissed = 'true';
    toast.classList.remove('is-visible');
    toast.classList.add('is-hiding');

    window.setTimeout(function () {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 200);
  }

  CCS.register('toast', {
    show,
    dismiss,
    info(message, options) {
      return show(message, Object.assign({}, normalizeOptions(options), { type: 'info' }));
    },
    success(message, options) {
      return show(message, Object.assign({}, normalizeOptions(options), { type: 'success' }));
    },
    warning(message, options) {
      return show(message, Object.assign({}, normalizeOptions(options), { type: 'warning' }));
    },
    error(message, options) {
      return show(message, Object.assign({}, normalizeOptions(options), { type: 'error', timeout: 7000 }));
    },
  });
})(window, document);
