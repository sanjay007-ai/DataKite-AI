# ============================================================
# 🔮 PHASE 6.6 — FORECASTING ENGINE
# ============================================================

import pandas as pd
import numpy as np


# ============================================================
# 6.6.1 — DETECT DATE COLUMN
# ============================================================

def detect_date_column(df):

    date_keywords = [
        "date",
        "order_date",
        "sales_date",
        "transaction_date",
        "invoice_date",
        "month"
    ]

    # Exact / keyword match
    for column in df.columns:

        column_lower = str(column).lower().strip()

        if column_lower in date_keywords:
            return column

    # Try date conversion
    for column in df.columns:

        try:
            converted = pd.to_datetime(
                df[column],
                errors="coerce"
            )

            if converted.notna().mean() >= 0.7:
                return column

        except Exception:
            continue

    return None


# ============================================================
# 6.6.2 — DETECT SALES COLUMN
# ============================================================

def detect_sales_column(df):

    sales_keywords = [
        "sales",
        "sale",
        "amount",
        "revenue",
        "net_sales",
        "order_amount",
        "total_sales",
        "price",
        "income"
    ]

    # Exact / keyword match
    for column in df.columns:

        column_lower = str(column).lower().strip()

        if column_lower in sales_keywords:
            return column

    # Partial match
    for column in df.columns:

        column_lower = str(column).lower().strip()

        for keyword in sales_keywords:

            if keyword in column_lower:
                return column

    # Numeric fallback
    numeric_columns = df.select_dtypes(
        include=np.number
    ).columns

    if len(numeric_columns) > 0:
        return numeric_columns[0]

    return None


# ============================================================
# 6.6.3 — FORECAST FUNCTION
# ============================================================

def forecast_sales(
    df,
    periods=6
):

    if df is None or df.empty:
        return {
            "error": "No data available for forecasting."
        }

    date_column = detect_date_column(df)
    sales_column = detect_sales_column(df)

    if not date_column:
        return {
            "error": "No date column detected."
        }

    if not sales_column:
        return {
            "error": "No sales/revenue column detected."
        }

    try:

        data = df[
            [date_column, sales_column]
        ].copy()

        data[date_column] = pd.to_datetime(
            data[date_column],
            errors="coerce"
        )

        data[sales_column] = pd.to_numeric(
            data[sales_column],
            errors="coerce"
        )

        data = data.dropna()

        if len(data) < 3:
            return {
                "error":
                    "At least 3 valid historical records are required."
            }

        # --------------------------------------------------------
        # Aggregate by date
        # --------------------------------------------------------

        daily_data = (
            data
            .groupby(date_column)[sales_column]
            .sum()
            .sort_index()
        )

        if len(daily_data) < 3:
            return {
                "error":
                    "Not enough historical dates for forecasting."
            }

        # --------------------------------------------------------
        # Convert dates into numeric time index
        # --------------------------------------------------------

        x = np.arange(
            len(daily_data),
            dtype=float
        )

        y = daily_data.values.astype(float)

        # --------------------------------------------------------
        # Linear trend
        # --------------------------------------------------------

        slope, intercept = np.polyfit(
            x,
            y,
            1
        )

        # Historical fitted values
        fitted_values = (
            intercept +
            slope * x
        )

        # --------------------------------------------------------
        # Forecast future periods
        # --------------------------------------------------------

        future_x = np.arange(
            len(daily_data),
            len(daily_data) + periods,
            dtype=float
        )

        forecast_values = (
            intercept +
            slope * future_x
        )

        # Sales cannot be negative
        forecast_values = np.maximum(
            forecast_values,
            0
        )

        # --------------------------------------------------------
        # Forecast dates
        # --------------------------------------------------------

        last_date = daily_data.index.max()

        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=periods,
            freq="D"
        )

        # --------------------------------------------------------
        # Trend
        # --------------------------------------------------------

        if slope > 0:
            trend = "Increasing"
        elif slope < 0:
            trend = "Decreasing"
        else:
            trend = "Stable"

        # --------------------------------------------------------
        # Historical average
        # --------------------------------------------------------

        historical_average = float(
            daily_data.mean()
        )

        forecast_average = float(
            np.mean(forecast_values)
        )

        # --------------------------------------------------------
        # Growth
        # --------------------------------------------------------

        if historical_average != 0:

            forecast_growth = (
                (
                    forecast_average -
                    historical_average
                )
                / historical_average
            ) * 100

        else:
            forecast_growth = 0

        # --------------------------------------------------------
        # MAE
        # --------------------------------------------------------

        mae = float(
            np.mean(
                np.abs(
                    y - fitted_values
                )
            )
        )

        # --------------------------------------------------------
        # Build forecast records
        # --------------------------------------------------------

        forecast_records = []

        for date, value in zip(
            future_dates,
            forecast_values
        ):

            forecast_records.append({
                "date": date.strftime("%Y-%m-%d"),
                "forecast_sales": round(
                    float(value),
                    2
                )
            })

        return {

            "date_column": date_column,

            "sales_column": sales_column,

            "historical_records":
                int(len(daily_data)),

            "historical_start":
                daily_data.index.min().strftime(
                    "%Y-%m-%d"
                ),

            "historical_end":
                daily_data.index.max().strftime(
                    "%Y-%m-%d"
                ),

            "historical_average":
                round(
                    historical_average,
                    2
                ),

            "forecast_average":
                round(
                    forecast_average,
                    2
                ),

            "forecast_growth":
                round(
                    float(forecast_growth),
                    2
                ),

            "trend":
                trend,

            "slope":
                round(
                    float(slope),
                    4
                ),

            "mae":
                round(
                    mae,
                    2
                ),

            "forecast_periods":
                int(periods),

            "forecast":
                forecast_records
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# 6.6.4 — FORMAT FORECAST SUMMARY
# ============================================================

def format_forecast_summary(result):

    if not result:
        return "❌ No forecasting result available."

    if result.get("error"):
        return (
            "❌ Forecasting error: "
            f"{result['error']}"
        )

    lines = []

    lines.append(
        "🔮 Forecast Analysis"
    )

    lines.append("")

    lines.append(
        f"📅 Historical Period: "
        f"{result['historical_start']} → "
        f"{result['historical_end']}"
    )

    lines.append(
        f"📊 Historical Records: "
        f"{result['historical_records']:,}"
    )

    lines.append(
        f"💰 Historical Average Sales: "
        f"₹{result['historical_average']:,.2f}"
    )

    lines.append(
        f"🔮 Forecast Average Sales: "
        f"₹{result['forecast_average']:,.2f}"
    )

    lines.append(
        f"📈 Forecast Trend: "
        f"{result['trend']}"
    )

    lines.append(
        f"📊 Expected Change: "
        f"{result['forecast_growth']:,.2f}%"
    )

    lines.append(
        f"🎯 Forecast Error (MAE): "
        f"₹{result['mae']:,.2f}"
    )

    lines.append("")

    lines.append(
        "🔮 Future Forecast:"
    )

    for item in result["forecast"]:

        lines.append(
            f"• {item['date']}: "
            f"₹{item['forecast_sales']:,.2f}"
        )

    return "\n".join(lines)


# ============================================================
# 6.6.5 — STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    test_data = pd.DataFrame({

        "Date": pd.date_range(
            "2026-01-01",
            periods=10,
            freq="D"
        ),

        "Sales": [
            1000,
            1100,
            1200,
            1300,
            1400,
            1500,
            1600,
            1700,
            1800,
            1900
        ]
    })

    result = forecast_sales(
        test_data,
        periods=5
    )

    print(
        format_forecast_summary(
            result
        )
    )