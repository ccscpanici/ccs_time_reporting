# Milestone 004.1 – Platform Stabilization

## Goal

Stabilize the shared CCS JavaScript platform before building Live Forms, keyboard navigation, and JobGrid components on top of it.

## Why

Milestone 004 introduced `CCS.request()`, but the original core still included an older placeholder `CCS.request()` function. Loading `request.js` replaced that placeholder and produced a duplicate-module warning in the browser console.

That warning was harmless, but the platform should not replace modules during normal startup. Duplicate module registration should be treated as a development error so we catch accidental double-loading early.

## Changes

- Removed the older placeholder request helper from `ccs.js`.
- Made `CCS.register()` stricter: duplicate module registration now throws unless explicitly allowed.
- Added `CCS.modules` as a lightweight module registry.
- Added `CCS.hasModule(name)`.
- Added `CCS.info()` for quick browser-console diagnostics.

## Console Checks

Run these from the browser console on the development site:

```javascript
CCS.info()
```

Expected result includes:

```javascript
{
  version: "1.0.0",
  debug: false,
  modules: ["request", "toast"]
}
```

Then test the request manager:

```javascript
CCS.request(window.location.pathname)
  .then(r => console.log(r.status, r.ok))
  .catch(console.error);
```

Expected result:

```text
200 true
```

## Future Consumers

- Weekly Editor live saving
- JobGrid task editing
- Shared search components
- Developer diagnostics panel
