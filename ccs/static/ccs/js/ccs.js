/*
 * CCS UI Core
 * Shared JavaScript namespace for CCS web applications.
 *
 * This file intentionally avoids page-specific behavior. Feature modules such
 * as live forms, toast notifications, keyboard shortcuts, and JobGrid panels
 * should attach themselves to window.CCS instead of creating new globals.
 */
(function (window, document) {
  'use strict';

  const existing = window.CCS || {};
  const moduleRegistry = existing.modules || {};

  const CCS = Object.assign(existing, {
    version: existing.version || '1.0.0',

    config: Object.assign({
      debug: false,
    }, existing.config || {}),

    modules: moduleRegistry,

    /**
     * Register a module under the CCS namespace.
     *
     * Example:
     *   CCS.register('toast', { success: function(message) {} });
     */
    register(name, module, options) {
      const settings = Object.assign({ replace: false }, options || {});

      if (!name || typeof name !== 'string') {
        throw new Error('CCS.register requires a module name.');
      }

      if (Object.prototype.hasOwnProperty.call(CCS, name) && !settings.replace) {
        throw new Error(`CCS module "${name}" is already registered.`);
      }

      CCS[name] = module;
      CCS.modules[name] = {
        name: name,
        loadedAt: new Date().toISOString(),
        type: typeof module,
      };

      if (CCS.config.debug && window.console && console.info) {
        console.info(`CCS module loaded: ${name}`);
      }

      return module;
    },

    hasModule(name) {
      return Object.prototype.hasOwnProperty.call(CCS.modules, name);
    },

    /**
     * Return the CSRF token from the standard Django cookie.
     */
    getCsrfToken() {
      const name = 'csrftoken=';
      const cookies = document.cookie ? document.cookie.split(';') : [];

      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name)) {
          return decodeURIComponent(cookie.substring(name.length));
        }
      }

      return '';
    },

    ready(callback) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', callback, { once: true });
      } else {
        callback();
      }
    },

    info() {
      return {
        version: CCS.version,
        debug: !!CCS.config.debug,
        modules: Object.keys(CCS.modules).sort(),
      };
    },
  });

  window.CCS = CCS;
})(window, document);
