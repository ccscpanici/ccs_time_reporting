/*
 * CCS LiveTable
 * Reusable table controller for selection, navigation, and future grid behavior.
 */
(function (window, document) {
  "use strict";

  const CCS = window.CCS;

  class LiveTable {
    constructor(table, options) {
      this.table = table;
      this.options = options || {};
      this.activeCell = null;
      this.activeRow = null;

      this.handleClick = this.handleClick.bind(this);
      this.bindEvents();
    }

    bindEvents() {
      this.table.addEventListener("click", this.handleClick);
    }

    handleClick(event) {
      const cell = event.target.closest("td, th");
      if (!cell || !this.table.contains(cell)) return;

      this.selectCell(cell);
    }

    selectCell(cell) {
      this.clearSelection();

      this.activeCell = cell;
      this.activeRow = cell.closest("tr");

      cell.classList.add("ccs-table-active-cell");

      if (this.activeRow) {
        this.activeRow.classList.add("ccs-table-active-row");
      }

      CCS.emit("table:cellSelected", {
        table: this,
        cell: this.activeCell,
        row: this.activeRow
      });

      return this;
    }

    clearSelection() {
      if (this.activeCell) {
        this.activeCell.classList.remove("ccs-table-active-cell");
      }

      if (this.activeRow) {
        this.activeRow.classList.remove("ccs-table-active-row");
      }

      this.activeCell = null;
      this.activeRow = null;

      return this;
    }

    destroy() {
      this.table.removeEventListener("click", this.handleClick);
      this.clearSelection();
      this.table = null;
      return this;
    }
  }

  function resolveTable(target) {
    if (typeof target === "string") {
      return document.querySelector(target);
    }

    return target;
  }

  const liveTable = {
    version: "0.1.0",

    attach(target, options) {
      const table = resolveTable(target);

      if (!table) {
        throw new Error("CCS.liveTable.attach: table not found.");
      }

      return new LiveTable(table, options || {});
    },

    LiveTable
  };

  CCS.ready(() => {
    document
      .querySelectorAll("table[data-live-table]")
      .forEach(table => {
        if (!table._ccsLiveTable) {
          table._ccsLiveTable = liveTable.attach(table);
        }
      });
  });

  CCS.registerModule("liveTable", liveTable, { replace: true });
})(window, document);