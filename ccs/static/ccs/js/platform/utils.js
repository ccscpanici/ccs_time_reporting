/*
 * CCS Utilities
 * Shared helper functions used throughout the CCS Platform.
 */
(function (window) {
    "use strict";

    const CCS = window.CCS;

    const utils = {

        debounce(fn, delay = 300) {
            let timer;

            return function (...args) {
                clearTimeout(timer);

                timer = setTimeout(() => {
                    fn.apply(this, args);
                }, delay);
            };
        },

        throttle(fn, delay = 300) {
            let waiting = false;

            return function (...args) {

                if (waiting) {
                    return;
                }

                waiting = true;

                fn.apply(this, args);

                setTimeout(() => {
                    waiting = false;
                }, delay);
            };
        },

        uuid() {

            if (window.crypto?.randomUUID) {
                return crypto.randomUUID();
            }

            return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
                .replace(/[xy]/g, function (c) {

                    const r = Math.random() * 16 | 0;
                    const v = c === "x" ? r : (r & 0x3 | 0x8);

                    return v.toString(16);

                });

        },

        escapeHtml(text) {

            const div = document.createElement("div");

            div.textContent = text;

            return div.innerHTML;

        }

    };

    CCS.registerModule("utils", utils);

})(window);
