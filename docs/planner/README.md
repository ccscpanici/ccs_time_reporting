# CCS Planner Design Package

This folder captures the design decisions for the CCS Planner module before implementation.

The Planner is intended to become a Smartsheet-style project execution tool inside the CCS application, with workspaces, spaces, projects, task sheets, hierarchy, assignments, comments, files, and eventual integration with jobs, timesheets, packages, and SharePoint.

## Documents

- `phase_0_design.md` - overall product design and scope
- `data_model.md` - proposed Django model structure
- `permissions.md` - workspace roles and access rules
- `ui_workflows.md` - navigation and user workflows
- `implementation_roadmap.md` - phased development plan

## Guiding Principle

Build the Planner as its own Django app named `planner`, isolated from existing time reporting features until it is stable. The experimental `jobgrid` app should not be expanded further.
