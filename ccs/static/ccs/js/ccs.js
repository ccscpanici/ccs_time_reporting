/*
 * CCS UI Core
 * Shared JavaScript namespace for CCS web applications.
 */
(function (window, document) {
  "use strict";

  const existing = window.CCS || {};
  const moduleRegistry = existing.modules || {};
  const eventRegistry = existing.events || {};

  const CCS = Object.assign(existing, {
    version: existing.version || "1.0.0",

    config: Object.assign({
      debug: false,
      environment: "production"
    }, existing.config || {}),

    modules: moduleRegistry,
    events: eventRegistry,
    initialized: existing.initialized || false,

    registerModule(name, module, options) {
      const settings = Object.assign({ replace: false }, options || {});

      if (!name || typeof name !== "string") {
        throw new Error("CCS.registerModule requires a module name.");
      }

      if (Object.prototype.hasOwnProperty.call(CCS, name) && !settings.replace) {
        throw new Error(`CCS module "${name}" is already registered.`);
      }

      CCS[name] = module;
      CCS.modules[name] = {
        name: name,
        version: module && module.version ? module.version : "1.0.0",
        loadedAt: new Date().toISOString(),
        type: typeof module
      };

      CCS.emit("module:registered", { name: name, module: module });

      if (CCS.config.debug && window.console && console.info) {
        console.info(`CCS module loaded: ${name}`);
      }

      return module;
    },

    register(name, module, options) {
      return CCS.registerModule(name, module, options);
    },

    hasModule(name) {
      return Object.prototype.hasOwnProperty.call(CCS.modules, name);
    },

    on(eventName, handler) {
      if (!eventName || typeof handler !== "function") return;

      CCS.events[eventName] = CCS.events[eventName] || [];
      CCS.events[eventName].push(handler);
    },

    off(eventName, handler) {
      if (!CCS.events[eventName]) return;

      CCS.events[eventName] = CCS.events[eventName].filter(function (registeredHandler) {
        return registeredHandler !== handler;
      });
    },

    emit(eventName, detail) {
      if (!CCS.events[eventName]) return;

      CCS.events[eventName].forEach(function (handler) {
        try {
          handler(detail);
        } catch (error) {
          if (window.console && console.error) {
            console.error(`CCS event handler failed for "${eventName}"`, error);
          }
        }
      });
    },

    init() {
      if (CCS.initialized) return;

      Object.keys(CCS.modules).forEach(function (moduleName) {
        const module = CCS[moduleName];

        if (module && typeof module.init === "function") {
          module.init(CCS);
        }
      });

      CCS.initialized = true;
      CCS.emit("platform:ready", CCS.info());
    },

    getCsrfToken() {
      const name = "csrftoken=";
      const cookies = document.cookie ? document.cookie.split(";") : [];

      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name)) {
          return decodeURIComponent(cookie.substring(name.length));
        }
      }

      return "";
    },

    ready(callback) {
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", callback, { once: true });
      } else {
        callback();
      }
    },

    info() {
      return {
        version: CCS.version,
        debug: !!CCS.config.debug,
        environment: CCS.config.environment,
        initialized: CCS.initialized,
        modules: Object.keys(CCS.modules).sort()
      };
    }
  });

  window.CCS = CCS;

  CCS.ready(function () {
    CCS.init();
  });
})(window, document);
