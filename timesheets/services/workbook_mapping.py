# Workbook mapping for the CCS timecard template.
# Confirm cell positions against the final production template before going live.

TIME_SHEET_NAME = 'Time Sheet'
EXPENSE_SHEET_NAME = 'Expense Report'
PARTS_SHEET_NAME = 'Parts Report'

# Time entries are grouped into 7 chunks of 5 rows. Each chunk shares one date.
TIME_ENTRY_CHUNKS = [(20, 24), (25, 29), (30, 34), (35, 39), (40, 44), (45, 49), (50, 54)]

# Candidate cells because template revisions often move labels slightly.
FIRST_NAME_CELLS = ['B4', 'B5', 'C4', 'C5']
LAST_NAME_CELLS = ['D4', 'D5', 'E4', 'E5']
# The official workbook stores the week-start date in F7.
WEEK_START_CELLS = ['F7']

# Row-relative columns on Time Sheet. Adjust after exact template mapping is locked.
DATE_COL = 'A'
JOB_COL = 'B'
WORK_CODE_COL = 'C'
REGULAR_COL = 'D'
OVERTIME_COL = 'E'
DOUBLETIME_COL = 'F'
# Description cells are merged across G:M in the template, with G as the anchor cell.
DESCRIPTION_COL = 'G'

# Overnight is in column N, stored as TRUE()/FALSE() on the last line of each date group.
OVERNIGHT_COL = 'N'

# Expense Report rows map one-to-one to Time Sheet entry rows.
# Expense row 9 corresponds to Time Sheet row 20, and so on through 43 -> 54.
EXPENSE_FIRST_ROW = 9
EXPENSE_LAST_ROW = 43
EXPENSE_TIME_ROW_OFFSET = 11
EXPENSE_MILES_COL = 'C'
# Column D is calculated mileage amount in the workbook. The app recalculates it
# from miles * timesheet.mileage_rate, so it is intentionally not imported.
EXPENSE_PER_DIEM_FOOD_COL = 'E'
EXPENSE_AIR_FARE_COL = 'F'
EXPENSE_HOTEL_COL = 'G'
EXPENSE_TOLLS_PARKING_COL = 'H'
EXPENSE_RENTAL_CAR_FUEL_COL = 'I'
EXPENSE_BUSINESS_MEALS_COL = 'J'
EXPENSE_OTHER_EXPENSE_COL = 'K'
EXPENSE_EXPLANATION_COL = 'L'


# Parts Report rows map one-to-one to Time Sheet entry rows.
# Parts row 9 corresponds to Time Sheet row 20, through row 43 -> 54.
PARTS_FIRST_ROW = 9
PARTS_LAST_ROW = 43
PARTS_TIME_ROW_OFFSET = 11
PARTS_EE_STOCK_JOB_COL = 'B'
PARTS_QUANTITY_COL = 'C'
PARTS_DESCRIPTION_PART_NUMBER_COL = 'D'
PARTS_ADDITIONAL_NOTES_COL = 'E'
PARTS_REORDER_COL = 'F'
