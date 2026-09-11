"""Universal, explainable Business Health scoring."""
import re
import numpy as np
import pandas as pd
from smart_analytics_engine import detect_schema


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col and col in df.columns else pd.Series(dtype=float)


def _clip(v): return int(max(0, min(100, round(v))))


def business_health(df):
    s = detect_schema(df)
    sales = _num(df, s.get("sales")); profit = _num(df, s.get("profit")); qty = _num(df, s.get("quantity"))
    n = max(len(df), 1)
    explanations=[]; scores=[]

    # Financial: margin when available, otherwise sales quality/completeness.
    if profit.notna().sum() >= 2 and sales.abs().sum() > 0:
        margin=float(profit.sum()/sales.sum()*100)
        financial=_clip(55 + margin*3)
        reason=f"Profit margin is {margin:.1f}%, based on detected sales and profit fields."
    else:
        completeness=float(df.notna().mean().mean()*100)
        financial=_clip(55+completeness*.35); reason=f"Financial fields are {completeness:.0f}% complete; profit data was not available for a direct margin test."
    explanations.append(("Financial Health",financial,reason,"financial")); scores.append(financial)

    # Sales: volume plus trend if date exists.
    if sales.notna().sum() >= 4:
        date_col=s.get("date")
        if date_col:
            d=pd.to_datetime(df[date_col],errors="coerce"); tmp=pd.DataFrame({"d":d,"v":sales}).dropna()
            if len(tmp)>=4:
                monthly=tmp.groupby(tmp.d.dt.to_period("M"))["v"].sum()
                growth=float((monthly.iloc[-1]/monthly.iloc[-2]-1)*100) if len(monthly)>=2 and monthly.iloc[-2]!=0 else 0
                sales_score=_clip(65+growth*2)
                reason=f"Latest-period sales changed {growth:+.1f}% versus the previous period."
            else: sales_score=70; reason="Sales are available, but there are not enough valid periods for a reliable trend comparison."
        else: sales_score=70; reason="Sales are available, but no reliable date field was detected for trend scoring."
    else: sales_score=55; reason="A usable sales/revenue field was not strong enough for a full sales-health calculation."
    explanations.append(("Sales Health",sales_score,reason,"sales")); scores.append(sales_score)

    # Customer: unique customer coverage + repeat behavior proxy.
    c=s.get("customer")
    if c and c in df.columns:
        unique=df[c].nunique(dropna=True); ratio=unique/n
        customer=_clip(70 + (ratio*30 if ratio < 1 else 0))
        reason=f"Detected {unique:,} unique customers across {n:,} records; the score rewards healthy customer coverage."
    else:
        customer=65; reason="No reliable customer identifier was detected, so the score uses a conservative baseline."
    explanations.append(("Customer Health",customer,reason,"customer")); scores.append(customer)

    # Inventory: direct stock field if present; otherwise quantity stability proxy.
    inv=None
    for col in df.columns:
        k=re.sub(r"[^a-z0-9]","",str(col).lower())
        if any(x in k for x in ["stock","inventory","onhand","stockqty"]): inv=col; break
    if inv:
        iv=_num(df,inv).dropna(); nonnegative=(iv>=0).mean()*100 if len(iv) else 60
        inventory=_clip(nonnegative); reason=f"Inventory/stock field '{inv}' is non-negative for {nonnegative:.0f}% of usable records."
    elif not qty.empty:
        q=qty.dropna(); cv=(q.std()/q.mean()) if len(q)>1 and q.mean()!=0 else 0
        inventory=_clip(88 - min(abs(cv)*15,30)); reason="No stock field was detected; quantity consistency is being used as a transparent inventory proxy."
    else:
        inventory=60; reason="No inventory or quantity field was detected, so the score uses a conservative baseline."
    explanations.append(("Inventory Health",inventory,reason,"inventory")); scores.append(inventory)

    # Operations: status quality + delivery/operations field completeness.
    status=s.get("status")
    if status:
        st=df[status].dropna().astype(str); valid=(st.str.strip().ne("")).mean()*100
        operations=_clip(65+valid*.35); reason=f"Status data is {valid:.0f}% populated, giving a strong view of operational outcomes."
    else:
        operations=_clip(55+df.notna().mean().mean()*.3*100); reason="No explicit status field was detected; operations score uses overall data completeness."
    explanations.append(("Operations Health",operations,reason,"operations")); scores.append(operations)

    overall=_clip(np.mean(scores))
    label="Excellent" if overall>=85 else "Healthy" if overall>=70 else "Watch" if overall>=55 else "Needs attention"
    return {"score":overall,"label":label,"components":[{"name":a,"score":b,"reason":c,"key":d} for a,b,c,d in explanations],"summary":f"Business Health is {overall}/100 — {label.lower()}. The score is calculated from the fields DataKite detected in this dataset."}
