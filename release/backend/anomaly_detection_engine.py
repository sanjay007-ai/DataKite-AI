# ============================================================
# 🚨 PHASE 6.5 — ANOMALY DETECTION ENGINE
# ============================================================

import pandas as pd
import numpy as np


def detect_anomalies(data):

    if data is None or data.empty:
        return {
            "error": "Dataset is empty."
        }

    try:

        numeric_df = data.select_dtypes(
            include=["number"]
        )

        if numeric_df.empty:
            return {
                "error": "No numeric columns found."
            }

        results = {}

        for column in numeric_df.columns:

            series = numeric_df[column].dropna()

            if len(series) < 4:
                continue

            # ------------------------------------------------
            # IQR method
            # ------------------------------------------------

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)

            iqr = q3 - q1

            lower_bound = q1 - (1.5 * iqr)
            upper_bound = q3 + (1.5 * iqr)

            anomaly_mask = (
                (series < lower_bound)
                | (series > upper_bound)
            )

            anomalies = series[anomaly_mask]

            high_anomalies = series[
                series > upper_bound
            ]

            low_anomalies = series[
                series < lower_bound
            ]

            results[column] = {

                "total_values": int(len(series)),

                "anomaly_count": int(
                    len(anomalies)
                ),

                "anomaly_percentage": float(
                    len(anomalies)
                    / len(series)
                    * 100
                ),

                "lower_bound": float(
                    lower_bound
                ),

                "upper_bound": float(
                    upper_bound
                ),

                "high_anomaly_count": int(
                    len(high_anomalies)
                ),

                "low_anomaly_count": int(
                    len(low_anomalies)
                ),

                "highest_anomaly": (
                    float(high_anomalies.max())
                    if not high_anomalies.empty
                    else None
                ),

                "lowest_anomaly": (
                    float(low_anomalies.min())
                    if not low_anomalies.empty
                    else None
                )
            }

        return {
            "success": True,
            "anomalies": results
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# 📋 FORMAT ANOMALY SUMMARY
# ============================================================

def format_anomaly_summary(result):

    if not result.get("success"):
        return (
            "❌ Anomaly detection failed: "
            f"{result.get('error', 'Unknown error')}"
        )

    anomalies = result.get(
        "anomalies",
        {}
    )

    if not anomalies:
        return (
            "✅ No numeric columns available "
            "for anomaly detection."
        )

    lines = []

    lines.append("🚨 Anomaly Detection")
    lines.append("")

    total_anomalies = 0

    for column, info in anomalies.items():

        count = info["anomaly_count"]

        total_anomalies += count

        lines.append(
            f"🔹 {column}"
        )

        lines.append(
            f"• Anomalies: {count:,}"
        )

        lines.append(
            f"• Anomaly Rate: "
            f"{info['anomaly_percentage']:.2f}%"
        )

        lines.append(
            f"• Lower Bound: "
            f"{info['lower_bound']:,.2f}"
        )

        lines.append(
            f"• Upper Bound: "
            f"{info['upper_bound']:,.2f}"
        )

        lines.append(
            f"• High Anomalies: "
            f"{info['high_anomaly_count']:,}"
        )

        lines.append(
            f"• Low Anomalies: "
            f"{info['low_anomaly_count']:,}"
        )

        if info["highest_anomaly"] is not None:

            lines.append(
                f"• Highest Anomaly: "
                f"{info['highest_anomaly']:,.2f}"
            )

        if info["lowest_anomaly"] is not None:

            lines.append(
                f"• Lowest Anomaly: "
                f"{info['lowest_anomaly']:,.2f}"
            )

        lines.append("")

    lines.append(
        f"🚨 Total Detected Anomalies: "
        f"{total_anomalies:,}"
    )

    return "\n".join(lines)


# ============================================================
# 🧪 TEST
# ============================================================

if __name__ == "__main__":

    test_data = pd.DataFrame({

        "Sales": [
            100, 110, 105, 115,
            108, 112, 109, 111,
            500
        ],

        "Profit": [
            20, 22, 21, 23,
            19, 24, 20, 22,
            150
        ],

        "Quantity": [
            2, 3, 2, 4,
            3, 2, 3, 4,
            25
        ]
    })

    result = detect_anomalies(
        test_data
    )

    print(
        format_anomaly_summary(
            result
        )
    )