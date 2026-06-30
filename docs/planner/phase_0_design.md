# CCS Planner - Phase 0 Design

## Purpose

CCS Planner will provide a Smartsheet-style project planning workspace inside the CCS web application. The goal is not to copy Smartsheet feature-for-feature, but to build a project execution tool that matches CCS workflows and integrates with existing CCS time reporting, jobs, reporting, document packages, and future SharePoint integration.

## Product Hierarchy

```text
Workspace
  Space
    Project
      Task
        Subtasks
```

## Definitions

### Workspace

A workspace is the primary security and collaboration boundary. Workspace creators, owners, and project managers can add users to the workspace and assign workspace-level roles.

Examples:

```text
Saputo
Crystal Finishing
CCS Internal
Wastewater
Dairy
```

### Space

A space groups related projects within a workspace.

Examples:

```text
Workspace: Saputo
  Space: Waupun
  Space: Lena
  Space: Franklin
```

### Project

A project is a planning container inside a space. A project contains task sheets, files, comments, activity, and future integrations.

Examples:

```text
250435 - Whey Plant Demo
Black Creek PLC Upgrade
Lena Sweet Cream Injection
```

### Task

A task is a spreadsheet row in the project sheet. Tasks can contain unlimited nested subtasks.

## MVP Scope

The first production version should include:

- New Django app named `planner`
- Workspaces
- Workspace memberships
- Spaces
- Projects
- Smartsheet-style task sheet
- Parent/child task hierarchy
- Expand/collapse
- Inline editing
- Row add/delete
- Indent/outdent
- Drag reorder
- Copy/paste rows
- Autosave
- User assignment
- Status
- Start and finish dates
- Percent complete
- Notes/comments field

## Out of Scope for MVP

These should be designed for but not implemented first:

- Gantt chart
- True dependency scheduling
- Critical path
- Files and attachments
- Full comment threads
- Email notifications
- Customer portal
- SharePoint synchronization
- Timesheet-to-task entry
- Project templates
- Advanced dashboards

## Application Name

The Django app should be named:

```text
planner
```

The failed experimental `jobgrid` app should be removed before Planner implementation begins.
