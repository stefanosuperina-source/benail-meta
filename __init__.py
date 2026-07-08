# Task prompts for the Benail product metadata pipeline.
# {product_name}, {category}, {description}, {attributes}, {existing_meta_title},
# {existing_meta_description}, {batch_titles_so_far} are filled in at runtime
# from src/crew.py using the product dict passed to the pipeline.

draft_metadata_task:
  description: >
    Write new metadata for this product:

    Name: {product_name}
    Category: {category}
    Description (source of truth — do not add facts not present here): {description}
    Attributes/specs: {attributes}
    Current meta_title (may be empty or poor quality): {existing_meta_title}
    Current meta_description (may be empty or poor quality): {existing_meta_description}

    Requirements:
    - meta_title: 50-60 characters, includes the product name and one
      distinguishing detail (format, use-case, or category), no more
      than one keyword phrase reused from other products in this batch.
    - meta_description: 140-160 characters, written as a natural sentence
      or two, states what the product is and who it's for, includes at
      most ONE claim keyword (e.g. HEMA Free, TPO Free) and only if it
      appears in the source description/attributes above.
    - Mention each core phrase (e.g. "prodotto professionale", "per
      onicotecniche") at most once. Do not repeat the exact phrasing
      used in {batch_titles_so_far} for other products in this run.
    - Do not invent certifications, percentages, durations, or safety
      claims that are not explicitly present in the source data above.
  expected_output: >
    A JSON object: {{"meta_title": "...", "meta_description": "...",
    "claims_used": ["..."]}} — claims_used lists any claim keywords
    included, for the fact-checker to verify.

fact_check_task:
  description: >
    Take the drafted metadata and claims_used list from the previous
    task. For each item in claims_used, confirm it is explicitly
    present in this product's source description/attributes:

    Description: {description}
    Attributes: {attributes}

    If a claim is NOT explicitly present in the source data, remove it
    from the meta_title/meta_description and rewrite that portion
    without it. Do not search external sources — the only source of
    truth is this product's own data. Do not soften this into a vague
    claim (e.g. don't replace an unverified "HEMA Free" with a vague
    "sicuro" if "sicuro" isn't supported either).
  expected_output: >
    A JSON object: {{"meta_title": "...", "meta_description": "...",
    "claims_verified": ["..."], "claims_removed": ["..."]}}

critic_task:
  description: >
    Review the fact-checked metadata for this product against the
    other products already drafted in this batch: {batch_titles_so_far}

    Check for:
    - meta_title outside 50-60 characters, or meta_description outside
      140-160 characters
    - any phrase repeated more than twice within the same field
    - phrasing generic enough to apply to more than one product in
      {batch_titles_so_far}
    - remaining unverifiable claims

    Do not rewrite anything yourself — only report issues found, or
    an empty list if none.
  expected_output: >
    A JSON object: {{"issues": ["..."]}} — empty list if no issues.
