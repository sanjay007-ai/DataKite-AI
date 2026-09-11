import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

# ============================================================
# 🔥 PHASE 5.8 — BACKEND TESTING
# ============================================================

from advanced_comparison_engine import advanced_compare_files
from root_cause_engine import root_cause_years
from business_recommendation_engine import business_recommendations_years


def run_engine_test(name, function, *args):

    print("\n" + "=" * 60)
    print(f"🧪 TEST: {name}")
    print("=" * 60)

    try:

        result = function(*args)

        if result is None:
            print("❌ FAILED — Returned None")
            return False

        print("✅ PASSED")
        print("Result preview:")
        print(str(result)[:500])

        return True

    except Exception as error:

        print("❌ FAILED")
        print("Error:", repr(error))

        return False


def main():

    print("\n🔥 PHASE 5.8 — FULL BACKEND TESTING\n")

    results = []

    # --------------------------------------------------------
    # 1. ADVANCED COMPARISON
    # --------------------------------------------------------

    results.append(
        run_engine_test(
            "Advanced Comparison 2024 vs 2025",
            advanced_compare_files,
            "2024",
            "2025"
        )
    )

    # --------------------------------------------------------
    # 2. ROOT CAUSE
    # --------------------------------------------------------

    results.append(
        run_engine_test(
            "Root Cause 2024 vs 2025",
            root_cause_years,
            "2024",
            "2025"
        )
    )

    # --------------------------------------------------------
    # 3. BUSINESS RECOMMENDATIONS
    # --------------------------------------------------------

    results.append(
        run_engine_test(
            "Business Recommendations 2024 vs 2025",
            business_recommendations_years,
            "2024",
            "2025"
        )
    )

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print("📊 PHASE 5.8 TEST SUMMARY")
    print("=" * 60)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:

        print(
            "\n🎉 PHASE 5 TESTING PASSED"
        )

        print(
            "✅ Advanced Comparison"
            "\n✅ Root Cause Engine"
            "\n✅ Business Recommendation Engine"
        )

        print(
            "\n🚀 PHASE 5 BACKEND IS READY"
        )

    else:

        print(
            "\n⚠️ SOME TESTS FAILED"
        )

        print(
            "Check the error shown above."
        )


if __name__ == "__main__":
    main()