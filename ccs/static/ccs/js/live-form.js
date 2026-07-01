/*
 * CCS LiveForm
 * Reusable form controller for dirty tracking, autosave, and save state.
 */
(function (window) {
  "use strict";

  const CCS = window.CCS;

  class LiveForm {
    constructor(form, options) {
      this.form = form;
      this.options = options || {};
      this.dirty = false;
      this.saving = false;
      this.paused = false;
      this.destroyed = false;
    }

    isDirty() {
      return this.dirty;
    }

    isSaving() {
      return this.saving;
    }

    markDirty() {
      if (this.paused || this.destroyed) return;
      this.dirty = true;
      return this;
    }

    markClean() {
      this.dirty = false;
      return this;
    }

    pause() {
      this.paused = true;
      return this;
    }

    resume() {
      this.paused = false;
      return this;
    }

    async save() {
      if (this.destroyed) return null;

      if (typeof this.options.onSave === "function") {
        this.saving = true;

        try {
          const result = await this.options.onSave(this);
          this.markClean();
          return result;
        } finally {
          this.saving = false;
        }
      }

      return {
        ok: true,
        skipped: true,
        reason: "No onSave handler provided."
      };
    }

    destroy() {
      this.pause();
      this.destroyed = true;
      this.form = null;
      return this;
    }
  }

  function resolveForm(target) {
    if (typeof target === "string") {
      return document.querySelector(target);
    }

    return target;
  }

  const liveForm = {
    version: "1.0.0",

    attach(target, options) {
      const form = resolveForm(target);

      if (!form) {
        throw new Error("CCS.liveForm.attach: form not found.");
      }

      return new LiveForm(form, options || {});
    },

    LiveForm
  };

  CCS.registerModule("liveForm", liveForm);
})(window);
