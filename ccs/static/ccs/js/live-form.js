/*
 * CCS LiveForm
 * Reusable form controller for dirty tracking, autosave, and save state.
 */
(function (window, document) {
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
      this.saveTimer = null;
      this.saveDelay = this.options.saveDelay || 750;

      this.handleChange = this.handleChange.bind(this);
      this.bindEvents();
    }

    isDirty() {
      return this.dirty;
    }

    isSaving() {
      return this.saving;
    }

    markDirty(field) {
      if (this.paused || this.destroyed) return this;

      if (!this.dirty) {
        this.dirty = true;

        CCS.emit("form:dirty", {
          form: this,
          field: field || null
        });
      }

      return this;
    }

    markClean() {
      if (this.dirty) {
        this.dirty = false;

        CCS.emit("form:clean", {
          form: this
        });
      }

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

    bindEvents() {
      this.form.addEventListener("input", this.handleChange);
      this.form.addEventListener("change", this.handleChange);
    }

    handleChange(event) {
      this.markDirty(event.target);
      this.scheduleSave();
    }

    scheduleSave() {
      if (this.paused || this.destroyed) return;

      clearTimeout(this.saveTimer);

      this.saveTimer = setTimeout(() => {
        if (this.isDirty() && !this.isSaving()) {
          this.save();
        }
      }, this.saveDelay);
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
      if (this.form) {
        this.form.removeEventListener("input", this.handleChange);
        this.form.removeEventListener("change", this.handleChange);
      }

      this.pause();
      clearTimeout(this.saveTimer);
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

  CCS.ready(() => {
    document
    .querySelectorAll("form[data-live-form]")
    .forEach(form => {
      if (!form._ccsLiveForm) {
        form._ccsLiveForm = liveForm.attach(form);
      }
    });
  });

  CCS.registerModule("liveForm", liveForm, { replace: true });
})(window, document);
