(function () {
  const cfg = window.ProjectSheetConfig;
  const statuses = JSON.parse(document.getElementById("jobgrid-statuses").textContent);
  let currentProjectId = cfg.initialProjectId;
  let table = null;

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function url(template, id) {
    return template.replace(/0\//, `${id}/`);
  }

  async function jsonRequest(targetUrl, method, body) {
    const options = { method, headers: {"X-CSRFToken": csrfToken()} };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(targetUrl, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `Request failed: ${response.status}`);
    return payload;
  }

  function flattenRows(rows, parentId, output) {
    rows.forEach((row) => {
      output.push({id: row.id, parent_id: parentId || null, sort_order: output.length * 10});
      if (row._children && row._children.length) flattenRows(row._children, row.id, output);
    });
  }

  async function persistOrder() {
    const flat = [];
    flattenRows(table.getData(), null, flat);
    await jsonRequest(url(cfg.reorderUrlTemplate, currentProjectId), "POST", {rows: flat});
  }

  function selectedRow() {
    const rows = table.getSelectedRows();
    return rows.length ? rows[0] : null;
  }

  function selectedData() {
    const row = selectedRow();
    return row ? row.getData() : null;
  }

  function initials(name) {
    return (name || "").split(/\s+/).filter(Boolean).slice(0, 2).map(x => x[0]).join("").toUpperCase();
  }

  function taskNameFormatter(cell) {
    const data = cell.getRow().getData();
    const value = cell.getValue() || "";
    const icons = data.is_group ? "▾" : "";
    const rowTools = data.is_group ? "" : "<span class='row-icons'>📎 💬 🔔</span>";
    return `<div class="task-name-cell"><span>${icons}</span><span>${value}</span>${rowTools}</div>`;
  }

  function statusFormatter(cell) {
    const value = cell.getValue() || "";
    if (!value) return "";
    const cls = value === "Complete" ? "status-pill status-complete" : "status-pill";
    return `<span class="${cls}">${value}</span>`;
  }

  function assigneeFormatter(cell) {
    const value = cell.getValue() || "";
    if (!value) return "";
    return `<span class="assignee-chip" data-initials="${initials(value)}">${value}</span>`;
  }

  async function loadProject(projectId) {
    currentProjectId = projectId;
    const data = await jsonRequest(url(cfg.dataUrlTemplate, projectId), "GET");
    document.getElementById("project-name").value = data.project.name;
    document.querySelectorAll(".project-pill").forEach((btn) => btn.classList.toggle("active", Number(btn.dataset.projectId) === Number(projectId)));
    table.setData(data.rows || []);
  }

  async function addTask(isGroup, asChild) {
    const selected = selectedData();
    await jsonRequest(url(cfg.createTaskUrlTemplate, currentProjectId), "POST", {
      task_name: isGroup ? "New Section" : "New Task",
      is_group: isGroup,
      parent_id: asChild && selected ? selected.id : (selected && selected.is_group ? selected.id : null),
      after_task_id: selected ? selected.id : null,
    });
    await loadProject(currentProjectId);
  }

  async function indentSelected() {
    const row = selectedRow();
    if (!row) return;
    const prev = row.getPrevRow();
    if (!prev) return;
    await jsonRequest(url(cfg.updateTaskUrlTemplate, row.getData().id), "PATCH", {parent_id: prev.getData().id});
    await loadProject(currentProjectId);
  }

  async function outdentSelected() {
    const row = selectedRow();
    if (!row) return;
    await jsonRequest(url(cfg.updateTaskUrlTemplate, row.getData().id), "PATCH", {parent_id: null});
    await loadProject(currentProjectId);
  }

  table = new Tabulator("#project-sheet-table", {
    height: "100%",
    layout: "fitDataStretch",
    selectableRows: 1,
    movableRows: true,
    dataTree: true,
    dataTreeStartExpanded: true,
    dataTreeChildField: "_children",
    dataTreeElementColumn: "task_name",
    clipboard: true,
    clipboardCopyRowRange: "selected",
    clipboardPasteParser: "table",
    clipboardPasteAction: "update",
    history: true,
    index: "id",
    rowFormatter: function (row) {
      const data = row.getData();
      row.getElement().classList.toggle("group-row", !!data.is_group);
      row.getElement().classList.toggle("facility-row", !!data.is_group && !data.parent_id && !(data.start || data.finish || data.duration || data.status));
      row.getElement().classList.toggle("task-complete", data.status === "Complete");
    },
    rowMoved: persistOrder,
    cellEdited: async function (cell) {
      const row = cell.getRow().getData();
      const field = cell.getField();
      const payload = {};
      payload[field] = cell.getValue();
      await jsonRequest(url(cfg.updateTaskUrlTemplate, row.id), "PATCH", payload);
    },
    rowContextMenu: [
      {label: "+ Row Below", action: () => addTask(false, false)},
      {label: "+ Child Row", action: () => addTask(false, true)},
      {label: "Copy Row", action: async () => { const row = selectedData(); if (row) { await jsonRequest(url(cfg.duplicateTaskUrlTemplate, row.id), "POST"); await loadProject(currentProjectId); } }},
      {separator: true},
      {label: "Delete Row", action: async () => { const row = selectedData(); if (row && confirm(`Delete "${row.task_name}" and any subtasks under it?`)) { await jsonRequest(url(cfg.deleteTaskUrlTemplate, row.id), "POST"); await loadProject(currentProjectId); } }},
    ],
    columns: [
      {title: "", formatter: "rownum", width: 62, hozAlign: "center", headerSort: false, frozen: true, resizable: false},
      {title: "Task Name", field: "task_name", width: 360, editor: "input", formatter: taskNameFormatter, frozen: true},
      {title: "Start", field: "start", width: 95, editor: "input"},
      {title: "Finish", field: "finish", width: 95, editor: "input"},
      {title: "Duration", field: "duration", width: 95, editor: "input"},
      {title: "Predecessors", field: "predecessors", width: 150, editor: "input"},
      {title: "Assigned To", field: "assigned_to", width: 190, editor: "input", formatter: assigneeFormatter},
      {title: "% Complete", field: "percent_complete", width: 118, hozAlign: "right", editor: "number", editorParams: {min: 0, max: 100}},
      {title: "Status", field: "status", width: 140, editor: "list", editorParams: {values: statuses, clearable: true}, formatter: statusFormatter},
      {title: "Comments", field: "comments", width: 350, editor: "textarea"},
    ],
  });

  document.querySelectorAll(".project-pill").forEach((btn) => btn.addEventListener("click", () => loadProject(Number(btn.dataset.projectId))));
  document.getElementById("task-add").addEventListener("click", () => addTask(false, false));
  document.getElementById("child-add").addEventListener("click", () => addTask(false, true));
  document.getElementById("task-indent").addEventListener("click", indentSelected);
  document.getElementById("task-outdent").addEventListener("click", outdentSelected);
  document.getElementById("save-order").addEventListener("click", persistOrder);

  document.getElementById("task-duplicate").addEventListener("click", async () => {
    const row = selectedData();
    if (!row) return;
    await jsonRequest(url(cfg.duplicateTaskUrlTemplate, row.id), "POST");
    await loadProject(currentProjectId);
  });

  document.getElementById("task-delete").addEventListener("click", async () => {
    const row = selectedData();
    if (!row || !confirm(`Delete "${row.task_name}" and any subtasks under it?`)) return;
    await jsonRequest(url(cfg.deleteTaskUrlTemplate, row.id), "POST");
    await loadProject(currentProjectId);
  });

  document.getElementById("project-add").addEventListener("click", async () => {
    const name = prompt("Project name?");
    if (!name) return;
    await jsonRequest(cfg.createProjectUrl, "POST", {name});
    window.location.reload();
  });

  document.getElementById("project-name").addEventListener("change", async (event) => {
    await jsonRequest(url(cfg.updateProjectUrlTemplate, currentProjectId), "PATCH", {name: event.target.value});
    const active = document.querySelector(`.project-pill[data-project-id="${currentProjectId}"]`);
    if (active) active.textContent = `▯ ${event.target.value}`;
  });

  document.addEventListener("keydown", async (event) => {
    if (event.key === "Insert") { event.preventDefault(); await addTask(false, false); }
    if (event.key === "Tab" && selectedRow()) { event.preventDefault(); event.shiftKey ? await outdentSelected() : await indentSelected(); }
    if (event.key === "Delete" && selectedRow() && !document.activeElement.classList.contains("tabulator-editing")) {
      event.preventDefault();
    }
  });

  loadProject(currentProjectId);
})();
