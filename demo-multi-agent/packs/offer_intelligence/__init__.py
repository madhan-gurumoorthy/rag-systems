"""Offer Intelligence pack — combined Offer Listing (delist) verification
and Offer Publish (unpublish reason-code) validation.

Exposes two read-only diagnostic tools that share a single pipeline:

  * ``DIAG-OL-TRIAGE-01``      — deterministic OL listing verification
    for an (offer_id, store_id) pair, plus the matched-rule evaluator
    and report renderer.
  * ``DIAG-VALIDATE-OFFER-01`` — comprehensive unpublish reason-code
    validator that fans out across IQS / CASTAR / Oasis / Offer Store /
    Product Matching / Product Store / Uber Keys.

Routing is owned by the TriageAgent prompt and the ``check_mode`` slot
on ``OfferIntelligenceState``:

  * ``ol_only``      — caller supplied ``store_id``; run OL triage only.
  * ``publish_only`` — no ``store_id``; run the unpublish validator only.
  * ``both``         — caller explicitly asked for both checks.
"""
