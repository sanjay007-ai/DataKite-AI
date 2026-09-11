"""Smart, dataset-driven conversational analytics layer.
Designed to sit above the existing analytics engines and provide robust
natural-language routing for short, long, and follow-up business questions.
"""
import re
import math
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())

ALIASES = {
    "sales": ["amount", "sales", "revenue", "netsales", "orderamount", "salesamount", "totalamount", "value", "turnover"],
    "profit": ["profit", "netprofit", "grossprofit", "profitamount", "marginprofit"],
    "cost": ["cost", "totalcost", "cogs", "costamount", "expense", "expenses"],
    "quantity": ["quantity", "qty", "units", "unitssold", "volume"],
    "order": ["orderid", "order", "transactionid", "transaction", "invoiceid", "invoice"],
    "customer": ["customer", "customerid", "client", "clientid", "buyer", "userid", "user"],
    "product": ["product", "productname", "item", "itemname", "sku", "sku_name"],
    "category": ["category", "subcategory", "department", "segment", "foodcategory"],
    "city": ["city", "town", "location", "storecity"],
    "region": ["region", "state", "province", "area", "territory", "country"],
    "date": ["date", "orderdate", "salesdate", "transactiondate", "invoicedate", "createdat", "timestamp", "datetime"],
}


def find_col(df, kind):
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    normalized = {_norm(c): c for c in cols}
    for alias in ALIASES.get(kind, []):
        if _norm(alias) in normalized:
            return normalized[_norm(alias)]
    # fuzzy contains fallback
    for c in cols:
        nc = _norm(c)
        if any(_norm(a) in nc or nc in _norm(a) for a in ALIASES.get(kind, [])):
            return c
    return None


def detect_schema(df):
    out = {k: find_col(df, k) for k in ALIASES}
    # Prefer a numeric column for sales if an explicit sales alias wasn't found.
    if out["sales"] is None:
        nums = df.select_dtypes(include=[np.number]).columns.tolist()
        candidates = [c for c in nums if not any(x in _norm(c) for x in ["id", "qty", "quantity", "year", "month", "day"])]
        if candidates:
            out["sales"] = candidates[0]
    return out


def parse_dates(df, date_col):
    if not date_col or date_col not in df.columns:
        return None
    s = df[date_col]
    try:
        d = pd.to_datetime(s, errors="coerce", format="mixed")
    except Exception:
        d = pd.to_datetime(s, errors="coerce")
    # Never accept an accidental epoch-only interpretation as a useful date field.
    if d.notna().sum() < 2:
        return None
    valid = d.dropna()
    if valid.empty or valid.dt.year.nunique() == 1 and valid.dt.year.iloc[0] <= 1971:
        return None
    return d


def money(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"₹{float(v):,.2f}"


def pct(v):
    return f"{float(v):.2f}%"


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce") if col else pd.Series(dtype=float)


def _metric(df, col):
    if not col:
        return None
    s = _num(df, col).dropna()
    return float(s.sum()) if not s.empty else None


def _top(df, group_col, value_col, n=5, ascending=False):
    if not group_col or not value_col:
        return []
    t = df[[group_col, value_col]].copy()
    t[value_col] = pd.to_numeric(t[value_col], errors="coerce")
    t = t.dropna(subset=[group_col, value_col])
    if t.empty:
        return []
    g = t.groupby(group_col, dropna=False)[value_col].sum().sort_values(ascending=ascending).head(n)
    return [(str(k), float(v)) for k, v in g.items()]


def monthly_sales(df, schema):
    date_col, sales_col = schema.get("date"), schema.get("sales")
    if not sales_col:
        return pd.DataFrame(columns=["period", "sales"])

    # Prefer a real date field.
    d = parse_dates(df, date_col)
    if d is not None:
        x = pd.DataFrame({"date": d, "sales": _num(df, sales_col)}).dropna(subset=["date", "sales"])
        if not x.empty:
            x["period"] = x["date"].dt.to_period("M").astype(str)
            return x.groupby("period", as_index=False)["sales"].sum()

    # Some business files contain Month/Period instead of a date.
    month_col = None
    for c in df.columns:
        n = _norm(c)
        if n in {"month", "period", "salesmonth", "ordermonth", "transactionmonth"}:
            month_col = c
            break
    if month_col:
        x = pd.DataFrame({"month": df[month_col], "sales": _num(df, sales_col)}).dropna(subset=["month", "sales"])
        if not x.empty:
            month_map = {name: i for i, name in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}
            def normalize_month(v):
                text=str(v).strip().lower()
                if text in month_map: return f"{month_map[text]:02d}-{text.title()}"
                try:
                    num=int(float(text))
                    if 1 <= num <= 12: return f"{num:02d}-{list(month_map.keys())[num-1].title()}"
                except Exception: pass
                return str(v).strip()
            x["period"] = x["month"].map(normalize_month)
            return x.groupby("period", as_index=False)["sales"].sum()

    return pd.DataFrame(columns=["period", "sales"])

def trend_result(df, schema):
    m = monthly_sales(df, schema)
    if len(m) < 1:
        return {"monthly": [], "available": False, "message": "I need a usable date field with at least one valid period."}
    m["growth_pct"] = m["sales"].pct_change() * 100
    first, last = float(m.iloc[0].sales), float(m.iloc[-1].sales)
    overall = ((last / first) - 1) * 100 if first else 0
    growth_rows = m.dropna(subset=["growth_pct"])
    inc = growth_rows.loc[growth_rows["growth_pct"].idxmax()] if not growth_rows.empty else None
    negative_rows = growth_rows[growth_rows["growth_pct"] < 0]
    dec = negative_rows.loc[negative_rows["growth_pct"].idxmin()] if not negative_rows.empty else None

    highest = m.loc[m.sales.idxmax()].to_dict()
    lowest = m.loc[m.sales.idxmin()].to_dict()
    # The first month has no prior month, so its growth is intentionally null.
    if not np.isfinite(float(highest.get("growth_pct", np.nan))):
        highest["growth_pct"] = None
    if not np.isfinite(float(lowest.get("growth_pct", np.nan))):
        lowest["growth_pct"] = None

    return {"available": True, "monthly": m.to_dict("records"), "overall_growth": float(overall),
            "highest": highest, "lowest": lowest,
            "biggest_increase": inc.to_dict() if inc is not None else None,
            "biggest_decrease": dec.to_dict() if dec is not None else None}


def _context_target(question, history):
    q = question.lower()
    # Resolve conversational references using recent assistant text/question.
    previous = " ".join(str(x) for x in (history[-3:] if history else []))
    if any(x in q for x in ["why", "cause", "reason", "what caused"]) and "month" not in q:
        m = re.findall(r"20\d{2}-\d{2}|\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", previous.lower())
        if m:
            return m[-1] if isinstance(m[-1], str) else str(m[-1])
    return None


def classify(question):
    q = re.sub(r"\s+", " ", str(question).strip().lower())
    if q in {"hi", "hello", "hey", "yo", "good morning", "good afternoon", "good evening"}:
        return "greeting"
    if q in {"thanks", "thank you", "thx", "ok", "okay", "great", "nice"}:
        return "casual"
    if any(x in q for x in ["generate report", "business report", "full analysis", "analyze this dataset", "analyse this dataset", "analyze dataset", "give me everything"]):
        return "full"
    # Explicit month-vs-month requests must win over generic trend words.
    month_names = "january|february|march|april|may|june|july|august|september|october|november|december"
    if re.search(r"\b(?:" + month_names + r")\b.*(?:\bvs\b|\bversus\b|\band\b).*\b(?:" + month_names + r")\b", q) or re.search(r"\b(?:" + month_names + r")\b.*\b(?:vs|versus|and)\b.*\b(?:" + month_names + r")\b", q):
        return "comparison"
    # Month-by-month requests are trend questions. This must run before KPI/category fallbacks.
    if ("month" in q or "monthly" in q) and not re.search(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b.*\b(?:vs|versus|and)\b.*\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", q):
        if any(x in q for x in ["monthly", "month over month", "highest", "lowest", "biggest", "growth", "decline", "trend", "increase", "decrease", "sales in"]):
            return "trend"
    if any(x in q for x in ["trend analysis", "sales trend", "sales growth", "growth trend", "performance trend"]):
        return "trend"
    if any(x in q for x in ["compare", "comparison", "versus", " vs ", "best and worst", "highest and lowest", "top and bottom"]):
        return "comparison"
    if any(x in q for x in ["forecast", "predict", "future sales", "next month", "next few periods"]):
        return "forecast"
    if any(x in q for x in ["anomal", "outlier", "unusual", "abnormal"]):
        return "anomaly"
    if any(x in q for x in ["recommend", "what should i do", "what should we do", "how can i improve", "actionable", "actions", "suggest"]):
        return "recommendation"
    if any(x in q for x in ["why", "cause", "reason", "driver", "drivers"]):
        return "root_cause"
    if any(x in q for x in ["customer", "customers", "client", "buyer"]):
        return "customer"
    if any(x in q for x in ["profit", "margin"]):
        return "profit"
    if any(x in q for x in ["category", "categories"]):
        return "category"
    if any(x in q for x in ["region", "state", "country", "city", "cities", "location"]):
        return "geo"
    if any(x in q for x in ["product", "products", "item", "sku"]):
        return "product"
    if any(x in q for x in ["explain my business", "business performance", "in simple words", "focus on next", "what should i focus"]):
        return "performance"
    if any(x in q for x in ["sales", "revenue", "amount", "turnover"]):
        return "sales"
    if any(x in q for x in ["cost", "cogs", "expense"]):
        return "cost"
    if any(x in q for x in ["order", "orders", "transaction", "transactions"]):
        return "orders"
    if any(x in q for x in ["column", "columns", "rows", "dataset", "file", "data"]):
        return "dataset"
    return "general"


def _kpi_answer(df, s):
    sales, profit = _metric(df, s["sales"]), _metric(df, s["profit"])
    # If the dataset has no explicit cost column, derive cost as Sales - Profit.
    cost = _metric(df, s["cost"]) if s.get("cost") else ((sales - profit) if sales is not None and profit is not None else None)
    order_col, cust_col = s["order"], s["customer"]
    orders = int(df[order_col].nunique()) if order_col else len(df)
    customers = int(df[cust_col].nunique()) if cust_col else None
    aov = sales / orders if sales is not None and orders else None
    lines = ["📊 Dynamic KPI Summary"]
    if sales is not None: lines.append(f"• Total Sales: {money(sales)}")
    if profit is not None: lines.append(f"• Total Profit: {money(profit)}")
    if cost is not None: lines.append(f"• Total Cost: {money(cost)}")
    lines.append(f"• Total Orders: {orders:,}")
    if customers is not None: lines.append(f"• Unique Customers: {customers:,}")
    if aov is not None: lines.append(f"• Average Order Value: {money(aov)}")
    if profit is not None and sales: lines.append(f"• Profit Margin: {pct(profit/sales*100)}")
    if s["quantity"]:
        qty = _metric(df, s["quantity"])
        if qty is not None: lines.append(f"• Total Quantity: {qty:,.2f}")
    return "\n".join(lines)


def _full(df, s):
    lines = [_kpi_answer(df, s), "", "🏆 Top Performance"]
    for label, key in [("Category", "category"), ("Region/City", "region"), ("Product", "product")]:
        col = s[key]
        if key == "region" and not col: col = s["city"]
        tops = _top(df, col, s["sales"], 5)
        if tops:
            lines.append(f"• Top {label}s: " + ", ".join(f"{n} ({money(v)})" for n,v in tops))
    tr = trend_result(df, s)
    if tr.get("available"):
        lines += ["", "📈 Trend", f"• Overall change: {pct(tr['overall_growth'])}", f"• Highest month: {tr['highest']['period']} — {money(tr['highest']['sales'])}", f"• Lowest month: {tr['lowest']['period']} — {money(tr['lowest']['sales'])}"]
    if s["profit"]:
        pcol = s["profit"]
        for label, key in [("category", "category"), ("region", "region"), ("product", "product")]:
            col = s[key] or (s["city"] if key == "region" else None)
            tops = _top(df, col, pcol, 3)
            if tops: lines.append(f"• Top {label} by profit: " + ", ".join(f"{n} ({money(v)})" for n,v in tops))
    lines += ["", "💡 Key Insights", "• Focus on the strongest revenue segment while investigating the weakest month/segment.", "• Protect profitable products and customers, not just high-volume ones.", "• Monitor the largest month-to-month decline and its drivers.", "", "🎯 Actionable Recommendations", "1. Increase investment in the strongest category/market.", "2. Investigate the weakest month and its top declining drivers.", "3. Protect high-value customers with retention offers.", "4. Review low-margin products/categories for pricing or cost improvement.", "5. Track monthly sales, profit and margin together.", "", "💬 Useful next questions", "• Why did sales fall in the weakest month?", "• Which category generated the most profit?", "• Which customers are highest value?", "• What should I do to improve sales?"]
    return "\n".join(lines)


def answer_question(df, question, history=None):
    if df is None or df.empty:
        return {"answer": "Please upload a CSV or Excel file first."}
    history = history or []
    s = detect_schema(df)
    intent = classify(question)
    q = str(question).strip().lower()

    if intent == "greeting":
        return {"answer": "Hello! 👋 I'm your Data Analyst AI. Ask me about sales, profit, customers, products, trends, anomalies, forecasts, or recommendations."}
    if intent == "casual":
        return {"answer": "You're welcome! 👍 Ask me anything about the uploaded dataset."}
    if intent == "dataset":
        return {"answer": f"📄 Dataset: {len(df):,} rows × {len(df.columns):,} columns\n\nColumns: {', '.join(map(str, df.columns))}"}
    if intent == "full":
        return {"answer": _full(df, s), "intent": intent}
    if intent == "sales":
        return {"answer": _kpi_answer(df, s), "intent": intent}
    if intent == "performance":
        sales=_metric(df,s["sales"]); profit=_metric(df,s["profit"]); margin=(profit/sales*100) if sales and profit is not None else None
        tops=_top(df,s["category"],s["sales"],1); cities=_top(df,s["city"] or s["region"],s["sales"],1)
        tr=trend_result(df,s)
        lines=["📊 BUSINESS PERFORMANCE — SIMPLE SUMMARY"]
        if sales is not None: lines.append(f"• Sales: {money(sales)}")
        if profit is not None: lines.append(f"• Profit: {money(profit)}" + (f" ({pct(margin)} margin)" if margin is not None else ""))
        if tops: lines.append(f"• Strongest category: {tops[0][0]} ({money(tops[0][1])})")
        if cities: lines.append(f"• Strongest market: {cities[0][0]} ({money(cities[0][1])})")
        if tr.get("available"):
            direction="up" if tr["overall_growth"]>0 else "down" if tr["overall_growth"]<0 else "stable"
            lines.append(f"• Sales trend: {direction} ({pct(tr["overall_growth"])})")
        lines += ["", "🎯 What to focus on next", "• Protect the strongest profitable segments.", "• Investigate the largest monthly decline and its drivers.", "• Improve weak-margin segments and monitor sales and profit together."]
        return {"answer":"\n".join(lines),"intent":intent}
    if intent == "cost":
        v = _metric(df, s["cost"]) if s.get("cost") else None
        if v is None:
            sales = _metric(df, s.get("sales")); profit = _metric(df, s.get("profit"))
            v = (sales - profit) if sales is not None and profit is not None else None
        return {"answer": f"Total Cost: {money(v)}" if v is not None else "I couldn't calculate cost from this dataset."}
    if intent == "orders":
        col=s["order"]; v=int(df[col].nunique()) if col else len(df)
        return {"answer": f"Total Orders: {v:,}"}
    if intent == "profit":
        p = _metric(df, s["profit"])
        lines = [f"Total Profit: {money(p)}" if p is not None else "I couldn't find a profit column."]
        if p is not None and s["sales"]:
            sales=_metric(df,s["sales"]); lines.append(f"Profit Margin: {pct(p/sales*100)}" if sales else "")
        for label,key in [("category","category"),("region/city","region"),("product","product")]:
            col=s[key] or (s["city"] if key=="region" else None); tops=_top(df,col,s["profit"],5)
            if tops: lines.append(f"Top {label} by profit: " + ", ".join(f"{n} ({money(v)})" for n,v in tops))
        return {"answer":"\n".join(x for x in lines if x),"intent":intent}
    if intent == "category":
        tops=_top(df,s["category"],s["sales"],5)
        return {"answer": "🏆 Top Categories by Sales\n" + "\n".join(f"{i}. {n} — {money(v)}" for i,(n,v) in enumerate(tops,1)) if tops else "I couldn't find a category and sales column together."}
    if intent == "geo":
        col=s["region"] or s["city"]
        # Explicit city wording must use the City column, not State/Region.
        if "city" in q and s["city"]: col=s["city"]
        if col and s["sales"]:
            all_vals=_top(df,col,s["sales"],len(df[col].dropna().unique()))
            if all_vals and any(x in q for x in ["highest", "best", "strongest"]) and not any(x in q for x in ["top 5", "top five", "top 10", "top ten"]):
                n,v=all_vals[0]
                return {"answer":f"🏙️ Best City by Sales\n• {n} — {money(v)}","intent":intent}
            if all_vals and any(x in q for x in ["lowest", "weakest", "worst"]):
                top5=all_vals[:5]
                low=all_vals[-1]
                lines=["🏙️ City Sales Ranking"]+[f"{i}. {n} — {money(v)}" for i,(n,v) in enumerate(top5,1)]
                lines.append(f"\nLowest-performing: {low[0]} — {money(low[1])}")
                return {"answer":"\n".join(lines),"intent":intent}
        tops=_top(df,col,s["sales"],5)
        return {"answer": "🏙️ Top Regions/Cities by Sales\n" + "\n".join(f"{i}. {n} — {money(v)}" for i,(n,v) in enumerate(tops,1)) if tops else "I couldn't find a usable region/city and sales column."}
    if intent == "product":
        tops=_top(df,s["product"],s["sales"],5)
        return {"answer": "🛒 Top Products by Sales\n" + "\n".join(f"{i}. {n} — {money(v)}" for i,(n,v) in enumerate(tops,1)) if tops else "I couldn't find a usable product and sales column."}
    if intent == "comparison":
        # Explicit city-vs-city comparison must win over generic best/worst/category logic.
        # Example: "Compare Hyderabad vs Mumbai sales".
        if s.get("city") and s.get("sales"):
            cities = [str(v).strip() for v in df[s["city"]].dropna().unique() if str(v).strip()]
            city_hits = []
            for city in sorted(cities, key=len, reverse=True):
                if re.search(r"\b" + re.escape(city.lower()) + r"\b", q):
                    city_hits.append(city)
            # Preserve first occurrence and require two distinct cities.
            seen = set(); city_hits = [c for c in city_hits if not (c.casefold() in seen or seen.add(c.casefold()))]
            if len(city_hits) >= 2 and any(x in q for x in ["compare", " vs ", " versus ", " and "]):
                a, b = city_hits[0], city_hits[1]
                vals = df.assign(__sales=_num(df, s["sales"]))
                av = float(vals.loc[vals[s["city"]].astype(str).str.strip().str.casefold() == a.casefold(), "__sales"].sum())
                bv = float(vals.loc[vals[s["city"]].astype(str).str.strip().str.casefold() == b.casefold(), "__sales"].sum())
                diff = av - bv
                change = (diff / bv * 100) if bv else 0
                winner = a if av > bv else b if bv > av else "Tie"
                return {"answer": f"🏙️ City Comparison\n• {a}: {money(av)}\n• {b}: {money(bv)}\n• Difference: {money(diff)} ({pct(change)} vs {b}).\n• Better performer: {winner}", "intent": intent}

        # Explicit month-vs-month comparison (e.g. "compare July and March").
        month_names={"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        month_hits=re.findall(r"\b("+"|".join(month_names.keys())+r")\b", q)
        if len(month_hits) >= 2 and s.get("sales"):
            a,b=month_names[month_hits[0]],month_names[month_hits[1]]
            d=parse_dates(df,s.get("date"))
            if d is not None:
                x=pd.DataFrame({"date":d,"sales":_num(df,s["sales"]) }).dropna()
                x["month_num"]=x["date"].dt.month
                av=float(x.loc[x.month_num==a,"sales"].sum()); bv=float(x.loc[x.month_num==b,"sales"].sum())
            else:
                month_col=next((c for c in df.columns if _norm(c) in {"month","period","salesmonth","ordermonth","transactionmonth"}), None)
                if not month_col:
                    return {"answer":"📅 Month comparison unavailable: this dataset has no usable date or month field. I won't substitute a category comparison.","intent":intent}
                mv=df[month_col].astype(str).str.strip().str.lower()
                av=float(_num(df.loc[mv==month_hits[0],s["sales"]],s["sales"]).sum())
                bv=float(_num(df.loc[mv==month_hits[1],s["sales"]],s["sales"]).sum())
            if av==0 and bv==0:
                return {"answer":f"I couldn't find sales data for {month_hits[0].title()} and {month_hits[1].title()}.","intent":intent}
            diff=av-bv; base=bv if bv else 0; change=(diff/base*100) if base else 0
            return {"answer":f"📊 Month Comparison\n• {month_hits[0].title()}: {money(av)}\n• {month_hits[1].title()}: {money(bv)}\n• Difference: {money(diff)} ({pct(change)} vs {month_hits[1].title()}).","intent":intent}

        # Natural-language best/worst comparison: compute both sides from the uploaded dataset.
        group = s["category"]
        label = "category"
        if "city" in q and s["city"]:
            group = s["city"]; label = "city"
        elif "region" in q and s["region"]:
            group = s["region"]; label = "region"
        elif "product" in q and s["product"]:
            group = s["product"]; label = "product"
        vals=_top(df,group,s["sales"],len(df[group].dropna().unique()) if group else 0) if group and s["sales"] else []
        if not vals:
            return {"answer": f"I couldn't find a usable {label} and sales field for comparison.","intent":intent}
        best=vals[0]; worst=vals[-1]; delta=best[1]-worst[1]; pct_change=(delta/worst[1]*100) if worst[1] else 0
        return {"answer":f"⚖️ Best vs Worst {label.title()}\n• Best: {best[0]} — {money(best[1])}\n• Worst: {worst[0]} — {money(worst[1])}\n• Difference: {money(delta)} ({pct(pct_change)} higher for the best).","intent":intent}
    if intent == "customer":
        tops=_top(df,s["customer"],s["sales"],5)
        if not tops: return {"answer":"I couldn't find a usable customer and sales column."}
        total=sum(v for _,v in tops); overall=_metric(df,s["sales"])
        concentration=(total/overall*100) if overall else 0
        return {"answer":"👥 Highest-Value Customers\n"+"\n".join(f"{i}. {n} — {money(v)}" for i,(n,v) in enumerate(tops,1))+f"\n\nTop 5 customer concentration: {pct(concentration)} of total sales."}
    if intent == "trend":
        tr=trend_result(df,s)
        if not tr["available"]: return {"answer": "📅 Monthly analysis unavailable: " + tr["message"] + " I won't substitute a KPI, category, or other analysis."}
        lines=["📈 Monthly Sales Trend", f"Overall change: {pct(tr['overall_growth'])}",
               f"Highest sales month: {tr['highest']['period']} — {money(tr['highest']['sales'])}",
               f"Lowest sales month: {tr['lowest']['period']} — {money(tr['lowest']['sales'])}"]
        for r in tr["monthly"]:
            g = r.get("growth_pct")
            growth_text = f" ({pct(g)})" if g is not None and np.isfinite(g) else ""
            lines.append(f"• {r['period']}: {money(r['sales'])}" + growth_text)
        if tr.get("biggest_increase"): lines.append(f"\nBiggest increase: {tr['biggest_increase']['period']} — {pct(tr['biggest_increase']['growth_pct'])}")
        if tr.get("biggest_decrease"): lines.append(f"Biggest decrease: {tr['biggest_decrease']['period']} — {pct(tr['biggest_decrease']['growth_pct'])}")
        chart={"title":"Monthly Sales Growth","type":"line","labels":[r["period"] for r in tr["monthly"]],"values":[float(r["sales"]) for r in tr["monthly"]],"label_column":"period","value_column":"sales"}
        # JSON cannot represent NaN/Infinity. The first period has no prior period, so use null.
        safe_monthly=[]
        for r in tr["monthly"]:
            rr=dict(r); g=rr.get("growth_pct")
            rr["growth_pct"] = None if g is None or not np.isfinite(g) else float(g)
            safe_monthly.append(rr)
        tr["monthly"]=safe_monthly
        return {"answer":"\n".join(lines),"trend":tr,"chart":chart,"intent":intent}
    if intent == "root_cause":
        tr=trend_result(df,s)
        if not tr["available"] or len(tr["monthly"])<2: return {"answer":"🔍 I need a usable date field with at least two periods to identify a sales decline and its drivers."}
        # Determine requested target month: explicit month/year, weakest month, or biggest decline.
        target=None
        if "weakest" in q or "lowest" in q or "worst" in q:
            target=tr["lowest"]["period"]
        elif "biggest decrease" in q or "biggest decline" in q:
            target=tr["biggest_decrease"]["period"] if tr.get("biggest_decrease") else None
        else:
            target=tr["biggest_decrease"]["period"] if tr.get("biggest_decrease") else tr["lowest"]["period"]
        months=tr["monthly"]; idx=next((i for i,r in enumerate(months) if r["period"]==target),len(months)-1)
        if idx==0: idx=1
        prev=months[idx-1]; cur=months[idx]
        change=float(cur["sales"]-prev["sales"]); change_pct=(change/prev["sales"]*100) if prev["sales"] else 0
        lines=["🔍 SALES ROOT-CAUSE ANALYSIS",f"Target period: {cur['period']}",f"Sales changed by {money(change)} ({pct(change_pct)}) vs {prev['period']}."]
        for label,key in [("Category","category"),("Region/City","region"),("Product","product")]:
            col=s[key] or (s["city"] if key=="region" else None)
            if not col: continue
            a=df.copy(); d=parse_dates(a,s["date"]); a["__d"]=d; a["__v"]=_num(a,s["sales"])
            a["__p"]=a["__d"].dt.to_period("M").astype(str); a=a.dropna(subset=["__p","__v"])
            g=a.groupby([col,"__p"])['__v'].sum().unstack(fill_value=0)
            if prev["period"] in g.columns and cur["period"] in g.columns:
                diff=(g[cur["period"]]-g[prev["period"]]).sort_values().head(3)
                if len(diff):
                    lines.append(f"• {label} drivers: "+", ".join(f"{n} ({money(v)})" for n,v in diff.items()))
        lines.append("• Priority: investigate the largest negative driver first, then review order volume, pricing, and cost changes.")
        return {"answer":"\n".join(lines),"intent":intent}
    if intent == "recommendation":
        tr=trend_result(df,s); lines=["🎯 ACTIONABLE BUSINESS RECOMMENDATIONS"]
        if tr.get("available") and tr.get("biggest_decrease"): lines.append(f"1. Investigate the biggest monthly decline in {tr['biggest_decrease']['period']} ({pct(tr['biggest_decrease']['growth_pct'])}).")
        tops=_top(df,s["category"],s["sales"],1)
        if tops: lines.append(f"2. Double down on {tops[0][0]}, the strongest sales category ({money(tops[0][1])}).")
        if s["profit"] and s["category"]:
            pt=_top(df,s["category"],s["profit"],1)
            if pt: lines.append(f"3. Protect {pt[0][0]}, the strongest profit category ({money(pt[0][1])}).")
        if s["customer"] and s["sales"]: lines.append("4. Retain the highest-value customers with targeted offers and repeat-purchase campaigns.")
        lines.append("5. Monitor sales, profit margin and the largest negative driver together each month.")
        return {"answer":"\n".join(lines),"intent":intent}
    if intent == "anomaly":
        lines=["🚨 ANOMALY CHECK"]
        for label,col in [("Sales",s["sales"]),("Profit",s["profit"]),("Quantity",s["quantity"])] :
            if not col: continue
            x=_num(df,col).dropna()
            if len(x)<4: continue
            q1,q3=x.quantile(.25),x.quantile(.75); iqr=q3-q1; lo=q1-1.5*iqr; hi=q3+1.5*iqr; n=int(((x<lo)|(x>hi)).sum())
            lines.append(f"• {label}: {n} anomalies ({n/len(x)*100:.2f}%), bounds {lo:,.2f} to {hi:,.2f}.")
        return {"answer":"\n".join(lines)}
    if intent == "forecast":
        tr=trend_result(df,s)
        if not tr.get("available") or len(tr["monthly"])<3: return {"answer":"I need at least three valid monthly periods to produce a meaningful forecast."}
        y=np.array([float(r["sales"]) for r in tr["monthly"]]); x=np.arange(len(y)); slope,intercept=np.polyfit(x,y,1); future=[]
        last_period=pd.Period(tr["monthly"][-1]["period"],freq="M")
        for i in range(1,4):
            val=max(0,float(intercept+slope*(len(y)-1+i))); future.append((str(last_period+i),val))
        lines=["🔮 SALES FORECAST", "Forecast is based on the historical monthly trend (linear trend baseline)."]+[f"• {p}: {money(v)}" for p,v in future]
        return {"answer":"\n".join(lines),"forecast":[{"period":p,"value":v} for p,v in future]}
    # General: answer useful context rather than saying unknown.
    return {"answer": _kpi_answer(df,s)+"\n\n💬 You can ask: 'sales?', 'top category?', 'worst city?', 'why did sales drop?', 'forecast next month', or 'what should I do?'"}
