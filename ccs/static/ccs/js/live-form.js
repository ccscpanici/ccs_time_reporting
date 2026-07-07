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
      this.statusElement = this.form.querySelector("[data-live-form-status]");
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

    setStatus(text, state = "muted") {
      if (!this.statusElement) return;

      this.statusElement.textContent = text;
      this.statusElement.classList.remove(
        "text-muted",
        "text-success",
        "text-warning",
        "text-danger"
      );

      const classMap = {
        muted: "text-muted",
        success: "text-success",
        warning: "text-warning",
        danger: "text-danger"
      };

      this.statusElement.classList.add(classMap[state] || "text-muted");
    }

    markDirty(field) {
      if (this.paused || this.destroyed) return this;

      if (!this.dirty) {
        this.dirty = true;
        this.setStatus("Unsaved Changes", "warning");

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
        this.setStatus(
          `✓ Saved ${new Date().toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit"
          })}`,
          "success"
        );

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

      //
      // Custom save handler
      //
      if (typeof this.options.onSave === "function") {
        this.saving = true;
        this.setStatus("Saving...", "muted");

        try {
          const result = await this.options.onSave(this);

          this.markClean();
          return result;
        } catch (error) {
          this.setStatus("⚠ Save failed", "danger");
          throw error;
        } finally {
          this.saving = false;
        }
      }

      //
      // Default AJAX save
      //
      const url = this.options.url || this.form.dataset.liveFormUrl;

      if (!url) {
        return {
          ok: true,
          skipped: true,
          reason: "No onSave handler or URL provided."
        };
      }

      this.saving = true;
      this.setStatus("Saving...", "muted");

      try {
        const response = await CCS.request(url, {
          method: "POST",
          body: new FormData(this.form)
        });

        if (!response.ok) {
          this.setStatus("⚠ Save failed", "danger");
          throw new Error(`Save failed: ${response.status}`);
        }

        this.markClean();

        return response;
      } catch (error) {
        this.setStatus("⚠ Save failed", "danger");
        throw error;
      } finally {
        this.saving = false;
      }
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
