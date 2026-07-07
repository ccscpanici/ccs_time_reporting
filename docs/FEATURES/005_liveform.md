# CCS LiveForm

## Overview

CCS LiveForm is the standard client-side form controller used throughout the CCS platform.

It provides:

- Automatic dirty tracking
- Debounced autosave
- Manual AJAX save support
- Save status indicators
- Save button integration
- Common form lifecycle events
- Simple API for custom forms

A form becomes a LiveForm by adding the `data-live-form` attribute.

---

# Basic Usage

```html
<form
    method="post"
    data-live-form
    data-live-form-url="/timesheets/autosave/">

    {% csrf_token %}

    ...

</form>
```

When the page loads, LiveForm automatically attaches itself to every form containing:

```html
data-live-form
```

No JavaScript is required.

---

# HTML Attributes

## data-live-form

Marks a form as managed by LiveForm.

Example:

```html
<form data-live-form>
```

---

## data-live-form-url

Specifies the AJAX endpoint used for autosave.

Example

```html
<form

    data-live-form
    data-live-form-url="/timesheets/autosave/">

```

If omitted, LiveForm expects an `onSave()` handler.

---

## data-live-form-delay

Optional debounce delay (milliseconds).

Default:

```
750
```

Example

```html
<form

    data-live-form
    data-live-form-delay="1000">
```

---

# Save Button

A button can be linked to LiveForm.

```html
<button
    type="button"
    class="btn btn-primary"
    data-live-form-save>

    Save Now

</button>
```

LiveForm automatically

- prevents normal form submission
- performs an AJAX save
- disables the button while saving
- re-enables it afterwards

---

# Status Indicator

LiveForm can update a status element automatically.

```html
<span
    class="small text-muted"
    data-live-form-status>

</span>
```

Possible states include

```
Unsaved Changes
Saving...
✓ Saved 8:42 AM
⚠ Save failed
```

Status colors

| State | CSS Class |
|--------|-----------|
| Normal | text-muted |
| Saved | text-success |
| Unsaved | text-warning |
| Error | text-danger |

---

# Autosave

Autosave occurs automatically whenever:

- an input changes
- a select changes
- a textarea changes

After the configured debounce delay

(default 750 ms)

the form is posted via AJAX.

Multiple edits during the delay reset the timer.

---

# Manual Save

Clicking a save button

```html
data-live-form-save
```

calls

```javascript
liveForm.save()
```

instead of submitting the page.

---

# Dirty Tracking

The following events mark a form dirty

- input
- change

When the form becomes dirty

```
Unsaved Changes
```

is displayed.

After a successful save

```
✓ Saved
```

is displayed.

---

# AJAX Save

By default LiveForm submits

```javascript
new FormData(form)
```

using

```javascript
CCS.request()
```

to

```
data-live-form-url
```

The request uses

```
POST
```

Example

```javascript
await CCS.request(url, {
    method: "POST",
    body: new FormData(form)
});
```

---

# Custom Save Handler

Instead of using

```
data-live-form-url
```

a custom save handler may be supplied.

Example

```javascript
CCS.liveForm.attach(form, {

    async onSave(form) {

        ...

        return result;

    }

});
```

When an `onSave()` handler exists, LiveForm skips its built-in AJAX implementation.

---

# Events

LiveForm emits framework events.

Dirty

```javascript
CCS.on("form:dirty", e => {

    console.log(e.form);

});
```

Clean

```javascript
CCS.on("form:clean", e => {

    console.log(e.form);

});
```

These events allow future platform modules to integrate without modifying LiveForm.

Examples

- toast notifications
- navigation guards
- page unload warnings
- audit logging

---

# JavaScript API

A LiveForm instance is attached to the form.

```javascript
const lf = form._ccsLiveForm;
```

Available methods

## save()

```javascript
await lf.save();
```

---

## isDirty()

```javascript
if (lf.isDirty()) {

    ...

}
```

---

## isSaving()

```javascript
if (lf.isSaving()) {

    ...

}
```

---

## pause()

Temporarily disables dirty tracking.

```javascript
lf.pause();
```

---

## resume()

Re-enables dirty tracking.

```javascript
lf.resume();
```

---

## destroy()

Removes all event handlers.

```javascript
lf.destroy();
```

---

# Example

```html
<form

    method="post"

    data-live-form

    data-live-form-url="/timesheets/autosave/">

    {% csrf_token %}

    <input name="description">

    <button

        type="button"

        class="btn btn-primary"

        data-live-form-save>

        Save

    </button>

    <span

        class="small text-muted"

        data-live-form-status>

    </span>

</form>
```

No additional JavaScript is required.

---

# Current Features

✔ Dirty tracking

✔ Debounced autosave

✔ AJAX save

✔ Save status indicator

✔ Manual save button

✔ Automatic form attachment

✔ Framework events

---

# Planned Enhancements

- Unsaved changes navigation warning
- Save retry after network failure
- Offline queue
- Field validation integration
- Save progress indicator
- Multiple simultaneous LiveForms
- Save history
- Before-save hooks
- After-save hooks

---

# Related Platform Modules

- 002_ccs_framework.md
- 003_toast_notifications.md
- 004_request_manager.md
- 005_liveform.md

LiveForm depends on:

- CCS Framework
- Request Manager

LiveForm emits events that may be consumed by future platform modules.