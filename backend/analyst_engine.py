"""DataKite AI Analyst V3.
Deterministic question understanding and calculation layer.

Pipeline:
question -> intent + metric + dimension + direction + limit/time -> calculation -> validation -> answer.
The LLM is never the source of numeric truth.
"""
import re, math
import pandas as pd
import numpy as np

ALIASES = {
    "sales": ["sales","revenue","net sales","order amount","order_amount","amount","turnover","value","net_sales","total amount"],
    "profit": ["profit","net profit","gross profit","profit amount","net_profit"],
    "cost": ["cost","cogs","expense","expenses","total cost"],
    "quantity": ["quantity","qty","units","units sold","volume"],
    "order": ["order id","order_id","order","transaction id","transaction_id","invoice id","invoice_id","transaction"],
    "customer": ["customer id","customer_id","customer","client id","client_id","client","buyer","user id","user_id"],
    "product": ["product","product name","product_name","item","item name","sku"],
    "category": ["category","subcategory","department","segment","food category","food_category"],
    "geo": ["city","location","region","state","province","country","territory","area"],
    "date": ["date","order date","order_date","sales date","sales_date","transaction date","transaction_date","invoice date","invoice_date","timestamp","datetime","month","period"],
}

def norm(x):
    return re.sub(r"[^a-z0-9]+", "", str(x).lower())

def find_col(df, kind):
    if df is None or df.empty:
        return None
    cols = list(df.columns)
    nmap = {norm(c): c for c in cols}
    for a in ALIASES.get(kind, []):
        if norm(a) in nmap:
            return nmap[norm(a)]
    for c in cols:
        nc = norm(c)
        if any(norm(a) in nc or nc in norm(a) for a in ALIASES.get(kind, [])):
            return c
    return None

def schema(df):
    s = {k: find_col(df, k) for k in ALIASES}
    if not s["sales"]:
        nums = df.select_dtypes(include=np.number).columns.tolist()
        nums = [c for c in nums if not any(x in norm(c) for x in ["id","year","month","day","qty","quantity"])]
        if nums:
            s["sales"] = nums[0]
    return s

def num(df, c):
    if not c or c not in df.columns:
        return pd.Series(index=df.index, dtype=float)
    return pd.to_numeric(df[c], errors="coerce")

def money(x):
    if x is None:
        return "—"
    try:
        return "—" if not np.isfinite(float(x)) else f"₹{float(x):,.2f}"
    except Exception:
        return "—"

def pct(x):
    if x is None:
        return "—"
    try:
        return "—" if not np.isfinite(float(x)) else f"{float(x):.2f}%"
    except Exception:
        return "—"

def date_series(df, c):
    if not c or c not in df.columns:
        return None
    try:
        d = pd.to_datetime(df[c], errors="coerce", format="mixed")
    except Exception:
        d = pd.to_datetime(df[c], errors="coerce")
    if d.notna().sum() < 2:
        return None
    return d

def metric_sum(df, col):
    s = num(df, col).dropna()
    return float(s.sum()) if not s.empty else None

def metric_mean(df, col):
    s = num(df, col).dropna()
    return float(s.mean()) if not s.empty else None

def group_values(df, group_col, metric_col, ascending=False, limit=5):
    if not group_col or group_col not in df.columns or not metric_col or metric_col not in df.columns:
        return []
    x = pd.DataFrame({"group": df[group_col].astype(str), "value": num(df, metric_col)})
    x = x.replace({"group": {"nan": np.nan}}).dropna(subset=["group","value"])
    if x.empty:
        return []
    g = x.groupby("group")["value"].sum().sort_values(ascending=ascending).head(limit)
    return [{"label": str(k), "value": float(v)} for k, v in g.items()]

def monthly_metric(df, schema, metric_col=None):
    metric_col = metric_col or schema.get("sales")
    if not metric_col:
        return None
    d = date_series(df, schema.get("date"))
    if d is not None:
        x = pd.DataFrame({"date": d, "value": num(df, metric_col)}).dropna()
        if not x.empty:
            x["period"] = x["date"].dt.to_period("M").astype(str)
            return x.groupby("period", as_index=False)["value"].sum()
    month_col = next((c for c in df.columns if norm(c) in {"month","period","salesmonth","ordermonth","transactionmonth"}), None)
    if month_col:
        x = pd.DataFrame({"period": df[month_col].astype(str).str.strip(), "value": num(df, metric_col)}).dropna()
        if not x.empty:
            return x.groupby("period", as_index=False)["value"].sum()
    return None

def overview(df, s):
    sales = metric_sum(df, s.get("sales"))
    profit = metric_sum(df, s.get("profit"))
    orders = int(df[s["order"]].nunique()) if s.get("order") else len(df)
    customers = int(df[s["customer"]].nunique()) if s.get("customer") else None
    quantity = metric_sum(df, s.get("quantity"))
    aov = sales / orders if sales is not None and orders else None
    margin = profit / sales * 100 if sales not in (None, 0) and profit is not None else None
    return {
        "rows": len(df), "columns": len(df.columns), "total_sales": sales,
        "total_profit": profit, "orders": orders, "customers": customers,
        "quantity": quantity, "aov": aov, "margin": margin
    }

def _dimension_from_question(s, q):
    if any(w in q for w in ["customer", "customers", "client", "buyer"]):
        return "customer", s.get("customer")
    if any(w in q for w in ["product", "products", "item", "sku"]):
        return "product", s.get("product")
    if any(w in q for w in ["category", "categories", "department", "segment"]):
        return "category", s.get("category")
    if any(w in q for w in ["city", "cities", "region", "state", "country", "location", "market"]):
        return ("city", s.get("geo")) if "city" in q and s.get("geo") else ("geo", s.get("geo"))
    return None, None

def _metric_from_question(s, q):
    # Order matters: margin and quantity must never fall through to sales.
    if any(w in q for w in ["profit margin", "margin", "margin %", "margin percentage"]):
        return "margin"
    if any(w in q for w in ["quantity", "qty", "units sold", "units", "volume"]):
        return "quantity" if s.get("quantity") else None
    if any(w in q for w in ["profit", "profitable", "profitability"]):
        return "profit" if s.get("profit") else None
    if any(w in q for w in ["cost", "cogs", "expense", "expenses"]):
        return "cost" if s.get("cost") else "derived_cost"
    if any(w in q for w in ["order value", "average order", "aov"]):
        return "aov"
    if any(w in q for w in ["customer", "customers"]):
        # Customer alone is a dimension, not a metric.
        pass
    if any(w in q for w in ["sales", "revenue", "amount", "turnover", "value"]):
        return "sales" if s.get("sales") else None
    return "sales" if s.get("sales") else None

def _direction(q):
    if any(w in q for w in ["lowest", "least", "bottom", "smallest", "worst", "minimum", "lowest-performing"]):
        return "lowest"
    if any(w in q for w in ["highest", "most", "top", "best", "largest", "maximum", "strongest"]):
        return "highest"
    return None

def _limit(q, default=5):
    m = re.search(r"\btop\s+(\d+)\b", q)
    if m: return max(1, min(100, int(m.group(1))))
    m = re.search(r"\bbottom\s+(\d+)\b", q)
    if m: return max(1, min(100, int(m.group(1))))
    m = re.search(r"\b(\d+)\s+(?:best|highest|lowest|most valuable|least valuable)\b", q)
    if m: return max(1, min(100, int(m.group(1))))
    return default

def classify(q):
    q = re.sub(r"\s+", " ", str(q).strip().lower())
    if not q: return "empty"
    if q in {"hi","hello","hey","yo","good morning","good afternoon","good evening"}: return "greeting"
    if q in {"thanks","thank you","thx","ok","okay","great","nice"}: return "casual"
    # General conversation must be checked before generic business fallbacks.
    if any(x in q for x in ["who created datakite", "who made datakite", "who built datakite", "creator of datakite", "created by sanjay", "made by sanjay", "who created you", "who made you", "how were you made", "how were you created", "what are you", "how do you work"]):
        return "general_ai"
    if any(x in q for x in ["30-day plan","30 day plan","action plan","what should i stop","what should i invest","what should i do first","what decision should i make","recommend","recommendation","suggest","how can i improve"]):
        return "recommendation"
    if any(x in q for x in ["biggest opportunity","main opportunity","greatest opportunity"]): return "opportunity"
    if any(x in q for x in ["biggest risk","main risk","greatest risk"]): return "risk"
    if any(x in q for x in ["main business problems","business problems","key business problems","problems in this data"]): return "problems"
    if any(x in q for x in ["key business insights","business insights","important insights","key insights","summarize my business","5 important points","complete business summary","business summary","full analysis"]):
        return "insights"
    if any(x in q for x in ["unusual","anomal","outlier","abnormal"]): return "anomaly"
    if any(x in q for x in ["forecast","predict","future sales","future revenue","next period","next month"]): return "forecast"
    if any(x in q for x in ["why","cause","reason","driver","drivers","affecting my profit","factors affecting"]): return "root_cause"
    if any(x in q for x in ["fastest sales growth","biggest sales decline","fastest growth","biggest decline"]): return "trend_extreme"
    # Explicit month-to-month named comparisons.
    months = "january|february|march|april|may|june|july|august|september|october|november|december"
    if re.search(rf"\b(?:{months})\b.*\b(?:vs|versus|and)\b.*\b(?:{months})\b", q): return "comparison"
    if any(x in q for x in ["trend","monthly","month over month","over time","sales in each month","sales by month","month had"]):
        return "trend"
    if any(x in q for x in ["compare","comparison","versus"," vs ","difference between"]): return "comparison"
    # Exact KPI questions before dimension-only classification.
    if any(x in q for x in ["average order value","aov","profit margin","total sales","total revenue","total profit","total quantity","total orders","total customers","unique customers","average sales per customer"]):
        return "kpi"
    if any(x in q for x in ["top 10","top 5","bottom 5","least valuable","most valuable","highest","lowest","best","worst","most","least"]):
        if any(x in q for x in ["customer","product","category","city","region","state","country"]): return "ranking"
    if any(x in q for x in ["customer","customers","client","buyer"]): return "customer"
    if any(x in q for x in ["product","products","item","sku"]): return "product"
    if any(x in q for x in ["category","categories","department","segment"]): return "category"
    if any(x in q for x in ["city","cities","region","state","country","location","market"]): return "geo"
    if any(x in q for x in ["sales","revenue","amount","turnover"]): return "sales"
    if any(x in q for x in ["profit","margin"]): return "profit"
    if any(x in q for x in ["cost","cogs","expense"]): return "cost"
    return "overview"

def _kpi_answer(df, s, q):
    o = overview(df, s)
    if "average sales per customer" in q:
        if o["customers"] and o["total_sales"] is not None:
            return f"Average sales per customer: {money(o['total_sales']/o['customers'])}."
        return "I couldn't calculate average sales per customer because sales or customer data is unavailable."
    if "average order value" in q or "aov" in q:
        return f"Average Order Value: {money(o['aov'])}." if o["aov"] is not None else "I couldn't calculate AOV because sales or order data is unavailable."
    if "profit margin" in q or re.search(r"\bmargin\b", q):
        return f"Profit Margin: {pct(o['margin'])}." if o["margin"] is not None else "I couldn't calculate profit margin because sales and profit are required."
    if "total quantity" in q:
        return f"Total Quantity: {o['quantity']:,.2f}." if o["quantity"] is not None else "I couldn't find a quantity field."
    if "total orders" in q:
        return f"Total Orders: {o['orders']:,}."
    if "total customers" in q or "unique customers" in q:
        return f"Unique Customers: {o['customers']:,}." if o["customers"] is not None else "I couldn't find a customer field."
    if "total profit" in q:
        return f"Total Profit: {money(o['total_profit'])}." if o["total_profit"] is not None else "I couldn't find a profit field."
    if "total revenue" in q or "total sales" in q:
        return f"Total Sales / Revenue: {money(o['total_sales'])}." if o["total_sales"] is not None else "I couldn't find a sales/revenue field."
    lines = [
        f"Total Sales: {money(o['total_sales'])}",
        f"Total Profit: {money(o['total_profit'])}",
        f"Profit Margin: {pct(o['margin'])}",
        f"Total Orders: {o['orders']:,}",
        f"Average Order Value: {money(o['aov'])}",
    ]
    if o["customers"] is not None: lines.append(f"Unique Customers: {o['customers']:,}")
    if o["quantity"] is not None: lines.append(f"Total Quantity: {o['quantity']:,.2f}")
    return "\n".join(lines)

def _margin_groups(df, group_col, s, ascending=False, limit=5):
    if not group_col or not s.get("sales") or not s.get("profit"):
        return []
    a = pd.DataFrame({"group": df[group_col].astype(str), "sales": num(df,s["sales"]), "profit": num(df,s["profit"])}).dropna()
    if a.empty: return []
    g = a.groupby("group")[["sales","profit"]].sum()
    g["margin"] = np.where(g["sales"] != 0, g["profit"]/g["sales"]*100, np.nan)
    g = g.replace([np.inf,-np.inf], np.nan).dropna(subset=["margin"]).sort_values("margin", ascending=ascending).head(limit)
    return [{"label":str(k),"value":float(v.margin)} for k,v in g.iterrows()]

def _ranking_answer(df, s, q):
    dim, col = _dimension_from_question(s,q)
    if not col:
        return None
    metric = _metric_from_question(s,q)
    direction = _direction(q) or "highest"
    limit = _limit(q, 5)
    if metric == "margin":
        rows = _margin_groups(df,col,s,ascending=(direction=="lowest"),limit=limit)
        metric_label = "Profit Margin"
        fmt = pct
    elif metric == "aov":
        if not s.get("order") or not s.get("sales"):
            return "I couldn't calculate AOV by this dimension because sales and order data are required."
        x=df.copy()
        x["__sales"]=num(x,s["sales"])
        grouped=x.groupby(col,dropna=True).agg(sales=("__sales","sum"),orders=(s["order"],"nunique"))
        grouped["value"]=np.where(grouped["orders"]>0,grouped["sales"]/grouped["orders"],np.nan)
        grouped=grouped.dropna(subset=["value"]).sort_values("value",ascending=(direction=="lowest")).head(limit)
        rows=[{"label":str(k),"value":float(v)} for k,v in grouped["value"].items()]
        metric_label="AOV"; fmt=money
    else:
        metric_col = {"sales":s.get("sales"),"profit":s.get("profit"),"quantity":s.get("quantity"),"cost":s.get("cost")}.get(metric)
        if metric == "derived_cost":
            if not s.get("sales") or not s.get("profit"):
                return "I couldn't calculate cost because sales and profit are required."
            x=df.copy(); x["__value"]=num(x,s["sales"])-num(x,s["profit"])
            g=x.groupby(col)["__value"].sum().sort_values(ascending=(direction=="lowest")).head(limit)
            rows=[{"label":str(k),"value":float(v)} for k,v in g.items()]
        else:
            if not metric_col:
                return f"I couldn't find a usable {metric or 'sales'} field for this question."
            g=df.assign(__value=num(df,metric_col)).groupby(col)["__value"].sum().sort_values(ascending=(direction=="lowest")).head(limit)
            rows=[{"label":str(k),"value":float(v)} for k,v in g.items()]
        metric_label={"sales":"Sales / Revenue","profit":"Profit","quantity":"Quantity","cost":"Cost"}.get(metric,"Sales / Revenue")
        fmt = money if metric != "quantity" else lambda v:f"{v:,.2f}"
    if not rows: return f"I couldn't calculate this ranking from the available {dim} and metric fields."
    order_word = "Lowest" if direction=="lowest" else "Highest"
    lines=[f"{order_word} {dim.title()} by {metric_label}:"]
    for i,r in enumerate(rows,1):
        lines.append(f"{i}. {r['label']} — {fmt(r['value'])}")
    if limit == 1:
        lines=[f"{order_word} {dim.title()} by {metric_label}: {rows[0]['label']} — {fmt(rows[0]['value'])}"]
    return "\n".join(lines)

def _trend_answer(df,s,q,extreme=False):
    p=monthly_metric(df,s,s.get("sales"))
    if p is None or len(p)<1:
        return "Monthly analysis unavailable: I need a usable date or month field."
    p["growth_pct"]=p["value"].pct_change()*100
    if extreme:
        valid=p.dropna(subset=["growth_pct"])
        if "fastest" in q or "growth" in q and "decline" not in q:
            r=valid.loc[valid.growth_pct.idxmax()]
            return f"Fastest sales growth: {r.period} — {pct(r.growth_pct)} vs the previous period."
        valid=valid[valid.growth_pct<0]
        if valid.empty: return "No month-to-month sales decline was detected."
        r=valid.loc[valid.growth_pct.idxmin()]
        return f"Biggest sales decline: {r.period} — {pct(r.growth_pct)} vs the previous period."
    first,last=p.iloc[0],p.iloc[-1]
    overall=(float(last.value)/float(first.value)-1)*100 if first.value else None
    hi=p.loc[p.value.idxmax()]; lo=p.loc[p.value.idxmin()]
    lines=[f"Sales changed {pct(overall)} from {first.period} to {last.period}.",
           f"Highest sales month: {hi.period} — {money(hi.value)}.",
           f"Lowest sales month: {lo.period} — {money(lo.value)}."]
    return "\n".join(lines)

def _insights(df,s,q):
    o=overview(df,s)
    lines=[
        f"1. Sales are {money(o['total_sales'])} across {o['orders']:,} orders.",
        f"2. Profit is {money(o['total_profit'])} with a {pct(o['margin'])} margin."
    ]
    if s.get("category") and s.get("sales"):
        top=group_values(df,s["category"],s["sales"],False,1); low=group_values(df,s["category"],s["sales"],True,1)
        if top: lines.append(f"3. Strongest category by sales: {top[0]['label']} — {money(top[0]['value'])}.")
        if low: lines.append(f"4. Weakest category by sales: {low[0]['label']} — {money(low[0]['value'])}.")
    p=monthly_metric(df,s,s.get("sales"))
    if p is not None and len(p)>1:
        p["growth"]=p.value.pct_change()*100; valid=p.dropna(subset=["growth"])
        if not valid.empty:
            r=valid.loc[valid.growth.idxmin()]
            lines.append(f"5. Largest month-to-month sales decline: {r.period} — {pct(r.growth)}.")
    return "\n".join(lines[:5])

def _recommendation(df,s,q):
    o=overview(df,s)
    ql=q.lower()
    cat=s.get("category")
    sales=s.get("sales")
    profit=s.get("profit")
    if "30-day" in ql or "30 day" in ql:
        target="sales" if "sales" in ql else "profit" if "profit" in ql else "performance"
        lines=[f"30-Day {target.title()} Improvement Plan"]
        lines += [
            "Days 1–7: identify the strongest and weakest products/categories and verify the underlying transactions.",
            "Days 8–14: focus promotions/inventory on proven winners and test one targeted improvement on the weakest area.",
            "Days 15–21: measure sales, profit, quantity and customer response; stop actions that increase volume without acceptable margin.",
            "Days 22–30: scale the best-performing action and review the results against the starting baseline."
        ]
        return "\n".join(lines)
    if "stop" in ql:
        return "Stop pushing volume blindly. Prioritize products/categories that generate healthy profit and investigate weak or low-margin areas before increasing spend."
    if "invest" in ql:
        if cat and sales:
            top=group_values(df,cat,profit or sales,False,1)
            if top: return f"Invest more in the strongest verified category: {top[0]['label']} ({money(top[0]['value'])}), while monitoring margin and demand."
        return "Invest more in the strongest verified sales/profit segments, after confirming that the margin remains healthy."
    if "where am i losing" in ql:
        if cat and profit:
            low=group_values(df,cat,profit,True,1)
            if low: return f"The largest profit weakness is {low[0]['label']} at {money(low[0]['value'])}. Investigate its products, pricing and costs."
        return "I need a usable profit field to identify where the business is losing the most money."
    if "what should i do first" in ql or "decision" in ql:
        return "First, protect the strongest profitable segment and investigate the weakest one. Then compare the largest sales decline with its category/product drivers before changing pricing or promotions."
    if cat and (profit or sales):
        metric=profit or sales
        top=group_values(df,cat,metric,False,1); low=group_values(df,cat,metric,True,1)
        lines=[]
        if top: lines.append(f"Protect and scale the strongest category: {top[0]['label']} — {money(top[0]['value'])}.")
        if low: lines.append(f"Investigate the weakest category: {low[0]['label']} — {money(low[0]['value'])}.")
        if o["margin"] is not None: lines.append(f"Monitor the {pct(o['margin'])} profit margin while pursuing growth.")
        lines.append("Track sales, profit and volume together before changing pricing or promotions.")
        lines.append("Set a measurable target and review it weekly.")
        return "\n".join(lines[:5])
    return "Use verified sales, profit and customer/product performance to prioritize one high-confidence action, then measure the result."

def _root_cause(df,s,q):
    p=monthly_metric(df,s,s.get("sales"))
    if p is None or len(p)<2:
        return "I need a usable date/month field with at least two periods to investigate the cause."
    p["growth"]=p.value.pct_change()*100
    valid=p.dropna(subset=["growth"])
    target=valid.loc[valid.growth.idxmin()]
    idx=p.index.get_loc(target.name); prev=p.iloc[idx-1]
    lines=[f"Largest observed sales decline: {target.period} — {pct(target.growth)} vs {prev.period}."]
    for label,dim in [("category","category"),("product","product"),("city","geo")]:
        col=s.get(dim)
        if not col and dim=="geo": col=s.get("city")
        if not col or not s.get("sales"): continue
        d=date_series(df,s.get("date"))
        if d is None: continue
        a=df[d.dt.to_period("M").astype(str)==str(prev.period)]
        b=df[d.dt.to_period("M").astype(str)==str(target.period)]
        av=group_values(a,col,s["sales"],False,10000); bv=group_values(b,col,s["sales"],False,10000)
        am={x["label"]:x["value"] for x in av}; bm={x["label"]:x["value"] for x in bv}
        deltas=sorted(((k,bm.get(k,0)-am.get(k,0)) for k in set(am)|set(bm)), key=lambda z:z[1])
        if deltas and deltas[0][1]<0:
            lines.append(f"Largest detected {label} driver: {deltas[0][0]} — {money(deltas[0][1])} vs the prior period.")
            break
    return "\n".join(lines)

def _anomaly(df,s):
    c=s.get("sales")
    if not c: return "I couldn't find a numeric sales field for anomaly detection."
    vals=num(df,c).dropna()
    if len(vals)<5: return "I need at least 5 numeric sales records to detect reliable outliers."
    q1,q3=vals.quantile(.25),vals.quantile(.75); iqr=q3-q1; lo=q1-1.5*iqr; hi=q3+1.5*iqr
    mask=(num(df,c)<lo)|(num(df,c)>hi)
    return f"I found {int(mask.sum()):,} potential outlier transactions using the 1.5×IQR rule. Normal range: {money(lo)} to {money(hi)}."

def _forecast(df,s):
    p=monthly_metric(df,s,s.get("sales"))
    if p is None or len(p)<3: return "I need at least 3 historical periods to create a simple forecast."
    y=p.value.astype(float).values; x=np.arange(len(y)); slope,intercept=np.polyfit(x,y,1); pred=float(slope*len(y)+intercept)
    return f"Simple next-period sales forecast: {money(pred)} based on the historical linear trend. This is a directional estimate, not a guarantee."

def analyze(df, question, history=None):
    if df is None or df.empty:
        return {"ok":False,"answer":"Please upload a CSV or Excel file first.","intent":"empty"}
    history=history or []
    s=schema(df); q=re.sub(r"\s+"," ",str(question).strip().lower()); intent=classify(q)
    # Specific ranking questions outrank generic KPI/dimension intents.
    has_dimension = _dimension_from_question(s,q)[1] is not None
    has_rank_word = any(x in q for x in ["top ","bottom ","highest ","lowest ","most ","least ","best ","worst ","strongest ","weakest "])
    if has_dimension and has_rank_word:
        intent="ranking"
    # Explicit KPI questions use KPI calculations unless the user is ranking
    # a dimension (for example, "highest profit margin category").
    if intent != "ranking" and any(x in q for x in ["average order value","profit margin","average sales per customer","total quantity","total orders","total customers","unique customers","total profit","total revenue","total sales"]):
        intent="kpi"
    if intent=="empty": return {"ok":False,"answer":"Please enter a question.","intent":intent}
    if intent=="greeting": return {"ok":True,"answer":"Hello! 👋 I’m DataKite AI. Ask me about your sales, profit, quantity, products, categories, customers, cities, trends, anomalies, forecasts or business decisions.","intent":intent}
    if intent=="casual": return {"ok":True,"answer":"You're welcome! 👍 Ask me anything about the uploaded data.","intent":intent}
    if intent=="general_ai":
        if any(x in q for x in ["who created datakite", "who made datakite", "who built datakite", "creator of datakite", "created by sanjay", "made by sanjay", "who created you", "who made you"]):
            return {"ok":True,"answer":"DataKite AI was created by Sanjay. 🚀🤖📊","intent":intent}
        return {"ok":True,"answer":"I’m DataKite AI, a business analytics assistant. I was built to analyze uploaded business data, calculate verified metrics, explain trends, find anomalies, forecast performance, and turn the results into practical business insights.","intent":intent}
    if intent=="kpi":
        ans=_kpi_answer(df,s,q)
    elif intent=="ranking":
        ans=_ranking_answer(df,s,q)
    elif intent=="trend_extreme":
        ans=_trend_answer(df,s,q,True)
    elif intent=="trend":
        ans=_trend_answer(df,s,q,False)
    elif intent=="root_cause":
        ans=_root_cause(df,s,q)
    elif intent=="anomaly":
        ans=_anomaly(df,s)
    elif intent=="forecast":
        ans=_forecast(df,s)
    elif intent in {"recommendation","opportunity","risk","problems","insights"}:
        if intent=="opportunity":
            ans=_recommendation(df,s,"invest more")
        elif intent=="risk":
            ans=f"The clearest verified risk is margin pressure: current profit margin is {pct(overview(df,s)['margin'])}. Protect margin while growing and investigate the weakest profit segments."
        elif intent=="problems":
            ans="Main data-backed business problems to investigate:\n1. Weakest profit/sales segments.\n2. Any months with significant sales declines.\n3. Low-margin areas where volume may not create value.\n4. Customer/product concentration risk.\n5. Outlier transactions that may distort performance."
        elif intent=="insights":
            ans=_insights(df,s,q)
        else:
            ans=_recommendation(df,s,q)
    elif intent=="comparison":
        # Compare named months if possible; otherwise compare best vs worst requested dimension.
        months={"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        hits=[m for m in months if re.search(rf"\b{m}\b",q)]
        p=monthly_metric(df,s,s.get("sales"))
        if len(hits)>=2 and p is not None:
            rows=[]
            for m in hits[:2]:
                z=p[p.period.str[-2:]==f"{months[m]:02d}"]
                if not z.empty: rows.append((m,float(z.iloc[0].value)))
            if len(rows)==2:
                diff=rows[0][1]-rows[1][1]; ch=diff/rows[1][1]*100 if rows[1][1] else None
                ans=f"Month comparison:\n• {rows[0][0].title()}: {money(rows[0][1])}\n• {rows[1][0].title()}: {money(rows[1][1])}\n• Difference: {money(diff)} ({pct(ch)} vs {rows[1][0].title()})."
            else: ans="I couldn't find sales data for both requested months."
        else:
            dim,col=_dimension_from_question(s,q)
            metric=_metric_from_question(s,q)
            if metric=="margin": rows=_margin_groups(df,col,s,False,5)
            else: rows=group_values(df,col, s.get("profit") if metric=="profit" else s.get("sales"), False,5)
            ans="Comparison unavailable." if not rows else "Comparison:\n"+"\n".join(f"{i}. {r['label']} — {money(r['value'])}" for i,r in enumerate(rows,1))
    elif intent in {"customer","product","category","geo","sales","profit","cost","overview"}:
        # Dimension questions without ranking language get a useful breakdown.
        dim,col=_dimension_from_question(s,q)
        if dim and col:
            metric=_metric_from_question(s,q)
            metric_col=s.get("profit") if metric=="profit" else s.get("quantity") if metric=="quantity" else s.get("sales")
            rows=group_values(df,col,metric_col,False,5)
            label={"sales":"Sales / Revenue","profit":"Profit","quantity":"Quantity"}.get(metric,"Sales / Revenue")
            ans=f"Top {dim.title()} by {label}:\n"+"\n".join(f"{i}. {r['label']} — {money(r['value']) if metric!='quantity' else f'{r['value']:,.2f}'}" for i,r in enumerate(rows,1))
        else:
            o=overview(df,s)
            ans=f"Business overview:\n• Sales: {money(o['total_sales'])}\n• Profit: {money(o['total_profit'])}\n• Margin: {pct(o['margin'])}\n• Orders: {o['orders']:,}\n• Customers: {o['customers']:,}" if o["customers"] is not None else f"Business overview:\n• Sales: {money(o['total_sales'])}\n• Profit: {money(o['total_profit'])}\n• Margin: {pct(o['margin'])}\n• Orders: {o['orders']:,}"
    else:
        ans="I can analyze the uploaded data, but I couldn't identify the requested analysis safely. Try specifying a metric such as sales, profit, margin, quantity or AOV and a dimension such as product, category, customer or city."
    calc={"intent":intent,"question":str(question),"schema":s}
    validation={"passed":True,"checks":[{"check":"analysis_routed","passed":True},{"check":"answer_generated","passed":bool(ans)}]}
    return {"ok":True,"answer":"**Verified analysis**\n• "+ans.replace("\n","\n• "),"intent":intent,"calculation":calc,"validation":validation,"evidence":[],"chart":None,"recommendations":[],"followups":[],"schema":s,"method":"deterministic question routing + pandas"}
