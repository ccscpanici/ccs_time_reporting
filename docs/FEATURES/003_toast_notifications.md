# Feature 003 – Toast Notifications

## Purpose

Add a reusable `CCS.toast` component for lightweight notifications that can be used by Time Reporting, JobGrid, and future CCS modules.

## What Changed

- Added `ccs/static/ccs/js/toast.js`.
- Added reusable toast styles to `ccs/static/ccs/css/ccs.css`.
- Loaded `toast.js` from `templates/base.html` after `ccs.js`.

## Usage

```javascript
CCS.toast.success('Saved');
CCS.toast.info('Loading...');
CCS.toast.warning('Unsaved changes');
CCS.toast.error('Save failed');
```

## Notes

This feature does not replace existing Django message banners yet. It only adds the shared notification component so later features can use the same UI everywhere.
