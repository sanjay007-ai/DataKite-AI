"""Universal semantic schema adapter for DataKite AI.
Maps business concepts to real columns so charts/reports work across datasets.
"""
import re
import pandas as pd

ALIASES = {
    "sales": ["amount","sales","revenue","netsales","netrevenue","orderamount","salesamount","totalamount","gmv","turnover","value","price"],
    "profit": ["profit","netprofit","grossprofit","profitamount","marginprofit","earnings"],
    "cost": ["cost","totalcost","cogs","costamount","expense","expenses"],
    "quantity": ["quantity","qty","units","unitssold","volume"],
    "order": ["orderid","order","transactionid","transaction","invoiceid","invoice","orderno","ordernumber"],
    "customer": ["customer","customerid","client","clientid","buyer","userid","user","customername"],
    "product": ["product","productname","item","itemname","sku","skuname","service","serviceitem"],
    "category": ["category","subcategory","department","segment","foodcategory","productcategory","type"],
    "city": ["city","town","location","storecity","branchcity"],
    "region": ["region","state","province","area","territory","country","zone"],
    "payment": ["payment","paymentmethod","paymenttype","paymentmode","method"],
    "status": ["status","orderstatus","paymentstatus","state"],
    "date": ["date","orderdate","salesdate","transactiondate","invoicedate","createdat","timestamp","datetime","month","period"],
}

def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())

def find_column(df, kind):
    if df is None or df.empty: return None
    cols = list(df.columns)
    normalized = {norm(c): c for c in cols}
    for alias in ALIASES.get(kind, []):
        if norm(alias) in normalized: return normalized[norm(alias)]
    for c in cols:
        nc = norm(c)
        if any(norm(a) in nc or nc in norm(a) for a in ALIASES.get(kind, [])):
            return c
    return None

def detect_schema(df):
    schema = {k: find_column(df, k) for k in ALIASES}
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if schema["sales"] is None:
        candidates = [c for c in numeric if not any(x in norm(c) for x in ("id","qty","quantity","year","month","day","zip","postal"))]
        if candidates: schema["sales"] = candidates[0]
    if schema["quantity"] is None:
        candidates = [c for c in numeric if any(x in norm(c) for x in ("qty","quantity","units","volume"))]
        if candidates: schema["quantity"] = candidates[0]
    return schema

def numeric(df, col):
    return pd.to_numeric(df[col], errors="coerce").fillna(0) if col and col in df.columns else pd.Series(0, index=df.index, dtype=float)

def metric(df, col):
    return float(numeric(df,col).sum()) if col else 0.0

def unique_count(df, col):
    return int(df[col].dropna().astype(str).nunique()) if col and col in df.columns else 0

def order_count(df, schema):
    col = schema.get("order")
    return unique_count(df,col) if col else int(len(df))

def monthly(df, schema, value_kind="sales"):
    value_col = schema.get(value_kind)
    date_col = schema.get("date")
    if not value_col: return pd.DataFrame(columns=["period", value_kind])
    values = numeric(df,value_col)
    if date_col and date_col in df.columns:
        dates = pd.to_datetime(df[date_col], errors="coerce", format="mixed")
        if dates.notna().sum() >= 2:
            x = pd.DataFrame({"date":dates, value_kind:values}).dropna(subset=["date"])
            x["period"] = x["date"].dt.to_period("M").astype(str)
            return x.groupby("period",as_index=False)[value_kind].sum().sort_values("period")
    return pd.DataFrame(columns=["period", value_kind])

def grouped(df, group_col, value_col, n=10, ascending=False):
    if not group_col or not value_col or group_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame(columns=["label","value"])
    x = pd.DataFrame({"label":df[group_col].astype(str),"value":numeric(df,value_col)})
    g = x.groupby("label",as_index=False)["value"].sum().sort_values("value",ascending=ascending).head(n)
    return g
