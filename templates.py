"""
Client file format templates.

Each template defines how to read a specific client's file format and convert
it to the standard import format: Shift Date | First Name | Last Name | Total Hours
(and optionally Clock In / Clock Out).
"""

TEMPLATES = {
    "Staffing Agency Horizontal": {
        "description": "Punch-based export (one row per clock in/out).",
        "layout": "horizontal",
        "header_row": 0,
        "columns": {
            "full_name": "Employee",
            "clock_in": "In Time",
            "clock_out": "Out Time",
            "total_hours": "Hrs to Pay",
        },
        "name_order": "last_first",
        "strip_leading_digits": True,
        "datetime_in_clock": True,
        "skip_total_rows": True,
    },
    "Client Weekly Grid": {
        "description": "Weekly grid (one row per employee, day columns for hours).",
        "layout": "week_days",
        "header_row": 5,
        "week_ending_cell": {"row": 3, "col": 11},
        "week_ending_day": "saturday",
        "columns": {
            "full_name": "Contractor/Employee",
        },
        "day_columns": {
            "Monday": "MON HRS",
            "Tuesday": "TUES HRS",
            "Wednesday": "WED HRS",
            "Thursday": "THUR HRS",
            "Friday": "FRI HRS",
            "Saturday": "SAT HRS",
            "Sunday": "SUN HRS",
        },
        "name_order": "last_first",
        "skip_total_rows": True,
    },
}

SYSTEM_EXPORT_COLUMNS = {
    "date": "Date",
    "name": "Name",
    "total_hours": "Total Hours",
    "start_actual": "Start Actual",
    "finish_actual": "Finish Actual",
    "approval_status": "Approval Status",
}

DAY_OFFSETS_SAT_ENDING = {
    "Monday": -5,
    "Tuesday": -4,
    "Wednesday": -3,
    "Thursday": -2,
    "Friday": -1,
    "Saturday": 0,
    "Sunday": -6,
}
