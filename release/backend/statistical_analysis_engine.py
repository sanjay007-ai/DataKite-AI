# ============================================================
# 📊 PHASE 6.3 — STATISTICAL ANALYSIS ENGINE
# ============================================================

import pandas as pd
import numpy as np


def statistical_analysis(df):
    """
    Perform automatic statistical analysis on a dataset.
    """

    if df is None or df.empty:
        return {
            "error": "Dataset is empty."
        }

    try:

        # ----------------------------------------------------
        # Numeric columns
        # ----------------------------------------------------

        numeric_df = df.select_dtypes(
            include=["number"]
        )

        if numeric_df.empty:
            return {
                "error": "No numeric columns found for statistical analysis."
            }

        statistics = {}

        # ----------------------------------------------------
        # Analyze each numeric column
        # ----------------------------------------------------

        for column in numeric_df.columns:

            series = numeric_df[column].dropna()

            if series.empty:
                continue

            mean_value = float(series.mean())
            median_value = float(series.median())
            std_value = float(series.std())
            variance_value = float(series.var())

            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))

            minimum = float(series.min())
            maximum = float(series.max())

            # Coefficient of Variation
            if mean_value != 0:
                coefficient_variation = (
                    std_value / abs(mean_value)
                ) * 100
            else:
                coefficient_variation = 0

            # Skewness
            skewness = float(series.skew())

            statistics[column] = {
                "count": int(series.count()),
                "mean": mean_value,
                "median": median_value,
                "standard_deviation": std_value,
                "variance": variance_value,
                "minimum": minimum,
                "maximum": maximum,
                "q1": q1,
                "q3": q3,
                "iqr": q3 - q1,
                "coefficient_variation": coefficient_variation,
                "skewness": skewness
            }

        # ----------------------------------------------------
        # Correlation analysis
        # ----------------------------------------------------

        correlations = {}

        if len(numeric_df.columns) >= 2:

            correlation_matrix = numeric_df.corr()

            for column in correlation_matrix.columns:

                correlations[column] = {}

                for other_column in correlation_matrix.columns:

                    value = correlation_matrix.loc[
                        column,
                        other_column
                    ]

                    if pd.notna(value):
                        correlations[column][other_column] = float(
                            value
                        )

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        return {
            "success": True,
            "numeric_columns": list(numeric_df.columns),
            "statistics": statistics,
            "correlations": correlations
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# 📊 HUMAN-READABLE STATISTICAL SUMMARY
# ============================================================

def format_statistical_summary(result):

    if not result.get("success"):
        return (
            "❌ Statistical analysis failed: "
            f"{result.get('error', 'Unknown error')}"
        )

    statistics = result.get("statistics", {})

    if not statistics:
        return "❌ No statistical information available."

    lines = []

    lines.append("📊 Statistical Analysis")
    lines.append("")

    for column, stats in statistics.items():

        lines.append(f"🔹 {column}")

        lines.append(
            f"• Count: {stats['count']:,}"
        )

        lines.append(
            f"• Mean: {stats['mean']:,.2f}"
        )

        lines.append(
            f"• Median: {stats['median']:,.2f}"
        )

        lines.append(
            f"• Standard Deviation: "
            f"{stats['standard_deviation']:,.2f}"
        )

        lines.append(
            f"• Variance: "
            f"{stats['variance']:,.2f}"
        )

        lines.append(
            f"• Minimum: "
            f"{stats['minimum']:,.2f}"
        )

        lines.append(
            f"• Maximum: "
            f"{stats['maximum']:,.2f}"
        )

        lines.append(
            f"• Q1: {stats['q1']:,.2f}"
        )

        lines.append(
            f"• Q3: {stats['q3']:,.2f}"
        )

        lines.append(
            f"• IQR: {stats['iqr']:,.2f}"
        )

        lines.append(
            f"• Variation: "
            f"{stats['coefficient_variation']:.2f}%"
        )

        lines.append(
            f"• Skewness: "
            f"{stats['skewness']:.2f}"
        )

        lines.append("")

    return "\n".join(lines)
    
if __name__ == "__main__":

    test_data = pd.DataFrame({
        "Sales": [100, 200, 300, 400, 500],
        "Profit": [20, 40, 60, 80, 100],
        "Quantity": [2, 4, 6, 8, 10]
    })

    result = statistical_analysis(test_data)

    print(
        format_statistical_summary(result)
    )    