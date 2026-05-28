# Today View + Template Readability Update

Changes:
- Added `/timesheets/today/`.
- Added a Today link to the navigation bar.
- Added a Today button on the timesheet list page.
- Today's view creates/opens the current week's timesheet and edits only today's rows.
- Today's view supports time, expenses, and parts.
- Refactored the timesheet save logic so full-week edit and Today edit share the same day-save helper.
- Reformatted key templates for readability:
  - `templates/base.html`
  - `templates/timesheets/list.html`
  - new `templates/timesheets/today.html`

No database migration required.
