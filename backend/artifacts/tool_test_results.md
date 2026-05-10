# Agent Tool Test Results
Generated at: 2026-05-10 02:38:23

## Tool: `get_scheme_quote`
### Inputs
```json
{
  "scheme_code": "119551"
}
```
### Output
```json
{
  "scheme_code": "119551",
  "scheme_name": "Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW",
  "last_updated": "08-May-2026",
  "nav": "104.8696"
}
```

---

## Tool: `get_historical_nav`
### Inputs
```json
{
  "scheme_code": "119551"
}
```
### Output
```json
{
  "fund_house": "Aditya Birla Sun Life Mutual Fund",
  "scheme_type": "Open Ended Schemes",
  "scheme_category": "Debt Scheme - Banking and PSU Fund",
  "scheme_code": 119551,
  "scheme_name": "Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW",
  "scheme_start_date": {
    "date": "02-01-2013",
    "nav": "103.00590"
  },
  "52_week_high": "111.10720",
  "52_week_low": "103.88130",
  "data": [
    {
      "date": "08-05-2026",
      "nav": "104.86960"
    },
    {
      "date": "07-05-2026",
      "nav": "104.87620"
    },
    {
      "date": "06-05-2026",
      "nav": "104.80430"
    },
    {
      "date": "05-05-2026",
      "nav": "104.61660"
    },
    {
      "date": "04-05-2026",
      "nav": "104.65440"
    },
    {
      "date": "30-04-2026",
      "nav": "104.57060"
    },
    {
      "date": "29-04-2026",
      "nav": "104.65940"
    },
    {
      "date": "28-04-2026",
      "nav": "104.74280"
    },
    {
      "date": "27-04-2026",
      "nav": "104.77710"
    },
    {
      "date": "24-04-2026",
      "nav": "104.70910"
    },
    {
      "date": "23-04-2026",
      "nav": "104.76520"
    },
    {
      "date": "22-04-2026",
      "nav": "104.84730"
    },
    {
      "date": "21-04-2026",
      "nav": "104.84700"
    },
    {
      "date": "20-04-2026",
      "nav": "104.83690"
    },
    {
      "date": "17-04-2026",
      "nav": "104.78210"
    },
    {
      "date": "16-04-2026",
      "nav": "104.79590"
    },
    {
      "date": "15-04-2026",
      "nav": "104.79010"
    },
    {
      "date": "13-04-2026",
      "nav": "104.61130"
    },
    {
      "date": "10-04-2026",
      "nav": "104.59560"
    },
    {
      "date": "09-04-2026",
      "nav": "104.51500"
    },
    {
      "date": "08-04-2026",
      "nav": "104.39190"
    },
    {
      "date": "07-04-2026",
      "nav": "103.99180"
    },
    {
      "date": "06-04-2026",
      "nav": "103.91420"
    },
    {
      "date": "02-04-2026",
      "nav": "103.88130"
    },
   
... [TRUNCATED] ...
```

---

## Tool: `get_scheme_details`
### Inputs
```json
{
  "scheme_code": "119551"
}
```
### Output
```json
{
  "fund_house": "Aditya Birla Sun Life Mutual Fund",
  "scheme_type": "Open Ended Schemes",
  "scheme_category": "Debt Scheme - Banking and PSU Fund",
  "scheme_code": 119551,
  "scheme_name": "Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW",
  "scheme_start_date": {
    "date": "02-01-2013",
    "nav": "103.00590"
  },
  "expense_ratio": "Not available in live API. Use 'read_factsheet' for this data.",
  "exit_load": "Not available in live API. Use 'read_factsheet' for this data.",
  "sharpe_ratio": "Not available in live API. Use 'read_factsheet' for this data."
}
```

---

## Tool: `get_equity_performance`
### Inputs
```json
{}
```
### Output
```json
{
  "Large Cap": [
    {
      "scheme_name": "Aditya Birla Sun Life Large Cap Fund",
      "benchmark": "Nifty 100 TRI",
      "latest NAV- Regular": 513.64,
      "latest NAV- Direct": 570.64,
      "1-Year Return(%)- Regular": 0.99492705,
      "1-Year Return(%)- Direct": 1.6730512,
      "3-Year Return(%)- Regular": 13.532163,
      "3-Year Return(%)- Direct": 14.287195,
      "5-Year Return(%)- Regular": 12.513559,
      "5-Year Return(%)- Direct": 13.270166
    },
    {
      "scheme_name": "Axis Large Cap Fund",
      "benchmark": "BSE 100 TRI",
      "latest NAV- Regular": 58.53,
      "latest NAV- Direct": 67.8,
      "1-Year Return(%)- Regular": -0.7797932,
      "1-Year Return(%)- Direct": 0.08857396,
      "3-Year Return(%)- Regular": 10.682491,
      "3-Year Return(%)- Direct": 11.672785,
      "5-Year Return(%)- Regular": 8.326076,
      "5-Year Return(%)- Direct": 9.387359
    },
    {
      "scheme_name": "Bajaj Finserv Large Cap Fund",
      "benchmark": "Nifty 100 TRI",
      "latest NAV- Regular": 9.968,
      "latest NAV- Direct": 10.227,
      "1-Year Return(%)- Regular": 4.180602,
      "1-Year Return(%)- Direct": 5.7382135,
      "3-Year Return(%)- Regular": null,
      "3-Year Return(%)- Direct": null,
      "5-Year Return(%)- Regular": null,
      "5-Year Return(%)- Direct": null
    },
    {
      "scheme_name": "Bandhan Large Cap Fund",
      "benchmark": "BSE 100 TRI",
      "latest NAV- Regular": 77.138,
      "latest NAV- Direct": 89.422,
      "1-Year Return(%)- Regular": 4.9410934,
      "1-Year Return(%)- Direct": 6.161554,
      "3-Year Return(%)- Regular": 15.487242,
      "3-Year Return(%)- Direct": 16.847271,
      "5-Year Return(%)- Regular": 13.104665,
      "5-Year Return(%)- Direct": 14.47528
    },
    {
      "scheme_name": "Bank of India Large Cap Fund",
      "benchmark": "Nifty 100 TRI",
      "latest NAV- Regular": 16.69,
      "latest NAV- Direct": 17.77,
      "1-Year Return(%)- Regular": 11.340894,
      "1-Year Retu
... [TRUNCATED] ...
```

---

## Tool: `get_debt_performance`
### Inputs
```json
{}
```
### Output
```json
{
  "Long Duration": [
    {
      "scheme_name": "Aditya Birla Sun Life Long Duration Fund",
      "benchmark": "NIFTY Long Duration Debt Index A-III",
      "latest NAV- Regular": 12.8188,
      "latest NAV- Direct": 13.1265,
      "1-Year Return(%)- Regular": -0.7732976,
      "1-Year Return(%)- Direct": -0.15289125,
      "3-Year Return(%)- Regular": 5.762926,
      "3-Year Return(%)- Direct": 6.4439187,
      "5-Year Return(%)- Regular": null,
      "5-Year Return(%)- Direct": null
    },
    {
      "scheme_name": "Axis Long Duration Fund",
      "benchmark": "NIFTY Long Duration Debt Index A-III",
      "latest NAV- Regular": 1225.5686,
      "latest NAV- Direct": 1243.6251,
      "1-Year Return(%)- Regular": -2.1944096,
      "1-Year Return(%)- Direct": -1.8167715,
      "3-Year Return(%)- Regular": 5.2157063,
      "3-Year Return(%)- Direct": 5.6598496,
      "5-Year Return(%)- Regular": null,
      "5-Year Return(%)- Direct": null
    },
    {
      "scheme_name": "Bandhan Long Duration Fund",
      "benchmark": "NIFTY Long Duration Debt Index A-III",
      "latest NAV- Regular": 11.1316,
      "latest NAV- Direct": 11.2289,
      "1-Year Return(%)- Regular": -0.8868153,
      "1-Year Return(%)- Direct": -0.47860035,
      "3-Year Return(%)- Regular": null,
      "3-Year Return(%)- Direct": null,
      "5-Year Return(%)- Regular": null,
      "5-Year Return(%)- Direct": null
    },
    {
      "scheme_name": "Franklin India Long Duration Fund",
      "benchmark": "CRISIL Long Duration Debt A-III Index",
      "latest NAV- Regular": 10.5747,
      "latest NAV- Direct": 10.6479,
      "1-Year Return(%)- Regular": -0.014182787,
      "1-Year Return(%)- Direct": 0.45378214,
      "3-Year Return(%)- Regular": null,
      "3-Year Return(%)- Direct": null,
      "5-Year Return(%)- Regular": null,
      "5-Year Return(%)- Direct": null
    },
    {
      "scheme_name": "HDFC Long Duration Debt Fund",
      "benchmark": "NIFTY Long Duration Debt Index A-III",
     
... [TRUNCATED] ...
```

---

## Tool: `get_hybrid_performance`
### Inputs
```json
{}
```
### Output
```json
{
  "Aggressive Hybrid": [
    {
      "scheme_name": "Aditya Birla Sun Life Equity Hybrid 95 Fund",
      "benchmark": "CRISIL Hybrid 35+65 - Aggressive Index",
      "latest NAV- Regular": 1510.65,
      "latest NAV- Direct": 1702.23,
      "1-Year Return(%)- Regular": 3.213971,
      "1-Year Return(%)- Direct": 4.0082364,
      "3-Year Return(%)- Regular": 12.500041,
      "3-Year Return(%)- Direct": 13.370112,
      "5-Year Return(%)- Regular": 10.184044,
      "5-Year Return(%)- Direct": 11.0491
    },
    {
      "scheme_name": "Axis Aggressive Hybrid Fund",
      "benchmark": "CRISIL Hybrid 35+65 - Aggressive Index",
      "latest NAV- Regular": 20.42,
      "latest NAV- Direct": 22.58,
      "1-Year Return(%)- Regular": 2.7162979,
      "1-Year Return(%)- Direct": 3.816092,
      "3-Year Return(%)- Regular": 10.896622,
      "3-Year Return(%)- Direct": 12.132559,
      "5-Year Return(%)- Regular": 9.162414,
      "5-Year Return(%)- Direct": 10.471504
    },
    {
      "scheme_name": "Bandhan Aggressive Hybrid Fund",
      "benchmark": "CRISIL Hybrid 35+65 - Aggressive Index",
      "latest NAV- Regular": 27.067,
      "latest NAV- Direct": 30.926,
      "1-Year Return(%)- Regular": 11.044103,
      "1-Year Return(%)- Direct": 12.601493,
      "3-Year Return(%)- Regular": 15.881219,
      "3-Year Return(%)- Direct": 17.435604,
      "5-Year Return(%)- Regular": 13.288215,
      "5-Year Return(%)- Direct": 14.776668
    },
    {
      "scheme_name": "Bank of India Mid & Small Cap Equity & Debt Fund",
      "benchmark": "70% Nifty MidSmall cap 400 TRI Index & 30% CRISIL Short Term Bond Index",
      "latest NAV- Regular": 41.0,
      "latest NAV- Direct": 45.17,
      "1-Year Return(%)- Regular": 16.180222,
      "1-Year Return(%)- Direct": 17.752867,
      "3-Year Return(%)- Regular": 20.61464,
      "3-Year Return(%)- Direct": 22.089632,
      "5-Year Return(%)- Regular": 17.458916,
      "5-Year Return(%)- Direct": 18.761852
    },
    {
      "scheme_name"
... [TRUNCATED] ...
```

---

## Tool: `search_schemes`
### Inputs
```json
{
  "amc_name": "HDFC"
}
```
### Output
```json
{
  "128628": "HDFC Banking and PSU Debt Fund - Growth Option",
  "128629": "HDFC Banking and PSU Debt Fund - Growth Option - Direct Plan",
  "128627": "HDFC Banking and PSU Debt Fund - IDCW Option",
  "128626": "HDFC Banking and PSU Debt Fund - IDCW Option - Direct Plan",
  "113070": "HDFC Corporate Bond Fund - Growth Option",
  "118987": "HDFC Corporate Bond Fund - Growth Option - Direct Plan",
  "132848": "HDFC Corporate Bond Fund - IDCW Option",
  "132849": "HDFC Corporate Bond Fund - IDCW Option - Direct Plan",
  "113071": "HDFC Corporate Bond Fund - Quarterly IDCW Option",
  "118986": "HDFC Corporate Bond Fund - Quarterly IDCW Option - Direct Plan",
  "128053": "HDFC Credit Risk Debt Fund - Growth Option",
  "128051": "HDFC Credit Risk Debt Fund - Growth Option - Direct Plan",
  "133148": "HDFC Credit Risk Debt Fund - IDCW Option",
  "133147": "HDFC Credit Risk Debt Fund - IDCW Option - Direct Plan",
  "128050": "HDFC Credit Risk Debt Fund - Quarterly IDCW - Direct Plan",
  "128052": "HDFC Credit Risk Debt Fund - Quarterly IDCW Option",
  "101872": "HDFC Dynamic Debt Fund - Growth Option",
  "119075": "HDFC Dynamic Debt Fund - Growth Option - Direct Plan",
  "119072": "HDFC Dynamic Debt Fund - Half Yearly IDCW - Direct Plan",
  "101874": "HDFC Dynamic Debt Fund - Half Yearly IDCW Option",
  "133369": "HDFC Dynamic Debt Fund - Normal IDCW - Direct Plan",
  "133370": "HDFC Dynamic Debt Fund - Normal IDCW Option",
  "119073": "HDFC Dynamic Debt Fund - Quarterly IDCW - Direct Plan",
  "101873": "HDFC Dynamic Debt Fund - Quarterly IDCW Option",
  "119074": "HDFC Dynamic Debt Fund - Yearly IDCW - Direct Plan",
  "101875": "HDFC Dynamic Debt Fund - Yearly IDCW Option",
  "106838": "HDFC Floating Rate Debt Fund - Daily IDCW Option",
  "118959": "HDFC Floating Rate Debt Fund - Direct Plan - Daily IDCW",
  "118961": "HDFC Floating Rate Debt Fund - Direct Plan - Growth Option",
  "118960": "HDFC Floating Rate Debt Fund - Direct Plan - Monthly IDCW",
  "118962": "HDFC Flo
... [TRUNCATED] ...
```

---

## Tool: `search_scheme_by_name`
### Inputs
```json
{
  "keyword": "midcap"
}
```
### Output
```json
{
  "152821": "ITI Large & Midcap Fund - Direct Plan - Growth",
  "152823": "ITI Large & Midcap Fund - Direct Plan - IDCW Option",
  "152824": "ITI Large & Midcap Fund - Regular Plan - Growth",
  "152822": "ITI Large & Midcap Fund - Regular Plan - IDCW Option",
  "120158": "Kotak Large & Midcap Fund - Direct- Growth",
  "103234": "Kotak Large & Midcap Fund - Growth-Regular",
  "120157": "Kotak Large & Midcap Fund - IDCW-Direct",
  "103233": "Kotak Large & Midcap Fund - IDCW-Regular",
  "118834": "Mirae Asset Large & Midcap Fund - Direct Plan - Growth",
  "118835": "Mirae Asset Large & Midcap Fund - Direct Plan - IDCW",
  "112932": "Mirae Asset Large & Midcap Fund - Regular Plan - Growth",
  "112931": "Mirae Asset Large & Midcap Fund - Regular Plan - IDCW",
  "147704": "Motilal Oswal Large and Midcap Fund - Direct Plan Growth",
  "147701": "Motilal Oswal Large and Midcap Fund - Regular Plan Growth",
  "147706": "Motilal Oswal Large and Midcap Fund Direct - IDCW Payout/Reinvestment",
  "147703": "Motilal Oswal Large and Midcap Fund Regular - IDCW Payout/Reinvestment",
  "141414": "Navi Large & Midcap Fund - Direct Annual IDCW Payout",
  "141415": "Navi Large & Midcap Fund - Direct Half Yearly IDCW Payout",
  "135679": "Navi Large & Midcap Fund - Direct Normal IDCW Payout",
  "141411": "Navi Large & Midcap Fund - Regular Annual IDCW payout"
}
```

---

## Tool: `calculate_returns`
### Inputs
```json
{
  "scheme_code": "119551",
  "balance_units": 100.5,
  "monthly_sip": 5000.0,
  "investment_months": 36
}
```
### Output
```json
{
  "scheme_code": "119551",
  "scheme_name": "Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW",
  "total_invested": 180000.0,
  "current_value": 10539.39,
  "profit_loss": -169460.61,
  "absolute_return_pct": "-94.14 %",
  "annualised_return_pct": "-84.92 %",
  "estimated_units": 100.5,
  "method": "Lump Sum Estimate"
}
```

---

## Tool: `read_factsheet`
### Inputs
```json
{
  "query": "What are the top holdings of HDFC Top 100 fund?"
}
```
### Output
```json
{
  "context": "Source: level1_simple_table.pdf (Page 1)\nSection: Top Holdings \u2014 January 2025\nTop Holdings \u2014 January 2025\n\nParag Parikh Flexi Cap Fund\nCompany Industry % of Net Assets\nHDFC Bank Limited Banks 8.11%\n\n---\n\nSource: level2_table_and_text.pdf (Page 2)\nSection: Top Holdings \u2014 Core Equity\nTop Holdings \u2014 Core Equity\n\nCompany Industry % of Net Assets\nHDFC Bank Limited Banks 8.11%\n\n---\n\nSource: level2_table_and_text.pdf (Page 2)\nSection: Top Holdings \u2014 Core Equity\nTop Holdings \u2014 Core Equity\n\nCompany Industry % of Net Assets\nHDFC Bank Limited Banks 8.11%\n\n---\n\nSource: ppfas-mf-factsheet-for-January-2025.pdf (Page 3)\nSection: Top Holdings\n[DATA-TABLE]: Top Holdings\n\n{'headers': ['Name Industry % of Net Assets', ''], 'rows': [['HDFC Bank Limited Banks 8.11%', ''], ['Bajaj Holdings & Investment Limited Finance 6.85%', ''], ['Power Grid Corporation of India Limited Power 6.24%', ''], ['Coal India Limited Consumable Fuels 6.15%', ''], ['ITC Limited Diversified FMCG 4.94%', ''], ['ICICI Bank Limited Banks 4.89%', ''], ['Kotak Mahindra Bank Limited Banks 4.19%', ''], ['Maruti Suzuki India Limited Automobiles 4.14%', ''], ['HCL Technologies Limited IT - Software 3.60%', ''], ['Mahindra & Mahindra Limited Automobiles 3.11%', ''], ['Axis Bank Limited Banks 3.00%', ''], ['Infosys Limited IT - Software 1.95%', ''], ['Balkrishna Industries Limited Auto Components 1.29%', ''], ['Cipla Limited Pharmaceuticals & Biotechnology 1.03%', ''], [\"Dr. Reddy's Laboratories Limited Pharmaceuticals & Biotechnology 1.0\", '0%'], ['Zydus Lifesciences Limited Pharmaceuticals & Biotechnology 0.96%', ''], ['Indian Energy Exchange Limited Capital Markets 0.86%', ''], ['Motilal Oswal Financial Services Limited Capital Markets 0.86%', ''], ['Multi Commodity Exchange of India Limited Capital Markets 0.56%', '']]}\n\n---\n\nSource: ppfas-mf-factsheet-for-January-2025.pdf (Page 10)\nSection: Mr. Raj Mehta - Debt Fund Manager 100\nMr. R
... [TRUNCATED] ...
```

---

