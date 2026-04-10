"""Color maps and styling helpers for status and priority display."""

STATUS_COLORS = {
    "Introduced": "#2196F3",       # Blue
    "Assigned": "#FF9800",         # Orange
    "Reading": "#FFC107",          # Amber
    "Pending Approval": "#9C27B0", # Purple
    "Approved": "#4CAF50",         # Green
    "Cancelled": "#F44336",        # Red
}

PRIORITY_COLORS = {
    range(1, 4): "#4CAF50",   # Low — Green
    range(4, 7): "#FF9800",   # Medium — Orange
    range(7, 10): "#F44336",  # High — Red
    range(10, 11): "#9C27B0", # STAT — Purple
}


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "#9E9E9E")


def priority_color(priority: int) -> str:
    for r, color in PRIORITY_COLORS.items():
        if priority in r:
            return color
    return "#9E9E9E"


def priority_label(priority: int) -> str:
    if priority == 10:
        return "STAT"
    if priority >= 7:
        return "High"
    if priority >= 4:
        return "Medium"
    return "Low"


def style_status_column(df, column="status"):
    """Apply background color to the status column of a dataframe."""
    def _color(val):
        c = STATUS_COLORS.get(val, "#9E9E9E")
        return f"background-color: {c}; color: white; font-weight: bold"
    return df.style.applymap(_color, subset=[column])
