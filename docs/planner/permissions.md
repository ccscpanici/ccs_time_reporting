# CCS Planner Permissions

## Permission Strategy

Workspace membership is the primary security boundary. Users only see workspaces where they are members or where they have system-level administrative access.

## Workspace Roles

### Owner

Can:

- View workspace
- Edit workspace settings
- Delete/archive workspace
- Add users
- Remove users
- Change member roles
- Create/edit/archive spaces
- Create/edit/archive projects
- Create/edit/archive tasks
- Manage all future workspace settings

### Project Manager

Can:

- View workspace
- Invite editors and viewers
- Remove editors and viewers
- Create/edit/archive spaces
- Create/edit/archive projects
- Create/edit/archive tasks
- Manage task sheets

Cannot:

- Remove owners
- Change owner roles
- Delete workspace

### Editor

Can:

- View workspace
- View spaces/projects/tasks
- Create/edit tasks
- Add comments in future phase
- Upload task files in future phase

Cannot:

- Add/remove users
- Create/delete spaces
- Create/delete projects unless later allowed
- Change workspace settings

### Viewer

Can:

- View workspace
- View spaces/projects/tasks

Cannot:

- Edit tasks
- Add/delete rows
- Change project settings
- Add/remove users

## System Roles

Existing Django/admin-level permissions still apply. System administrators can access and administer all Planner records through Django admin.

## MVP Rule

Do not create space-specific permissions in the first version. Keep permissions workspace-based until a real need for space-specific access appears.
