# CCS Planner Implementation Roadmap

## Phase 0 - Design

Deliverables:

- Design documents in `docs/planner/`
- Agreement on hierarchy: Workspace > Space > Project > Task
- Agreement on roles: Owner, Project Manager, Editor, Viewer
- Agreement to replace experimental `jobgrid` with clean `planner` app

## Phase 1 - Planner Foundation

Deliverables:

- Remove `jobgrid` from `INSTALLED_APPS` and URLs
- Add new Django app: `planner`
- Add models and migrations:
  - Workspace
  - WorkspaceMembership
  - Space
  - Project
  - Task
- Register models in Django admin
- Add basic Planner navigation link
- Add workspace/project list pages

## Phase 2 - Task Sheet MVP

Deliverables:

- Project task sheet page
- Spreadsheet-style grid
- Inline task editing
- Add/delete tasks
- Parent/child hierarchy
- Expand/collapse
- Indent/outdent
- Drag reorder
- Autosave API
- Workspace permission enforcement

## Phase 3 - Collaboration

Deliverables:

- Manage workspace members page
- Invite/add existing users to workspace
- Task comments
- Task activity history
- Basic notifications

## Phase 4 - CCS Integration

Deliverables:

- Optional project link to existing Job records
- Project overview showing job/time summary
- Actual hours by project/job
- Future task-level time reporting support
- Document package links

## Phase 5 - Advanced Planning

Deliverables:

- Project templates
- Gantt view
- Task dependencies
- Dashboards
- Workload view by engineer
- Import/export
- SharePoint integration hooks
