# Feature 002 - CCS Framework App

## Purpose

Create a reusable Django app named `ccs` to own shared UI framework assets for
both Time Reporting and JobGrid.

## What changed

- Added `ccs.apps.CcsConfig` to `INSTALLED_APPS`.
- Added a new `ccs/` app with placeholders for shared static assets, templates,
  and template tags.
- Moved the CCS core JavaScript and CSS into the shared app static structure:
  - `ccs/static/ccs/js/ccs.js`
  - `ccs/static/ccs/css/ccs.css`
- Updated `templates/base.html` to use Django's `{% static %}` tag for shared
  static assets.

## Behavior impact

No user-facing behavior should change. This feature is structural only.

## Future features enabled

- Toast notifications
- Save status indicator
- Live form/autosave framework
- Keyboard shortcut manager
- Dialogs and slide-out panels
- Shared JobGrid and Time Reporting UI components
