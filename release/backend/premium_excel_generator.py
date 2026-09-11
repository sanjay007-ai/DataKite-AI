from pathlib import Path
import math
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, DoughnutChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter, column_index_from_string
from openpyxl.worksheet.table import Table, TableStyleInfo


def _safe(v):
    return str(v).replace("'", "''")


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _find_col(df, aliases):
    by_norm = {_norm(c): c for c in df.columns}
    for a in aliases:
        if _norm(a) in by_norm:
            return by_norm[_norm(a)]
    for c in df.columns:
        n = _norm(c)
        if any(_norm(a) in n or n in _norm(a) for a in aliases):
            return c
    return None


def _schema(df):
    return {
        "sales": _find_col(df, ["amount", "sales", "revenue", "net sales", "order amount", "total amount", "value", "turnover"]),
        "profit": _find_col(df, ["profit", "net profit", "gross profit", "profit amount"]),
        "cost": _find_col(df, ["cost", "total cost", "cogs", "expense", "expenses"]),
        "order": _find_col(df, ["order id", "orderid", "transaction id", "transaction", "invoice id", "invoice"]),
        "customer": _find_col(df, ["customer", "customer id", "client", "client id", "buyer", "user id", "user"]),
        "date": _find_col(df, ["date", "order date", "sales date", "transaction date", "invoice date", "created at", "timestamp", "datetime"]),
        "category": _find_col(df, ["category", "subcategory", "department", "segment", "food category"]),
        "city": _find_col(df, ["city", "town", "location", "store city"]),
        "region": _find_col(df, ["region", "state", "province", "area", "territory", "country"]),
        "product": _find_col(df, ["product", "product name", "item", "item name", "sku"]),
    }


def _num_series(df, col):
    if not col or col not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _filter_candidates(df, s):
    preferred = [s.get("region"), s.get("city"), s.get("category")]
    fallback = []
    for c in df.columns:
        if c in preferred or c in {s.get("sales"), s.get("profit"), s.get("cost"), s.get("order"), s.get("customer"), s.get("date")}:
            continue
        if not (pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c])):
            continue
        n = int(df[c].nunique(dropna=True))
        if 1 < n <= 30:
            fallback.append(c)
    out = []
    for c in preferred + fallback:
        if c and c in df.columns and c not in out:
            n = int(df[c].nunique(dropna=True))
            if 1 < n <= 30:
                out.append(c)
        if len(out) == 3:
            break
    while len(out) < 3:
        out.append(None)
    return out


def _values(df, col):
    if not col:
        return ["All"]
    vals = sorted({str(v) for v in df[col].dropna().tolist() if str(v).strip() != ""})
    return ["All"] + vals


def _range(sheet, col_letter, start_row, end_row):
    return f"'{sheet}'!${col_letter}${start_row}:${col_letter}${end_row}"


def _condition(filter_cell, raw_range):
    return f'--((({filter_cell}="All")+({raw_range}={filter_cell}))>0)'


def _sum_formula(raw_sheet, value_range, filter_specs):
    terms = [value_range]
    for cell, rng in filter_specs:
        terms.append(_condition(cell, rng))
    return "=SUMPRODUCT(" + ",".join(terms) + ")"


def _count_formula(raw_sheet, filter_specs, count_range=None):
    terms = []
    if count_range:
        terms.append(f"--({count_range}<>\"\")")
    else:
        terms.append("--(ROW('Raw Data'!$A$2:$A$20001)>0)")
    for cell, rng in filter_specs:
        terms.append(_condition(cell, rng))
    return "=SUMPRODUCT(" + ",".join(terms) + ")"


def _unique_formula(raw_col, filter_specs):
    # IMPORTANT: this deliberately avoids UNIQUE()/FILTER(). openpyxl writes
    # formula text as-is, but Excel's dynamic-array functions must be stored
    # internally with an "_xlfn." prefix (e.g. "_xlfn.UNIQUE") or the cell
    # errors out with #NAME?/#VALUE! when opened — in real Excel, not only
    # here. That was the cause of Orders/Customers always reading 0.
    # SUMPRODUCT + COUNTIFS is supported by every Excel version (2007+) and
    # LibreOffice, and gives a correct filter-aware distinct count:
    # each matching row contributes 1/(number of matching rows sharing its
    # ID), which sums to exactly the count of distinct IDs.
    countifs_args = [raw_col, raw_col]
    for cell, rng in filter_specs:
        countifs_args.append(rng)
        countifs_args.append(f'IF({cell}="All","*",{cell})')
    countifs = "COUNTIFS(" + ",".join(countifs_args) + ")"
    mask = "*".join(_condition(cell, rng) for cell, rng in filter_specs) if filter_specs else "1"
    numerator = f'(({mask})*({raw_col}<>""))'
    return f'=SUMPRODUCT(IFERROR({numerator}/{countifs},0))'


def build_premium_excel(data: pd.DataFrame, out_path):
    df = data.copy()
    df.columns = [str(c).strip() for c in df.columns]
    s = _schema(df)
    filters = _filter_candidates(df, s)

    wb = Workbook()
    dash = wb.active
    dash.title = "Dashboard"
    raw = wb.create_sheet("Raw Data")
    lists = wb.create_sheet("Filter Lists")
    charts = wb.create_sheet("Chart Data")
    insights = wb.create_sheet("Insights & Recommendations")

    # Light, card-based SaaS-dashboard palette (mirrors the reference design:
    # soft grey canvas, white cards, colored icon chips, dark text) instead
    # of the old flat dark panels.
    C = {"bg":"EEF2F6","card":"FFFFFF","teal":"14B8A6","orange":"F97316","cyan":"38BDF8",
         "purple":"A78BFA","green":"22C55E","red":"EF4444","yellow":"F5B92E",
         "ink":"0F172A","muted":"64748B","white":"FFFFFF"}
    thin = Side(style="thin", color="E2E8F0")
    accent = Side(style="medium", color=C["teal"])
    icon_glyph = {"TOTAL SALES":"$","TOTAL PROFIT":"^","TOTAL COST":"~","ORDERS":"#","CUSTOMERS":"@","AOV":"=","MARGIN":"%"}

    # Raw data
    raw.append(list(df.columns))
    for row in df.itertuples(index=False, name=None):
        raw.append(list(row))
    raw.freeze_panes = "A2"
    raw.auto_filter.ref = raw.dimensions
    raw.sheet_view.showGridLines = False
    for cell in raw[1]:
        cell.fill = PatternFill("solid", fgColor=C["teal"])
        cell.font = Font(bold=True, color=C["white"])
    if raw.max_row > 1:
        ref = f"A1:{get_column_letter(raw.max_column)}{raw.max_row}"
        tab = Table(displayName="BusinessData", ref=ref)
        tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False)
        raw.add_table(tab)

    # Filter list values
    for i, col in enumerate(filters, 1):
        letter = get_column_letter(i)
        lists.cell(1, i).value = col or f"Filter {i}"
        lists.cell(1, i).font = Font(bold=True, color=C["white"])
        for r, v in enumerate(_values(df, col), 2):
            lists.cell(r, i).value = v
    lists.sheet_state = "hidden"

    # Raw column references
    col_letter = {c: get_column_letter(i + 1) for i, c in enumerate(df.columns)}
    end = max(len(df) + 1, 2)
    filter_specs = []
    # NOTE: fully sheet-qualified so these refs stay correct wherever the
    # formula is written (Dashboard, Chart Data, etc). Bare "A5" style refs
    # silently pointed at the *current* sheet's A5 instead of Dashboard's,
    # which is why every chart used to show zero data regardless of filter.
    filter_cells = ["Dashboard!$A$5", "Dashboard!$E$5", "Dashboard!$I$5"]
    for idx, c in enumerate(filters):
        if c:
            filter_specs.append((filter_cells[idx], _range("Raw Data", col_letter[c], 2, end)))

    sales_col = s.get("sales")
    profit_col = s.get("profit")
    cost_col = s.get("cost")
    order_col = s.get("order")
    customer_col = s.get("customer")

    def fill_range(rng, color):
        for row in dash[rng]:
            for cell in row:
                cell.fill = PatternFill("solid", fgColor=color)

    def border_range(rng, side):
        cells = list(dash[rng])
        nrows = len(cells); ncols = len(cells[0])
        for r, row in enumerate(cells):
            for c, cell in enumerate(row):
                cell.border = Border(
                    left=side if c == 0 else None,
                    right=side if c == ncols - 1 else None,
                    top=side if r == 0 else None,
                    bottom=side if r == nrows - 1 else None,
                )

    # Dashboard background: soft light canvas with white cards (matches a
    # standard SaaS-style analytics dashboard rather than a flat dark sheet).
    for row in dash.iter_rows(min_row=1, max_row=42, min_col=1, max_col=16):
        for cell in row:
            cell.fill = PatternFill("solid", fgColor=C["bg"])
    dash.sheet_view.showGridLines = False
    dash.merge_cells("A1:P2")
    fill_range("A1:P2", C["teal"])
    dash["A1"] = "AI BUSINESS ANALYTICS"
    dash["A1"].font = Font(size=22, bold=True, color=C["white"])
    dash["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    dash["A3"] = "Executive dashboard • filters update every KPI and chart below"
    dash["A3"].font = Font(size=10, italic=True, color=C["muted"])

    # Filters — rendered as light "chip" cards with a teal accent edge,
    # similar to the filter pills in the reference dashboards.
    filter_titles = [filters[0] or "Filter 1", filters[1] or "Filter 2", filters[2] or "Filter 3"]
    for i, (title, cell) in enumerate(zip(filter_titles, filter_cells)):
        base = [1, 5, 9][i]
        dash.cell(4, base).value = f"FILTER • {str(title).upper()}"
        dash.cell(4, base).font = Font(size=9, bold=True, color=C["muted"])
        rng = f"{get_column_letter(base)}5:{get_column_letter(base+1)}5"
        dash.merge_cells(rng)
        fill_range(rng, C["card"])
        border_range(rng, thin)
        fc = dash.cell(5, base)
        fc.value = "All"
        fc.font = Font(size=11, bold=True, color=C["ink"])
        fc.border = Border(left=Side(style="thick", color=C["teal"]))
        fc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        list_col = get_column_letter(i + 1)
        max_list = max(2, len(_values(df, filters[i])) + 1)
        dv = DataValidation(type="list", formula1=f"='Filter Lists'!${list_col}$2:${list_col}${max_list}", allow_blank=False)
        dv.error = "Choose a value from the dropdown."
        dv.errorTitle = "Invalid filter"
        dv.prompt = "Select a filter value"
        dv.promptTitle = "Dashboard filter"
        dash.add_data_validation(dv)
        dv.add(fc)
    dash["M4"] = "TIP"
    dash["M4"].font = Font(size=9, bold=True, color=C["muted"])
    dash["M5"] = "Pick a value to filter everything"
    dash["M5"].font = Font(size=10, color=C["muted"])

    # KPI formulas
    def money_formula(col):
        if not col:
            return '=0'
        return _sum_formula("Raw Data", _range("Raw Data", col_letter[col], 2, end), filter_specs)

    sales_formula = money_formula(sales_col)
    profit_formula = money_formula(profit_col)
    if cost_col:
        cost_formula = money_formula(cost_col)
    else:
        cost_formula = "=A9-C9"
    if order_col:
        orders_formula = _unique_formula(_range("Raw Data", col_letter[order_col], 2, end), filter_specs)
    else:
        orders_formula = _count_formula("Raw Data", filter_specs)
    if customer_col:
        customers_formula = _unique_formula(_range("Raw Data", col_letter[customer_col], 2, end), filter_specs)
    else:
        customers_formula = _count_formula("Raw Data", filter_specs)

    # Each KPI is a small "card": a colored icon chip on top, then the
    # label, then the big value — mirroring the icon+figure KPI tiles in
    # the reference dashboards instead of the old flat colored-border boxes.
    cards = [
        ("TOTAL SALES", sales_formula, "A", C["teal"], "₹#,##0.00", "$"),
        ("TOTAL PROFIT", profit_formula, "C", C["green"], "₹#,##0.00", "^"),
        ("TOTAL COST", cost_formula, "E", C["orange"], "₹#,##0.00", "~"),
        ("ORDERS", orders_formula, "G", C["cyan"], "#,##0", "#"),
        ("CUSTOMERS", customers_formula, "I", C["purple"], "#,##0", "@"),
        ("AOV", "=IFERROR(A9/G9,0)", "K", C["yellow"], "₹#,##0.00", "="),
        ("MARGIN", "=IFERROR(C9/A9,0)", "M", C["teal"], "0.00%", "%"),
    ]
    for label, formula, col0, accent_color, fmt, glyph in cards:
        col1 = get_column_letter(column_index_from_string(col0) + 1)
        icon_rng = f"{col0}7:{col1}7"
        label_cell = f"{col0}8"
        value_cell = f"{col0}9"
        dash.merge_cells(icon_rng)
        fill_range(icon_rng, accent_color)
        ic = dash[f"{col0}7"]
        ic.value = glyph
        ic.font = Font(size=13, bold=True, color=C["white"])
        ic.alignment = Alignment(horizontal="center", vertical="center")
        card_rng = f"{col0}8:{col1}9"
        fill_range(card_rng, C["card"])
        border_range(f"{col0}7:{col1}9", thin)
        dash[label_cell] = label
        dash[label_cell].font = Font(size=9, bold=True, color=C["muted"])
        dash[label_cell].alignment = Alignment(horizontal="left", vertical="center", indent=1)
        dash[value_cell] = formula
        dash[value_cell].font = Font(size=15, bold=True, color=C["ink"])
        dash[value_cell].number_format = fmt
        dash[value_cell].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    dash.merge_cells("A11:N11")
    dash["A11"] = "INTERACTIVE ANALYSIS"
    dash["A11"].font = Font(size=11, bold=True, color=C["teal"])

    # Chart data: category, geo, product, monthly. Values are filter-aware.
    charts.sheet_view.showGridLines = False
    charts.append(["Category", "Sales"])
    chart_group_cols = [s.get("category"), s.get("region") or s.get("city"), s.get("product")]
    for block, group_col in enumerate(chart_group_cols):
        start = 1 + block * 2
        if not group_col:
            continue
        charts.cell(1, start).value = group_col
        charts.cell(1, start + 1).value = "Sales"
        vals = sorted({str(v) for v in df[group_col].dropna().tolist()})[:20]
        for r, v in enumerate(vals, 2):
            charts.cell(r, start).value = v
            group_rng = _range("Raw Data", col_letter[group_col], 2, end)
            sales_rng = _range("Raw Data", col_letter[sales_col], 2, end) if sales_col else _range("Raw Data", get_column_letter(1), 2, end)
            conds = [f"--({group_rng}={charts.cell(r,start).coordinate})"] + [_condition(cell, rng) for cell, rng in filter_specs]
            charts.cell(r, start + 1).value = "=SUMPRODUCT(" + ",".join([sales_rng] + conds) + ")"
            charts.cell(r, start + 1).number_format = "₹#,##0.00"

    # Monthly data using real month/date values calculated in Python, while sales remain filter-aware where possible.
    month_col = s.get("date")
    month_rows = []
    if month_col:
        parsed = pd.to_datetime(df[month_col], errors="coerce")
        if parsed.notna().sum() > 0:
            month_rows = sorted(parsed.dropna().dt.to_period("M").astype(str).unique())
    if not month_rows:
        mcol = _find_col(df, ["month", "period", "sales month", "order month"])
        if mcol:
            month_rows = sorted({str(v) for v in df[mcol].dropna().tolist()})
    if month_rows:
        start = 7
        charts.cell(1, start).value = "Month"
        charts.cell(1, start + 1).value = "Sales"
        for r, period in enumerate(month_rows, 2):
            charts.cell(r, start).value = period
            if month_col:
                rng = _range("Raw Data", col_letter[month_col], 2, end)
                sales_rng = _range("Raw Data", col_letter[sales_col], 2, end) if sales_col else _range("Raw Data", get_column_letter(1), 2, end)
                # SUMPRODUCT over month prefix YYYY-MM; works for Excel date cells and text dates.
                conds = [f"--(TEXT({rng},\"yyyy-mm\")={charts.cell(r,start).coordinate})"] + [_condition(cell, rr) for cell, rr in filter_specs]
                charts.cell(r, start + 1).value = "=SUMPRODUCT(" + ",".join([sales_rng] + conds) + ")"
            else:
                charts.cell(r, start + 1).value = 0
            charts.cell(r, start + 1).number_format = "₹#,##0.00"

    # Charts on dashboard. Category/Product stay as bar charts; Region/City
    # is rendered as a donut (mirrors the "All Expenses" donut-breakdown
    # tile in the reference dashboard) instead of a third bar chart.
    bar_specs = [("Category Sales", 2, 1, "A13"), ("Product Sales", 6, 5, "A28")]
    donut_specs = [("Sales by Region / City", 4, 3, "H13")]
    donut_colors = [C["teal"], C["orange"], C["cyan"], C["purple"], C["green"], C["yellow"], C["red"]]
    for title, val_col, cat_col, anchor in bar_specs:
        if charts.cell(1, cat_col).value and charts.max_row >= 2:
            ch = BarChart(); ch.type = "col"; ch.style = 10; ch.title = title; ch.height = 7; ch.width = 12
            ch.add_data(Reference(charts, min_col=val_col, min_row=1, max_row=min(charts.max_row, 11)), titles_from_data=True)
            ch.set_categories(Reference(charts, min_col=cat_col, min_row=2, max_row=min(charts.max_row, 11)))
            if ch.series:
                ch.series[0].graphicalProperties.solidFill = C["teal"]
            dash.add_chart(ch, anchor)
    for title, val_col, cat_col, anchor in donut_specs:
        if charts.cell(1, cat_col).value and charts.max_row >= 2:
            ch = DoughnutChart(); ch.title = title; ch.height = 7; ch.width = 12; ch.holeSize = 55
            data_ref = Reference(charts, min_col=val_col, min_row=1, max_row=min(charts.max_row, 8))
            cats_ref = Reference(charts, min_col=cat_col, min_row=2, max_row=min(charts.max_row, 8))
            ch.add_data(data_ref, titles_from_data=True)
            ch.set_categories(cats_ref)
            if ch.series:
                from openpyxl.chart.marker import DataPoint
                pts = []
                for i in range(min(charts.max_row - 1, 7)):
                    dp = DataPoint(idx=i)
                    dp.graphicalProperties.solidFill = donut_colors[i % len(donut_colors)]
                    pts.append(dp)
                ch.series[0].data_points = pts
            dash.add_chart(ch, anchor)
    if month_rows:
        ch = LineChart(); ch.style = 13; ch.title = "Monthly Sales Trend"; ch.height = 7; ch.width = 12
        ch.add_data(Reference(charts, min_col=8, min_row=1, max_row=min(charts.max_row, len(month_rows)+1)), titles_from_data=True)
        ch.set_categories(Reference(charts, min_col=7, min_row=2, max_row=min(charts.max_row, len(month_rows)+1)))
        if ch.series:
            ch.series[0].graphicalProperties.line.solidFill = C["teal"]
            ch.series[0].graphicalProperties.line.width = 25000
            ch.series[0].smooth = True
        dash.add_chart(ch, "H28")

    # Product analysis / insights.
    product_sheet = wb.create_sheet("Product Analysis")
    product_sheet.append([s.get("product") or "Product", "Sales"])
    if s.get("product") and sales_col:
        top = df.groupby(s["product"])[sales_col].apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()).sort_values(ascending=False).head(20)
        for k, v in top.items():
            product_sheet.append([str(k), float(v)])
            product_sheet.cell(product_sheet.max_row, 2).number_format = "₹#,##0.00"

    insights.append(["Business Insights & Recommendations"])
    insights.append(["Active filters", "See Dashboard filter cells"])
    if s.get("category") and sales_col:
        g = df.groupby(s["category"])[sales_col].apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()).sort_values(ascending=False)
        if not g.empty: insights.append(["Top category", f"{g.index[0]} — ₹{g.iloc[0]:,.2f}"])
    geo = s.get("region") or s.get("city")
    if geo and sales_col:
        g = df.groupby(geo)[sales_col].apply(lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum()).sort_values(ascending=False)
        if not g.empty: insights.append(["Top region/city", f"{g.index[0]} — ₹{g.iloc[0]:,.2f}"])
    insights.append([])
    insights.append(["Recommended Actions"])
    insights.append(["Use the dashboard dropdown filters to isolate segments before comparing KPIs."])
    insights.append(["Compare profit margin with sales growth before scaling promotions or discounts."])
    insights.append(["Investigate the weakest category/region and its operational drivers."])

    # Formatting all sheets.
    for sh in wb.worksheets:
        sh.sheet_view.showGridLines = False
        sh.freeze_panes = "A2"
        for col_cells in sh.columns:
            vals = [str(c.value) if c.value is not None else "" for c in col_cells]
            width = min(max(max((len(v) for v in vals), default=10) + 2, 12), 34)
            sh.column_dimensions[get_column_letter(col_cells[0].column)].width = width
        if sh.max_row >= 1:
            for c in sh[1]:
                c.font = Font(bold=True, color=C["white"])
                c.fill = PatternFill("solid", fgColor=C["teal"])
    dash.freeze_panes = "A12"
    for r in range(1, 41):
        dash.row_dimensions[r].height = 22
    dash.row_dimensions[1].height = 28
    dash.row_dimensions[2].height = 28
    dash.row_dimensions[5].height = 28
    dash.column_dimensions["A"].width = 18
    # Widened from 15 -> 18: at 15 the bold 16pt KPI currency values (e.g. large
    # or negative Profit/Cost totals) overflowed and Excel/Calc displayed "###"
    # instead of the number.
    for col in "BCDEFGHIJKLMNOP": dash.column_dimensions[col].width = 18
    charts.sheet_state = "hidden"

    # Fit the dashboard to one page width when printed/exported to PDF,
    # so all seven KPI cards and both chart rows are visible together
    # instead of being cut off mid-card at the default page width.
    dash.page_setup.orientation = "landscape"
    dash.page_setup.fitToWidth = 1
    dash.page_setup.fitToHeight = 0
    dash.sheet_properties.pageSetUpPr.fitToPage = True
    dash.print_area = "A1:P40"

    # Make Excel recalculate formulas on open.
    try:
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"
    except Exception:
        pass

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out
