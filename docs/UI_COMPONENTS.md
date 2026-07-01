# CCS UI Components

Shared UI components live in the `ccs` Django app. These components should be
usable by both Time Reporting and JobGrid.

## Current foundation

- `CCS` JavaScript namespace
- `CCS.register(name, module)` module registration helper
- `CCS.getCsrfToken()` Django CSRF helper
- `CCS.request(url, options)` request manager with CSRF, JSON parsing, normalized errors, and optional toast integration
- `CCS.ready(callback)` DOM-ready helper

## Current reusable components

- Toast notifications
- Request manager

## Planned components

- Save status indicator
- Live form/autosave
- Keyboard shortcut manager
- Confirmation dialog
- Sliding side panel
- Search/picker components

## Toast Notifications

Reusable toast notifications are exposed through `CCS.toast`.

```javascript
CCS.toast.success('Saved');
CCS.toast.info('Loading...');
CCS.toast.warning('Unsaved changes');
CCS.toast.error('Save failed');
```

The toast component is intentionally generic and should be used by both Time Reporting and JobGrid instead of creating page-specific alert implementations.
