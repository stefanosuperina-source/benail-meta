import os
import sys
import csv
import datetime
import click
import pandas as pd
from dotenv import load_dotenv

from src.ecommerce_client import get_client
from src.audit import audit_product, flag_cross_product_duplicates
from src import grok_client

load_dotenv()

REPORTS_DIR = "reports"


@click.group()
def cli():
    pass


def _today_report_path(prefix="metadata_review"):
    date_str = datetime.date.today().isoformat()
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return os.path.join(REPORTS_DIR, f"{prefix}_{date_str}.csv")


@cli.command()
@click.option("--category", default=None, help="Restrict to a category ID")
def audit(category):
    """Rule-based audit only — no LLM calls, fast and free."""
    client = get_client()
    products = client.list_products(category_id_filter=category)
    seen_descriptions = {}
    results = [audit_product(p, seen_descriptions) for p in products]
    dup_flags = flag_cross_product_duplicates(seen_descriptions)

    rows = []
    for r in results:
        issues = list(r.issues)
        if r.product_id in dup_flags:
            issues.append(dup_flags[r.product_id])
        rows.append({
            "id": r.product_id,
            "name": r.name,
            "issues_found": "; ".join(issues) if issues else "OK",
            "contains_claims": ", ".join(r.contains_claims),
            "needs_generation": r.needs_generation or r.product_id in dup_flags,
        })

    df = pd.DataFrame(rows)
    path = _today_report_path("audit_only")
    df.to_csv(path, index=False)
    n_flagged = df["needs_generation"].sum()
    click.echo(f"Audited {len(df)} products — {n_flagged} flagged for generation.")
    click.echo(f"Report written to {path}")


@cli.command()
@click.option("--ids", default=None, help="Comma-separated product IDs to process (default: all flagged by audit)")
@click.option("--category", default=None, help="Restrict to a category ID")
@click.option("--limit", default=None, type=int, help="Cap number of products processed (cost control)")
def generate(ids, category, limit):
    """Audit + generate improved metadata via the CrewAI pipeline for flagged products."""
    from src.crew import MetadataCrew  # imported lazily so `audit` works without crewai installed

    client = get_client()
    products = client.list_products(category_id_filter=category)

    if ids:
        id_set = set(ids.split(","))
        products = [p for p in products if p.id in id_set]

    seen_descriptions = {}
    audits = {a.product_id: a for a in (audit_product(p, seen_descriptions) for p in products)}
    dup_flags = flag_cross_product_duplicates(seen_descriptions)

    to_process = [
        p for p in products
        if audits[p.id].needs_generation or p.id in dup_flags or ids
    ]
    if limit:
        to_process = to_process[:limit]

    if not to_process:
        click.echo("No products need generation. Run `audit` first to see current status.")
        return

    click.echo(f"Generating metadata for {len(to_process)} product(s)...")
    crew = MetadataCrew()
    batch_titles = []
    rows = []
    for i, p in enumerate(to_process, 1):
        click.echo(f"  [{i}/{len(to_process)}] {p.name} (id={p.id})")
        result = crew.generate_for_product(p, batch_titles)
        batch_titles.append(result["proposed_meta_title"])
        a = audits[p.id]
        all_issues = list(a.issues)
        if p.id in dup_flags:
            all_issues.append(dup_flags[p.id])
        rows.append({
            "id": p.id,
            "name": p.name,
            "current_meta_title": p.meta_title,
            "current_meta_description": p.meta_description,
            "issues_found": "; ".join(all_issues),
            "proposed_meta_title": result["proposed_meta_title"],
            "proposed_meta_description": result["proposed_meta_description"],
            "claims_verified": ", ".join(result["claims_verified"]),
            "claims_removed": ", ".join(result["claims_removed"]),
            "qa_flags": "; ".join(result["qa_issues"]) if result["qa_issues"] else "none",
            "approved": "FALSE",
        })

    df = pd.DataFrame(rows)
    path = _today_report_path("metadata_review")
    df.to_csv(path, index=False)
    click.echo(f"\nReport written to {path}")
    click.echo("Review it, set approved=TRUE for rows to publish, then run:")
    click.echo(f"  python -m src.main publish --input {path}")


@cli.command()
@click.option("--input", "input_path", required=True, help="Reviewed CSV with approved=TRUE rows")
def publish(input_path):
    """Push approved rows from a reviewed report back to the shop. Never touches unapproved rows."""
    client = get_client()
    df = pd.read_csv(input_path, dtype=str).fillna("")
    approved = df[df["approved"].str.upper() == "TRUE"]

    if approved.empty:
        click.echo("No rows marked approved=TRUE — nothing to publish.")
        return

    click.echo(f"Publishing {len(approved)} approved product(s)...")
    for _, row in approved.iterrows():
        client.update_meta(row["id"], row["proposed_meta_title"], row["proposed_meta_description"])
        click.echo(f"  updated product {row['id']} ({row['name']})")

    click.echo("Done.")


@cli.command()
@click.option("--url", default=None, help="Product page URL to review (if set, reviews a single product)")
@click.option("--group-id", default=None, help="Product group ID to review (fetches products from the shop)")
def review(url, group_id):
    """Run an LLM-based review (Grok) for a single product URL or a product group ID."""
    if not url and not group_id:
        click.echo("Provide --url or --group-id")
        return

    client = get_client()

    def extract_meta_from_html(html):
        # Lightweight extraction. For robust parsing use BeautifulSoup in requirements.
        title = None
        description = None
        keywords = None
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            if soup.title:
                title = soup.title.string.strip()
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag and desc_tag.get("content"):
                description = desc_tag["content"].strip()
            kw_tag = soup.find("meta", attrs={"name": "keywords"})
            if kw_tag and kw_tag.get("content"):
                keywords = kw_tag["content"].strip()
        except Exception:
            pass
        return title, description, keywords

    def review_single(url_to_review):
        resp = requests.get(url_to_review, timeout=15)
        resp.raise_for_status()
        title, description, keywords = extract_meta_from_html(resp.text)
        prompt = f"""You are an SEO reviewer.
URL: {url_to_review}
Current title: {title}
Current description: {description}
Current keywords: {keywords}

Provide:
- a short assessment (issues, length problems, missing keywords)
- suggested improved meta title (<= 60 chars)
- suggested meta description (<= 160 chars)
- suggested keyword list
Format your answer as JSON with fields: assessment, suggested_title, suggested_description, suggested_keywords.
"""
        res = grok_client.ask_grok(prompt)
        click.echo(res)

    if url:
        review_single(url)
    else:
        # group_id path: fetch products then review their product pages
        products = client.list_products(category_id_filter=None)
        # naive: filter by group_id attribute name — adapt to actual ecommerce client
        group_products = [p for p in products if getattr(p, "group_id", None) == group_id]
        if not group_products:
            click.echo("No products found for group_id")
            return
        for p in group_products:
            prod_url = getattr(p, "url", None) or p.link or p.meta_link
            if not prod_url:
                click.echo(f"Skipping product {p.id} — no public URL available")
                continue
            click.echo(f"Reviewing product {p.id} — {p.name}\n  URL: {prod_url}")
            review_single(prod_url)


if __name__ == "__main__":
    cli()
