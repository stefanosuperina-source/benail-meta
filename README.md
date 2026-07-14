# benail-meta

SEO metadata audit for benail: meta titles, meta descriptions, and meta keywords.

## Overview
This repository runs rule-based metadata audits and can be extended to call an LLM ("Grok") to provide a review of meta titles/descriptions/keywords for specific product pages or product group pages.

The repository already includes a GitHub Actions workflow (shown below) that runs a weekly read-only audit. To enable LLM-based reviews (Grok), you'll need to add your Grok API key as a repository secret and pass it into the workflow or into your runtime environment when running locally.

---

## Where to add the Grok API key
1. In the GitHub repository, go to: Settings > Secrets and variables > Actions > New repository secret.
2. Add a secret named: `GROK_API_KEY` with the value of your Grok API key.

In code or in workflows, read the key from the environment variable `GROK_API_KEY`.

---

## Workflow: pass the secret into Actions
Edit your workflow step that runs the audit to include the Grok env var. In your workflow (the current README shows the existing workflow) change the `Run audit` step's `env` to include `GROK_API_KEY`:

```yaml
      - name: Run audit
        env:
          PRESTASHOP_URL: ${{ secrets.PRESTASHOP_URL }}
          PRESTASHOP_API_KEY: ${{ secrets.PRESTASHOP_API_KEY }}
          GROK_API_KEY: ${{ secrets.GROK_API_KEY }}
        run: python -m src.main audit
```

If you want the workflow to run a Grok-based review for a specific product or group on manual dispatch, you can add inputs to `workflow_dispatch` and pass them into the command. Example `workflow_dispatch` snippet:

```yaml
on:
  workflow_dispatch:
    inputs:
      target_url:
        description: 'Product or product group URL to review'
        required: false
      target_group_id:
        description: 'Product group id to review'
        required: false
```

Then use those inputs in the `Run audit` step (example only — you'll need to implement CLI flags in the Python code to accept them):

```yaml
        run: |
          if [[ -n "${{ github.event.inputs.target_url }}" ]]; then
            python -m src.main review --url "${{ github.event.inputs.target_url }}"
          elif [[ -n "${{ github.event.inputs.target_group_id }}" ]]; then
            python -m src.main review --group-id "${{ github.event.inputs.target_group_id }}"
          else
            python -m src.main audit
          fi
```

---

## Running locally
1. Export env vars locally:

```bash
export PRESTASHOP_URL="https://your-shop.example"
export PRESTASHOP_API_KEY="your_prestashop_key"
export GROK_API_KEY="your_grok_key"
```

2. Run the script for a single product (if your code supports it):

```bash
python -m src.main review --url "https://your-shop.example/product/123"
# or
python -m src.main review --group-id 456
```

If the CLI `review` command does not exist yet, you'll need to add an entry point in `src/main.py` to accept `--url` or `--group-id` and call the review logic.

---

## Example: how to call Grok from Python (template)
Below is a template showing how your code could call an LLM-style Grok HTTP API. Replace the endpoint URL and request format with the provider's exact API spec.

```python
# example: src/grok_client.py
import os
import requests

GROK_API_KEY = os.environ.get("GROK_API_KEY")
GROK_ENDPOINT = "https://api.grok.example/v1/generate"  # replace with real endpoint

def ask_grok(prompt: str, max_tokens: int = 512) -> str:
    if not GROK_API_KEY:
        raise RuntimeError("GROK_API_KEY not set in environment")
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "prompt": prompt,
        "max_tokens": max_tokens,
    }
    resp = requests.post(GROK_ENDPOINT, json=data, headers=headers, timeout=30)
    resp.raise_for_status()
    j = resp.json()
    # Adjust parsing depending on provider's response schema
    return j.get("text") or j.get("result") or str(j)
```

When doing a meta review, build a clear prompt with the product URL, the current meta title/description/keywords, and any constraints (tone, length, keyword targets), then call ask_grok(prompt).

---

## What I changed in this README
- Added instructions for adding a `GROK_API_KEY` secret.
- Showed where to pass the secret into the GitHub Actions workflow.
- Added examples for manual workflow_dispatch inputs to target a specific product URL or group ID.
- Included a template Python client showing how to call a Grok-style HTTP API.

---

## Next steps I can take for you
- If you want, I can update the workflow file in .github/workflows to pass the secret and add the dispatch inputs (and adjust the run step). I can also add the `src/grok_client.py` file and a `review` CLI command in `src/main.py` to implement the product / group review flow — tell me if you want me to create those changes and whether you prefer a particular Grok API endpoint or SDK.


---

Below is the repository's existing workflow (kept for reference):

```yaml
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
```
