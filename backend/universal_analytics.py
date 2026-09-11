import re
import pandas as pd
from csv_reader import get_data, get_datasets


def _metric(df, kind="sales"):
    candidates = {
        "sales": ["Amount", "Sales", "Revenue", "Net Sales", "Turnover", "GMV"],
        "profit": ["Profit", "Net Profit", "Gross Profit"],
        "quantity": ["Quantity", "Qty", "Units"],
        "cost": ["Cost", "Total Cost", "Expense", "Expenses"],
    }[kind]
    for c in candidates:
        if c in df.columns:
            return c
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return numeric[0] if numeric else None


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _money(v): return f"₹{float(v):,.2f}"


def summary(df):
    sales = _metric(df, "sales")
    profit = _metric(df, "profit")
    quantity = _metric(df, "quantity")
    lines = ["📊 BUSINESS DATA SUMMARY", "", f"Records: {len(df):,}", f"Columns: {len(df.columns):,}"]
    if sales: lines.append(f"Total Sales / Revenue: {_money(_num(df[sales]).sum())}")
    if profit:
        p = _num(df[profit]).sum(); lines.append(f"Total Profit: {_money(p)}")
        if sales and _num(df[sales]).sum(): lines.append(f"Profit Margin: {p / _num(df[sales]).sum() * 100:.2f}%")
    if quantity: lines.append(f"Total Quantity / Units: {_num(df[quantity]).sum():,.0f}")
    lines.append(f"Numeric fields: {len(df.select_dtypes(include='number').columns)}")
    return "\n".join(lines)


def _top_dimension(df, keyword, descending=True):
    sales = _metric(df, "sales")
    if not sales: return None
    candidates = [c for c in df.columns if keyword in str(c).lower() and c != sales]
    if not candidates:
        candidates = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c]) and c not in ("Source_File",)]
    for c in candidates:
        if 1 < df[c].nunique(dropna=True) <= 500:
            g = df.groupby(c)[sales].sum().sort_values(ascending=not descending)
            if not g.empty: return c, g.index[0], float(g.iloc[0])
    return None


def _trend(df):
    sales = _metric(df, "sales")
    if not sales or "Order_Date" not in df.columns: return None
    d = pd.to_datetime(df["Order_Date"], errors="coerce")
    x = df.assign(__date=d).dropna(subset=["__date"])
    if x.empty: return None
    g = x.groupby(x["__date"].dt.to_period("M"))[sales].sum().sort_index()
    if len(g) < 2: return None
    prev, cur = float(g.iloc[-2]), float(g.iloc[-1])
    growth = ((cur-prev)/abs(prev)*100) if prev else 0
    return g, growth



def _orders_count(df):
    for c in ("Order_ID", "Order ID", "Order", "Invoice", "Transaction_ID", "Transaction ID"):
        if c in df.columns:
            return int(df[c].nunique(dropna=True))
    return int(len(df))


def _month_comparison(df, q):
    if "compare" not in q and not any(x in q for x in (" vs ", " versus ")):
        return None
    months = re.findall(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", q)
    if len(months) < 2:
        return None
    sales = _metric(df, "sales")
    if not sales or "Order_Date" not in df.columns:
        return "❌ I need a sales/revenue column and a date column to compare months."
    d = pd.to_datetime(df["Order_Date"], errors="coerce")
    x = df.assign(__date=d).dropna(subset=["__date"]).copy()
    month_num = {m.lower(): i for i, m in enumerate(pd.date_range("2000-01-01", periods=12, freq="MS").strftime("%B"), 1)}
    vals = {}
    for m in months[:2]:
        vals[m.title()] = float(_num(x.loc[x["__date"].dt.month.eq(month_num[m.lower()]), sales]).sum())
    a, b = list(vals.items())[:2]
    diff = b[1] - a[1]
    pct = (diff / abs(a[1]) * 100) if a[1] else 0
    direction = "increased" if diff > 0 else "decreased" if diff < 0 else "was unchanged"
    return (f"📅 Month Comparison\n\n{a[0]}: {_money(a[1])}\n{b[0]}: {_money(b[1])}\n\n"
            f"📈 Sales {direction} by {_money(abs(diff))} ({pct:+.2f}%) from {a[0]} to {b[0]}.")


def _multi_kpi(df, q):
    terms = sum(bool(x) for x in (
        "total sales" in q or "total revenue" in q or "overall sales" in q,
        "total profit" in q or "profit made" in q,
        "total cost" in q or "total expenses" in q or "total expense" in q,
        "orders" in q,
        "average order value" in q or "aov" in q,
        "profit margin" in q,
        "total quantity" in q or "quantity sold" in q or "units sold" in q,
    ))
    if terms < 2:
        return None
    sales = _metric(df, "sales"); profit = _metric(df, "profit"); cost = _metric(df, "cost"); qty = _metric(df, "quantity")
    lines = ["📊 BUSINESS KPI SUMMARY", ""]
    if sales: lines.append(f"💰 Total Sales / Revenue: {_money(_num(df[sales]).sum())}")
    if profit:
        p=float(_num(df[profit]).sum()); lines.append(f"📈 Total Profit: {_money(p)}")
        if sales:
            sv=float(_num(df[sales]).sum()); lines.append(f"📊 Profit Margin: {(p/sv*100 if sv else 0):.2f}%")
    if cost: lines.append(f"💸 Total Cost / Expenses: {_money(_num(df[cost]).sum())}")
    if "orders" in q: lines.append(f"🧾 Total Orders / Transactions: {_orders_count(df):,}")
    if qty: lines.append(f"📦 Total Quantity / Units: {_num(df[qty]).sum():,.0f}")
    if ("average order value" in q or "aov" in q) and sales:
        lines.append(f"🛒 Average Order Value: {_money(float(_num(df[sales]).sum()) / max(_orders_count(df), 1))}")
    return "\n".join(lines)

def answer_business_question(question):
    df = get_data()
    if df is None or df.empty:
        return None
    q = str(question).strip().lower()

    month_answer = _month_comparison(df, q)
    if month_answer:
        return month_answer

    multi = _multi_kpi(df, q)
    if multi:
        return multi

    if any(x in q for x in ("business summary", "overall summary", "executive summary", "summarize", "summary of")):
        return summary(df)
    if "total sales" in q or "total revenue" in q or "overall sales" in q or "overall revenue" in q:
        c = _metric(df, "sales"); return f"💰 Total Sales / Revenue: {_money(_num(df[c]).sum())}" if c else None
    if "total profit" in q or "profit made" in q:
        c = _metric(df, "profit"); return f"💰 Total Profit: {_money(_num(df[c]).sum())}" if c else None
    if "profit margin" in q or q == "margin":
        s,p = _metric(df,"sales"),_metric(df,"profit")
        if s and p and _num(df[s]).sum(): return f"📈 Profit Margin: {_num(df[p]).sum()/_num(df[s]).sum()*100:.2f}%"
    if "total cost" in q or "total expenses" in q or "total expense" in q:
        c=_metric(df,"cost"); return f"💸 Total Cost / Expenses: {_money(_num(df[c]).sum())}" if c else None
    if "total quantity" in q or "quantity sold" in q or "units sold" in q:
        c=_metric(df,"quantity"); return f"📦 Total Quantity / Units: {_num(df[c]).sum():,.0f}" if c else None
    if "how many rows" in q or "total rows" in q or "records" in q:
        return f"📄 The dataset contains {len(df):,} records across {len(df.columns):,} columns."
    if "how many columns" in q or "what are the columns" in q or "column names" in q:
        return "📑 Columns: " + ", ".join(map(str, df.columns))
    if "best" in q or "top" in q or "highest" in q:
        for key in ("product", "category", "city", "region", "department", "customer", "employee"):
            if key in q:
                hit=_top_dimension(df,key,True)
                if hit: return f"🏆 {hit[0]} with the highest sales: {hit[1]} — {_money(hit[2])}"
    if "worst" in q or "lowest" in q or "bottom" in q:
        for key in ("product", "category", "city", "region", "department", "customer", "employee"):
            if key in q:
                hit=_top_dimension(df,key,False)
                if hit: return f"⚠️ {hit[0]} with the lowest sales: {hit[1]} — {_money(hit[2])}"
    if any(x in q for x in ("why did", "why has", "what caused", "root cause", "sales drop", "sales decline", "sales decrease")):
        t=_trend(df)
        if t:
            g,growth=t
            direction="increased" if growth>0 else "decreased" if growth<0 else "was flat"
            lines=["🔍 SALES ROOT-CAUSE ANALYSIS", "", f"Latest monthly sales {direction} by {abs(growth):.2f}%."]
            # Identify dimensions contributing most to the latest-vs-previous change.
            sales=_metric(df,"sales")
            d=pd.to_datetime(df.get("Order_Date"),errors="coerce")
            x=df.assign(__date=d).dropna(subset=["__date"]).copy()
            periods=sorted(x["__date"].dt.to_period("M").dropna().unique())
            if len(periods)>=2:
                prev,cur=periods[-2],periods[-1]
                for col in [c for c in ("Category","Product","City","Region","Department","Customer") if c in x.columns][:3]:
                    a=x.loc[x["__date"].dt.to_period("M").eq(prev)].groupby(col)[sales].sum()
                    b=x.loc[x["__date"].dt.to_period("M").eq(cur)].groupby(col)[sales].sum()
                    common=a.index.intersection(b.index)
                    if len(common):
                        delta=(b.reindex(common,fill_value=0)-a.reindex(common,fill_value=0)).sort_values()
                        if len(delta):
                            worst=str(delta.index[0]); val=float(delta.iloc[0])
                            lines.append(f"• {col} driving the decline: {worst} ({_money(val)} change).")
                lines.append("• Review the declining segment, order volume, pricing, and costs in the latest period.")
            return "\n".join(lines)
        return "🔍 I need a usable date field with at least two periods to identify the sales decline and its likely drivers."

    if "trend" in q or "growth" in q:
        t=_trend(df)
        if t:
            g,growth=t
            direction="increased" if growth>0 else "decreased" if growth<0 else "was flat"
            return f"📈 The latest monthly sales {direction} by {abs(growth):.2f}%. Latest month: {_money(g.iloc[-1])}."
    if "risk" in q:
        t=_trend(df)
        return "⚠️ Business risks: monitor declining sales trends, low-profit areas, concentration in a small number of customers/products, and unusually high costs." + (f" Latest monthly growth is {t[1]:+.2f}%." if t else "")
    if "opportunit" in q:
        hit=_top_dimension(df,"product",True) or _top_dimension(df,"category",True)
        return (f"🚀 Opportunity: scale the strongest {hit[0].lower()} ({hit[1]}), while improving weaker segments." if hit else "🚀 Opportunity: focus investment on the highest-value measurable segments in the dataset.")
    if any(x in q for x in ("recommend", "suggest", "action plan", "what should")):
        return "🎯 Business Recommendations\n\n1. Double down on the highest-revenue segment.\n2. Investigate low-performing products/categories.\n3. Protect high-value customers with retention actions.\n4. Monitor monthly growth and cost trends.\n5. Use the dashboard filters to isolate underperforming periods or regions."
    return None
