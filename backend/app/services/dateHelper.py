from datetime import datetime, timedelta

# AMFI follows Indian market holidays. This is the 2025-26 calendar.
# Weekend dates are handled by the weekday check.
_AMFI_HOLIDAYS_2025 = {
    "26-Jan", "14-Apr", "15-Apr", "01-May", "17-Jun",
    "01-Jul", "15-Aug", "27-Aug", "02-Oct", "20-Oct",
    "01-Nov", "05-Nov", "25-Dec",
}
_AMFI_HOLIDAYS_2026 = {
    "26-Jan", "26-Mar", "02-Apr", "14-Apr", "01-May",
    "16-Jun", "07-Jul", "15-Aug", "27-Aug", "02-Oct",
    "20-Oct", "01-Nov", "05-Nov", "25-Dec",
}


def is_trading_day(dt: datetime) -> bool:
    """Check if a date is a potential AMFI publishing day.

    AMFI publishes NAV and performance data on trading days.
    On weekends and holidays, data is not updated.
    """
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    month_day = dt.strftime("%d-%b")
    year = dt.year
    holidays = _AMFI_HOLIDAYS_2025 if year == 2025 else _AMFI_HOLIDAYS_2026
    return month_day not in holidays


def prev_trading_day(dt: datetime) -> datetime:
    """Go back to the most recent trading day."""
    while not is_trading_day(dt):
        dt -= timedelta(days=1)
    return dt
