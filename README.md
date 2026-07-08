name: Weekly metadata audit (read-only)

# Runs the rule-based audit only (no LLM calls, no publishing) and uploads
# the report as a workflow artifact for review. Safe to enable without
# review since it never writes back to the shop.

on:
  workflow_dispatch: {}
  schedule:
    - cron: "0 6 * * 1"  # every Monday 06:00 UTC

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run audit
        env:
          PRESTASHOP_URL: ${{ secrets.PRESTASHOP_URL }}
          PRESTASHOP_API_KEY: ${{ secrets.PRESTASHOP_API_KEY }}
        run: python -m src.main audit

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: metadata-audit-report
          path: reports/audit_only_*.csv
