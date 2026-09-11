import pandas as pd

data = None


def _normalize_business_columns(df):
    """Add canonical alias columns (Amount, Profit, Quantity, Customer,
    Product, City, Category, Payment, Status, Date, Month) that point at
    whatever the real uploaded column is named.

    Several routes in app.py (chart endpoints, /report/summary,
    /word/download, /ppt/download, /pdf/download) were written against one
    specific demo file's exact headers ("Amount", "Payment", "Status", ...)
    instead of the flexible schema detector already used by
    /excel/download. That meant any real uploaded
    file with different header names (e.g. "Sales" instead of "Amount")
    made those routes fail with "Missing columns: Amount" even though the
    data was perfectly usable — confirmed by actually running the server
    and testing every download route with a realistic dataset.
    This adds the expected columns as aliases (originals are kept intact)
    so every route works regardless of the source file's real headers.
    """
    from smart_analytics_engine import detect_schema

    s = detect_schema(df)
    alias_map = {
        "Amount": s.get("sales"),
        "Profit": s.get("profit"),
        "Quantity": s.get("quantity"),
        "Customer": s.get("customer"),
        "Product": s.get("product"),
        "City": s.get("city"),
        "Category": s.get("category"),
        "Date": s.get("date"),
    }
    for canon, src in alias_map.items():
        if src and src in df.columns and canon not in df.columns:
            df[canon] = df[src]

    def _find_like(fragments):
        for c in df.columns:
            key = str(c).strip().lower().replace(" ", "").replace("_", "")
            if any(frag in key for frag in fragments):
                return c
        return None

    if "Payment" not in df.columns:
        c = _find_like(["paymentmethod", "paymenttype", "payment"])
        if c:
            df["Payment"] = df[c]
    if "Status" not in df.columns:
        c = _find_like(["orderstatus", "deliverystatus", "status"])
        if c:
            df["Status"] = df[c]
    if "Month" not in df.columns and "Date" in df.columns:
        d = pd.to_datetime(df["Date"], errors="coerce")
        if d.notna().any():
            df["Month"] = d.dt.strftime("%b")
    return df


def set_data(df):
    """Store an already-parsed DataFrame without a CSV round-trip."""
    global data
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("No tabular data was supplied.")
    data = df.copy()
    data.columns = [str(c).strip() for c in data.columns]
    data = _normalize_business_columns(data)
    data = data.dropna(how="all").reset_index(drop=True)
    if data.empty or len(data.columns) == 0:
        raise ValueError("The uploaded data contains no usable rows or columns.")
    print("DataFrame Loaded Successfully!")
    print(data.columns)
    return data

def load_csv(file_path):
    return set_data(pd.read_csv(file_path))

def get_data():
    return data
