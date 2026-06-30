# CCS Planner Data Model

## Django App

```text
planner
```

## Core Models

### Workspace

```text
Workspace
- id
- name
- slug
- description
- created_by -> User
- created_at
- updated_at
- archived
```

### WorkspaceMembership

```text
WorkspaceMembership
- id
- workspace -> Workspace
- user -> User
- role
- invited_by -> User
- created_at
- updated_at
```

Recommended roles:

```text
owner
project_manager
editor
viewer
```

### Space

```text
Space
- id
- workspace -> Workspace
- name
- slug
- description
- sort_order
- created_by -> User
- created_at
- updated_at
- archived
```

### Project

```text
Project
- id
- space -> Space
- name
- slug
- project_number
- description
- manager -> User
- status
- priority
- start_date
- due_date
- sort_order
- linked_job -> timesheets.Job, optional and nullable in a later phase
- created_by -> User
- created_at
- updated_at
- archived
```

Recommended status values:

```text
planning
active
on_hold
complete
cancelled
```

Recommended priority values:

```text
low
normal
high
urgent
```

### Task

```text
Task
- id
- project -> Project
- parent -> Task, nullable
- title
- assigned_to -> User, nullable
- status
- start_date
- finish_date
- duration_days
- percent_complete
- predecessor_text
- notes
- sort_order
- outline_level
- collapsed
- created_by -> User
- created_at
- updated_at
- archived
```

Recommended task status values:

```text
not_started
in_progress
waiting
blocked
complete
cancelled
```

## Future Models

### TaskComment

```text
TaskComment
- task -> Task
- user -> User
- body
- created_at
- updated_at
```

### TaskAttachment

```text
TaskAttachment
- task -> Task
- uploaded_by -> User
- file
- original_filename
- created_at
```

### TaskDependency

```text
TaskDependency
- predecessor -> Task
- successor -> Task
- dependency_type
- lag_days
```

### ProjectTemplate

```text
ProjectTemplate
- name
- description
- created_by
- created_at
```

### ProjectTemplateTask

```text
ProjectTemplateTask
- template -> ProjectTemplate
- parent -> ProjectTemplateTask
- title
- sort_order
- default_duration_days
```

## Notes

For MVP, use relational rows for tasks rather than a generic cell table. This keeps the database easy to query for dashboards, assignments, due dates, overdue work, and time integration.
