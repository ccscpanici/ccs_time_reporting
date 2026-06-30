# CCS Planner UI and Workflows

## Main Navigation

Add a top-level navigation item:

```text
Planner
```

Recommended routes:

```text
/planner/
/planner/workspaces/<workspace_id>/
/planner/spaces/<space_id>/
/planner/projects/<project_id>/
```

## Planner Home

The Planner home shows workspaces available to the logged-in user.

Primary actions:

- Create workspace
- Open workspace
- View my assigned tasks in a later phase

## Workspace View

The workspace view shows spaces and projects.

Layout:

```text
Workspace: Saputo

Sidebar:
  Waupun
    250435 - Whey Plant Demo
    250505 - Polished Water Silo Migration
  Lena
    Lena Sweet Cream Injection

Main panel:
  Workspace overview
  Recent activity later
  Open projects
```

Primary actions:

- Add space
- Add project
- Manage members
- Edit workspace settings

## Project View

A project should have tabs:

```text
Overview | Tasks | Files | Documents | Timesheets | Activity | Settings
```

MVP only needs:

```text
Overview | Tasks | Settings
```

## Task Sheet View

The task sheet should visually resemble Smartsheet:

```text
Toolbar: Add Row | Add Child | Indent | Outdent | Copy | Paste | Delete | Filter

Task Name | Assigned To | Status | Start | Finish | Duration | % Complete | Predecessors | Notes
```

Required behavior:

- Full-page grid layout
- Frozen header
- Inline cell editing
- Keyboard navigation
- Row selection
- Multi-row selection if practical
- Parent/child task hierarchy
- Expand/collapse parent rows
- Indent/outdent selected row
- Drag rows to reorder
- Autosave changes
- Clear visual distinction between parent tasks and child tasks

## Row Context Menu

Right-click or row action menu:

```text
Insert row above
Insert row below
Add child row
Indent
Outdent
Copy row
Delete row
```

## Autosave

Cell edits should save automatically through API endpoints. The UI should show a small save state:

```text
Saving...
Saved
Error saving
```

## Copy/Paste

MVP copy/paste behavior:

- Copy selected rows inside the sheet
- Paste below selected row
- Preserve hierarchy where practical

Excel-style clipboard integration can be improved later.
