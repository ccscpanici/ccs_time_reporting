"""Service-layer operations for history workflows.

Business rules live here so views and commands can share the same behavior.
"""

from django.utils import timezone


def _user_name(user):
    """Internal helper used to user name."""
    if not user:
        return "System"

    return user.get_full_name() or user.get_username()


def _add_event(events, *, timestamp, title, icon, badge,
               user=None, details=None):
    """Internal helper used to add event."""
    if not timestamp:
        return

    events.append({
        "timestamp": timestamp,
        "title": title,
        "icon": icon,
        "badge": badge,
        "user": _user_name(user),
        "details": details,
    })


def build_timesheet_history(timesheet):
    """
    Build a normalized chronological history for a timesheet.
    """

    events = []

    #
    # Timesheet lifecycle
    #
    _add_event(
        events,
        timestamp=timesheet.created_at,
        title="Timesheet Created",
        icon="bi-plus-circle",
        badge="secondary",
        user=timesheet.employee,
    )

    _add_event(
        events,
        timestamp=timesheet.submitted_at,
        title="Submitted",
        icon="bi-send",
        badge="primary",
        user=timesheet.employee,
    )

    _add_event(
        events,
        timestamp=getattr(timesheet, "approved_at", None),
        title="Approved",
        icon="bi-check-circle-fill",
        badge="success",
        user=getattr(timesheet, "approved_by", None),
    )

    _add_event(
        events,
        timestamp=getattr(timesheet, "reopened_at", None),
        title="Reopened",
        icon="bi-arrow-repeat",
        badge="warning",
        user=getattr(timesheet, "reopened_by", None),
    )

    _add_event(
        events,
        timestamp=getattr(timesheet, "quickbooks_exported_at", None),
        title="Exported to QuickBooks",
        icon="bi-box-arrow-up-right",
        badge="info",
        user=getattr(timesheet, "quickbooks_exported_by", None),
    )

    _add_event(
        events,
        timestamp=getattr(timesheet, "invoiced_at", None),
        title="Invoiced",
        icon="bi-receipt",
        badge="dark",
        user=getattr(timesheet, "invoiced_by", None),
    )

    #
    # Reopen Requests
    #
    for request in timesheet.reopen_requests.all().order_by("created_at"):

        _add_event(
            events,
            timestamp=request.created_at,
            title="Reopen Requested",
            icon="bi-unlock",
            badge="warning",
            user=request.requested_by,
            details=request.reason,
        )

        if request.status == "approved":

            _add_event(
                events,
                timestamp=request.decided_at,
                title="Reopen Approved",
                icon="bi-check-circle-fill",
                badge="success",
                user=request.decided_by,
                details=request.decision_notes,
            )

        elif request.status == "rejected":

            _add_event(
                events,
                timestamp=request.decided_at,
                title="Reopen Rejected",
                icon="bi-x-circle-fill",
                badge="danger",
                user=request.decided_by,
                details=request.decision_notes,
            )

    events.sort(key=lambda e: e["timestamp"])

    return events