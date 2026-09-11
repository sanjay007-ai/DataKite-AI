import pandas as pd

def _norm(x): return "".join(ch for ch in str(x).lower() if ch.isalnum())
DATE_ALIASES=["date","orderdate","salesdate","transactiondate","invoicedate","createdat","timestamp","datetime"]
SALES_ALIASES=["sales","revenue","amount","orderamount","netsales","salesamount","totalamount","value","turnover"]

def _find(df, aliases):
    cols=list(df.columns); mp={_norm(c):c for c in cols}
    for a in aliases:
        if _norm(a) in mp:return mp[_norm(a)]
    for c in cols:
        n=_norm(c)
        if any(_norm(a) in n or n in _norm(a) for a in aliases):return c
    return None

def trend_analysis(df):
    if df is None or df.empty:return {"available":False,"message":"No data available."}
    dcol=_find(df,DATE_ALIASES); scol=_find(df,SALES_ALIASES)
    if not dcol or not scol:return {"available":False,"message":"A usable date and sales field are required."}
    try:d=pd.to_datetime(df[dcol],errors="coerce",format="mixed")
    except Exception:d=pd.to_datetime(df[dcol],errors="coerce")
    # Reject epoch-only dates caused by numeric serial/garbage coercion.
    valid=d.notna()
    if valid.sum()<2:return {"available":False,"message":"At least two valid date records are required."}
    years=d[valid].dt.year
    if years.nunique()==1 and int(years.iloc[0])<=1971:return {"available":False,"message":"The detected date field appears invalid; no 1970 epoch dates accepted."}
    x=pd.DataFrame({"date":d,"sales":pd.to_numeric(df[scol],errors="coerce")}).dropna()
    x["period"]=x.date.dt.to_period("M").astype(str)
    m=x.groupby("period",as_index=False).sales.sum(); m["growth_pct"]=m.sales.pct_change()*100
    if len(m):
        return {"available":True,"monthly":m.to_dict("records"),"highest":m.loc[m.sales.idxmax()].to_dict(),"lowest":m.loc[m.sales.idxmin()].to_dict(),"overall_growth":float(((m.sales.iloc[-1]/m.sales.iloc[0])-1)*100) if m.sales.iloc[0] else 0}
    return {"available":False,"message":"No valid monthly sales data."}

def format_trend_summary(r):
    if not r.get("available"): return r.get("message","Trend unavailable.")
    lines=["📈 Trend Analysis",f"Overall Sales Growth: {r['overall_growth']:.2f}%",f"Highest Sales Month: {r['highest']['period']} — ₹{r['highest']['sales']:,.2f}",f"Lowest Sales Month: {r['lowest']['period']} — ₹{r['lowest']['sales']:,.2f}","","Monthly Sales:"]
    for x in r["monthly"]: lines.append(f"• {x['period']}: ₹{x['sales']:,.2f}" + (f" ({x['growth_pct']:.2f}%)" if pd.notna(x['growth_pct']) else ""))
    return "\n".join(lines)

def analyze_trend(df): return trend_analysis(df)
