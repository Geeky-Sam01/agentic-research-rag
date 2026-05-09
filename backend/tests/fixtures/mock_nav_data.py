"""Mock data for NAV related tools."""

MOCK_SCHEME_QUOTE = {
    "scheme_code": 119551,
    "scheme_name": "Aditya Birla Sun Life AMC Limited",
    "nav": 150.25,
    "last_updated": "07-May-2026"
}

MOCK_HISTORICAL_NAV = {
    "fund_house": "Aditya Birla Sun Life AMC Limited",
    "scheme_type": "Open Ended Schemes",
    "scheme_category": "Equity Scheme - Large Cap Fund",
    "scheme_code": 119551,
    "scheme_name": "Aditya Birla Sun Life Frontline Equity Fund",
    "52_week_high": 160.00,
    "52_week_low": 110.00,
    "data": [
        {"date": "07-05-2026", "nav": 150.25},
        {"date": "06-05-2026", "nav": 149.50}
    ]
}
