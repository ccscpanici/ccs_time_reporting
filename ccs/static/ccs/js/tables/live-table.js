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
			this.handleKeyDown = this.handleKeyDown.bind(this);

			this.bindEvents();
		}

		//
		// Public API
		//

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

            if (!cell.querySelector("input, select, textarea, button")) {
                cell.tabIndex = 0;
                cell.focus();
            }

			return this;
		}

		clearSelection() {
            
            if (this.activeCell) {
                this.activeCell.classList.remove("ccs-table-active-cell");
                this.activeCell.removeAttribute("tabindex");
            }

            if (this.activeRow) {
                this.activeRow.classList.remove("ccs-table-active-row");
            }

            this.activeCell = null;
            this.activeRow = null;

            return this;
        }

		//
		// Event Binding
		//

		bindEvents() {
			this.table.addEventListener("click", this.handleClick);
			this.table.addEventListener("keydown", this.handleKeyDown);
		}

		//
		// Event Handlers
		//

		handleClick(event) {
			const cell = event.target.closest("td, th");

			if (!cell || !this.table.contains(cell)) {
				return;
			}

			this.selectCell(cell);
		}

		handleKeyDown(event) {
			if (!this.activeCell) {
				return;
			}

			switch (event.key) {
				case "ArrowRight":
					event.preventDefault();
					this.moveRight();
					break;
			}
		}

		//
		// Navigation
		//

		moveRight() {
			const next = this.activeCell.nextElementSibling;

			if (!next) {
				return;
			}

			this.selectCell(next);
		}

		//
		// Cleanup
		//

		destroy() {
			this.table.removeEventListener("click", this.handleClick);
			this.table.removeEventListener("keydown", this.handleKeyDown);

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