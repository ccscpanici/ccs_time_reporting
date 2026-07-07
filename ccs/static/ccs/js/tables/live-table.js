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

            this.selection = {
                cell: null,
                row: null
            };

			this.handleClick = this.handleClick.bind(this);
			this.handleKeyDown = this.handleKeyDown.bind(this);

			this.bindEvents();
		}

		//
		// Public API
		//

		selectCell(cell) {
            
            if (!this.isEditableCell(cell)) {
                return this;
            }
			
            this.clearSelection();

			this.selection.cell = cell;
            this.selection.row = cell.closest("tr");

			cell.classList.add("ccs-table-active-cell");

			if (this.selection.row) {
				this.selection.row.classList.add("ccs-table-active-row");
			}

			CCS.emit("table:cellSelected", {
				table: this,
				cell: this.selection.cell,
				row: this.selection.row
			});

            if (!cell.querySelector("input, select, textarea, button")) {
                cell.tabIndex = 0;
                cell.focus();
            }

			return this;
		}

		clearSelection() {

            if (this.selection.cell) {
                this.selection.cell.classList.remove("ccs-table-active-cell");
                this.selection.cell.removeAttribute("tabindex");
            }

            if (this.selection.row) {
                this.selection.row.classList.remove("ccs-table-active-row");
            }

            this.selection.cell = null;
            this.selection.row = null;

            return this;
        }

        cell() {
            return this.selection.cell;
        }

        row() {
            return this.selection.row;
        }

        rowIndex() {
            if (!this.selection.row) {
                return -1;
            }

            return Array.from(this.selection.row.parentElement.rows).indexOf(this.selection.row);
        }

        columnIndex() {
            if (!this.selection.cell) {
                return -1;
            }

            return Array.from(this.selection.cell.parentElement.cells).indexOf(this.selection.cell);
        }

        rightCell() {
            if (!this.cell()) {
                return null;
            }

            let cell = this.cell().nextElementSibling;

            while (cell && !this.isEditableCell(cell)) {
                cell = cell.nextElementSibling;
            }

            return cell || null;
        }

        leftCell() {
            if (!this.cell()) {
                return null;
            }

            let cell = this.cell().previousElementSibling;

            while (cell && !this.isEditableCell(cell)) {
                cell = cell.previousElementSibling;
            }

            return cell || null;
        }

        downCell() {
            const rowIndex = this.rowIndex();
            const columnIndex = this.columnIndex();

            if (rowIndex === -1 || columnIndex === -1) {
                return null;
            }

            const rows = Array.from(this.selection.row.parentElement.rows);
            const nextRow = rows[rowIndex + 1];

            if (!nextRow) {
                return null;
            }

            return nextRow.cells[columnIndex] || null;
        }

        upCell() {
            const rowIndex = this.rowIndex();
            const columnIndex = this.columnIndex();

            if (rowIndex === -1 || columnIndex === -1) {
                return null;
            }

            const rows = Array.from(this.selection.row.parentElement.rows);
            const previousRow = rows[rowIndex - 1];

            if (!previousRow) {
                return null;
            }

            return previousRow.cells[columnIndex] || null;
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

			const target = event.target;

            if (!target.matches("input, select, textarea")) {
                return;
            }

            const cell = target.closest("td");

            if (!cell) {
                return;
            }

            this.selectCell(cell);


			switch (event.key) {

                case "ArrowLeft":
                    event.preventDefault();
                    this.moveLeft();
                    break;

                case "ArrowRight":
                    event.preventDefault();
                    this.moveRight();
                    break;

                case "ArrowUp":
                    event.preventDefault();
                    this.moveUp();
                    break;

                case "ArrowDown":
                    event.preventDefault();
                    this.moveDown();
                    break;

                case "Tab":
                    event.preventDefault();

                    if (event.shiftKey) {
                        this.moveLeft();
                    } else {
                        this.moveRight();
                    }
                    break;
                case "Enter":
                    event.preventDefault();

                    if (event.shiftKey) {
                        this.moveUp();
                    } else {
                        this.moveDown();
                    }
                    break;

                case "Home":
                    event.preventDefault();
                    this.moveToRowStart();
                    break;

                case "End":
                    event.preventDefault();
                    this.moveToRowEnd();
                    break;
            }
		}

		//
		// Navigation
		//
        isEditableCell(cell) {
            return this.controlInCell(cell) !== null;
        }

        move(cell) {
            if (!cell) {
                return;
            }

            this.focusCell(cell);
        }

		moveRight() {
            this.move(this.rightCell());
        }

        moveLeft() {
            this.move(this.leftCell());
        }

        moveUp() {
            this.move(this.upCell());
        }

        moveDown() {
            this.move(this.downCell());
        }

        moveToRowStart() {
            const row = this.row();

            if (!row) {
                return;
            }

            const cell = Array.from(row.cells).find(cell => this.isEditableCell(cell));

            this.move(cell || null);
        }

        moveToRowEnd() {
            const row = this.row();

            if (!row) {
                return;
            }

            const cell = Array.from(row.cells)
                .reverse()
                .find(cell => this.isEditableCell(cell));

            this.move(cell || null);
        }

        controlInCell(cell) {
            if (!cell) {
                return null;
            }

            return cell.querySelector("input, select, textarea, button");
        }

        focusCell(cell) {
            if (!cell) {
                return;
            }

            this.selectCell(cell);

            const control = this.controlInCell(cell);

            if (control) {
                control.focus();

                if (typeof control.select === "function") {
                    control.select();
                }
            }
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