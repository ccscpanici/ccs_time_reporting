"use strict";

const fs = require("fs");
const vm = require("vm");
const assert = require("assert");

function classList() {
  const values = new Set();
  return {
    add(value) { values.add(value); },
    remove(...items) { items.forEach(item => values.delete(item)); },
    contains(value) { return values.has(value); }
  };
}

const status = { textContent: "", classList: classList() };
const saveButton = { disabled: false, addEventListener() {}, removeEventListener() {} };
const form = {
  dataset: { liveFormDelay: "750" },
  value: "",
  querySelector(selector) {
    if (selector === "[data-live-form-status]") return status;
    if (selector === "[data-live-form-save]") return saveButton;
    return null;
  },
  querySelectorAll() { return []; },
  addEventListener() {},
  removeEventListener() {}
};

const documentStub = {
  addEventListener() {},
  removeEventListener() {},
  querySelectorAll() { return []; },
  querySelector() { return null; }
};

let liveFormModule = null;
const windowStub = {
  location: { href: "http://localhost/timesheets/today/", origin: "http://localhost", assign() {} },
  addEventListener() {},
  removeEventListener() {},
  CCS: {
    emit() {},
    ready(callback) { callback(); },
    registerModule(name, module) {
      if (name === "liveForm") liveFormModule = module;
    }
  }
};

const context = {
  window: windowStub,
  document: documentStub,
  FormData: class FormData { constructor(source) { this.value = source.value; } },
  URL,
  Date,
  Promise,
  setTimeout,
  clearTimeout,
  console
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync("ccs/static/ccs/js/components/live-form.js", "utf8"),
  context
);

assert(liveFormModule, "LiveForm module was not registered");

const field = { closest() { return null; } };
let resolveFirst;
const calls = [];

const controller = new liveFormModule.LiveForm(form, {
  onSave() {
    calls.push(form.value);
    if (calls.length === 1) {
      return new Promise(resolve => { resolveFirst = resolve; });
    }
    return Promise.resolve({ ok: true });
  }
});

async function run() {
  form.value = "first edit";
  controller.markDirty(field);
  const firstSave = controller.save();

  form.value = "newer edit";
  controller.markDirty(field);

  assert.strictEqual(controller.isDirty(), true, "newer edit must remain dirty");
  assert.strictEqual(status.textContent, "Unsaved Changes");

  const flush = controller.flush();
  resolveFirst({ ok: true });

  await firstSave;
  await flush;

  assert.deepStrictEqual(calls, ["first edit", "newer edit"]);
  assert.strictEqual(controller.isDirty(), false, "latest revision should be clean");
  assert.strictEqual(controller.isSaving(), false);
  assert.match(status.textContent, /Week Saved/);

  controller.destroy();
  console.log("LiveForm race regression test passed.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
