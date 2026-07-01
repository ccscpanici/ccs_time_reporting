# Milestone 004 – Request Manager

## Goal

Create one reusable AJAX/request layer for CCS web applications.

## Why

Time Reporting and JobGrid will both rely heavily on AJAX. Without a shared
request manager, every page would eventually reimplement CSRF handling, JSON
parsing, error handling, and status handling differently.

This milestone gives future components a single API for browser-to-Django
requests.

## Dependencies

- Milestone 001 – CCS Core
- Milestone 002 – CCS Framework
- Milestone 003 – Toast Notifications, optional for error toast integration

## Files Changed

- `ccs/static/ccs/js/request.js`
- `templates/base.html`
- `docs/UI_COMPONENTS.md`
- `docs/FEATURES/004_request_manager.md`

## Public API

```javascript
CCS.request('/some/url/', {
    method: 'POST',
    data: {
        name: 'Example'
    },
    toastErrors: true
});
```

Convenience helpers are also available:

```javascript
CCS.request.get('/api/jobs/');
CCS.request.post('/api/timesheets/save/', { hours: 8 });
CCS.request.patch('/api/tasks/123/', { status: 'done' });
CCS.request.delete('/api/tasks/123/');
```

## Behavior

The request manager:

- Adds Django CSRF headers automatically.
- Adds `X-Requested-With: XMLHttpRequest` automatically.
- Sends plain objects as JSON.
- Supports `FormData` without forcing a JSON content type.
- Parses JSON responses when returned by the server.
- Returns a normalized result object.
- Throws `CCS.request.RequestError` for failed HTTP responses by default.
- Can show toast errors when `toastErrors: true` is passed.

## Future Consumers

- Weekly Editor live save
- JobGrid task editor
- Job picker/search
- User picker/search
- Profile/preferences live editing
- Manager approval actions

## Success Criteria

- Site loads normally.
- `CCS.request` exists in the browser console.
- `CCS.request.get(window.location.pathname)` returns a result object.
- Existing pages continue to behave as before.
