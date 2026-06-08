"""
OL Triage Engine — deterministic, no LLM.

Orchestrates the full triage flow:
  1. get_listing_status  →  find matched rules
  2. get_rule_definition →  know which facts are needed
  3. Fetch only required facts (SIV, Merloc, Offer, Product, Price,
     Inventory, HAT Path)
  4. evaluate_rule       →  deterministic verdict per rule

Entry points:
  - ``OLTriageEngine.triage_offer(offer_id, store_id, mart_id)`` → single offer
  - ``OLTriageEngine.triage_batch(items)`` → many offers concurrently
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Field → Service mapping ──────────────────────────────────────────────────
# "FREE" fields come from the OL API response and need no extra call.

FREE_FIELDS = {
    "startDateSource",
    "endDateSource",
    "startDate",
    "endDate",
    "hasSellableNodeInventory",
    "lastInventoryModificationDate",
    "olRestrictionExpirationDate",
}

SIV_FIELDS = {"ValidityTypes", "hasSales", "recallFlag"}
HAT_FIELDS = {"hatPathIds"}
OFFER_FIELDS = {"sellerId", "wfsEligible", "offerGroupType", "offerGroupSubType"}
PRODUCT_FIELDS = {
    "productClassType",
    "productType",
    "itemId",
    "ItemClassId",
    "approvedForAnimals",
    "Personalization",
    "PersonalizationURL",
}
PRICE_FIELDS = {"storePrice", "priceTypeCode", "previewPriceReasonCode"}
MERLOC_FIELDS = {"NON_EMPTY_LOCATION_SIGNAL", "NON_EMPTY_CONFIRMATION_SIGNAL"}
INVENTORY_FIELDS = {
    "hasInventory",
    "hasSellableNodeInventory",
    "lastInventoryModificationDate",
}

INPUT_FIELDS = {"storeId"}


# ── Result models ────────────────────────────────────────────────────────────

@dataclass
class RuleVerdict:
    """Evaluation result for a single rule."""

    rule_id: str
    rule_name: str
    rule_group: str
    reason_code: str
    verdict: str  # VALID | INVALID | PARTIAL | CANNOT_EVALUATE
    expression_result: bool | None
    evaluated_count: int
    skipped_count: int
    total_conditions: int
    cannot_evaluate_fields: list[dict] = field(default_factory=list)
    per_condition_results: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TriageResult:
    """Full triage result for one offer+store."""

    offer_id: str
    store_id: str
    mart_id: str
    listing_status: str  # LISTED | DELISTED | UNKNOWN
    matched_rule_ids: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    rule_verdicts: list[RuleVerdict] = field(default_factory=list)
    overall_verdict: str = ""  # ALL_VALID | HAS_INVALID | PARTIAL | CANNOT_EVALUATE | LISTED
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "offer_id": self.offer_id,
            "store_id": self.store_id,
            "mart_id": self.mart_id,
            "listing_status": self.listing_status,
            "matched_rule_ids": self.matched_rule_ids,
            "reason_codes": self.reason_codes,
            "overall_verdict": self.overall_verdict,
            "rule_verdicts": [rv.to_dict() for rv in self.rule_verdicts],
            "errors": self.errors,
        }


# ── Triage Engine ────────────────────────────────────────────────────────────

class OLTriageEngine:
    """Deterministic OL triage engine — no LLM, pure Python.

    Instantiate once and call ``triage_offer()`` or ``triage_batch()``.
    Uses lazy-loaded service singletons.
    """

    def __init__(self):
        self._ol_api = None
        self._registry = None
        self._evaluator = None
        self._siv = None
        self._merloc = None
        self._offer = None
        self._product = None
        self._price = None
        self._inventory = None
        self._hat_path = None

    # ── Lazy service accessors ────────────────────────────────────────

    def _get_ol_api(self):
        if self._ol_api is None:
            from packs.offer_intelligence.services.ol_api_service import get_ol_api_service
            self._ol_api = get_ol_api_service()
        return self._ol_api

    def _get_registry(self):
        if self._registry is None:
            from packs.offer_intelligence.services.rule_registry import get_registry
            self._registry = get_registry()
        return self._registry

    def _get_evaluator(self):
        if self._evaluator is None:
            from packs.offer_intelligence.services import evaluator
            self._evaluator = evaluator
        return self._evaluator

    def _get_siv(self):
        if self._siv is None:
            from packs.offer_intelligence.services.siv_service import get_siv_service
            self._siv = get_siv_service()
        return self._siv

    def _get_merloc(self):
        if self._merloc is None:
            from packs.offer_intelligence.services.merloc_service import get_merloc_service
            self._merloc = get_merloc_service()
        return self._merloc

    def _get_offer(self):
        if self._offer is None:
            from packs.offer_intelligence.services.offer_service import get_offer_service
            self._offer = get_offer_service()
        return self._offer

    def _get_product(self):
        if self._product is None:
            from packs.offer_intelligence.services.product_service import get_product_service
            self._product = get_product_service()
        return self._product

    def _get_price(self):
        if self._price is None:
            from packs.offer_intelligence.services.store_price_service import get_store_price_service
            self._price = get_store_price_service()
        return self._price

    def _get_inventory(self):
        if self._inventory is None:
            from packs.offer_intelligence.services.inventory_service import get_inventory_service
            self._inventory = get_inventory_service()
        return self._inventory

    def _get_hat_path(self):
        if self._hat_path is None:
            from packs.offer_intelligence.services.hat_path_service import get_hat_path_service
            self._hat_path = get_hat_path_service()
        return self._hat_path

    # ── Fact resolution ───────────────────────────────────────────────

    async def _resolve_facts(
        self,
        offer_id: str,
        store_id: str,
        entry_fields_required: list[str],
        ol_response: dict,
    ) -> dict[str, Any]:
        """
        Resolve fact values for the given entry fields.

        Calls only the services whose fields appear in ``entry_fields_required``.
        Reuses FREE fields from the OL API response.
        """
        facts: dict[str, Any] = {}

        # 1. FREE fields from OL response
        key_map = {
            "startDateSource": "start_date_source",
            "endDateSource": "end_date_source",
            "startDate": "start_date",
            "endDate": "end_date",
            "hasSellableNodeInventory": "has_sellable_node_inventory",
            "lastInventoryModificationDate": "last_inventory_modification_date",
            "olRestrictionExpirationDate": "ol_restriction_expiration_date",
        }
        for f in entry_fields_required:
            if f in FREE_FIELDS:
                ol_key = key_map.get(f, f)
                facts[f] = ol_response.get(ol_key)

        # 2. storeId from input
        if "storeId" in entry_fields_required:
            facts["storeId"] = store_id

        # 3. Determine which services to call
        needed = set(entry_fields_required) - FREE_FIELDS - INPUT_FIELDS
        service_calls = []

        if needed & SIV_FIELDS:
            service_calls.append(("siv", self._fetch_siv(offer_id, store_id)))
        if needed & OFFER_FIELDS:
            service_calls.append(("offer", self._fetch_offer(offer_id)))
        if needed & PRODUCT_FIELDS:
            service_calls.append(("product", self._fetch_product(offer_id)))
        if needed & PRICE_FIELDS:
            service_calls.append(("price", self._fetch_price(offer_id, store_id)))
        if needed & MERLOC_FIELDS:
            service_calls.append(("merloc", self._fetch_merloc(offer_id, store_id)))
        if needed & INVENTORY_FIELDS:
            service_calls.append(("inventory", self._fetch_inventory(offer_id, store_id)))
        if needed & HAT_FIELDS:
            service_calls.append(("hat_path", self._fetch_hat_path(offer_id)))

        # 4. Execute all service calls concurrently
        if service_calls:
            results = await asyncio.gather(
                *[coro for _, coro in service_calls],
                return_exceptions=True,
            )
            for (name, _), result in zip(service_calls, results):
                if isinstance(result, Exception):
                    logger.error(f"core.triage.service_error service={name} error={result}")
                    continue
                if isinstance(result, dict):
                    for f in entry_fields_required:
                        if f in result:
                            facts[f] = result[f]

        return facts

    async def _fetch_siv(self, offer_id: str, store_id: str) -> dict:
        return await self._get_siv().get_siv_data(offer_id, store_id)

    async def _fetch_offer(self, offer_id: str) -> dict:
        return await self._get_offer().get_offer_attributes(offer_id)

    async def _fetch_product(self, offer_id: str) -> dict:
        return await self._get_product().get_product_attributes(offer_id)

    async def _fetch_price(self, offer_id: str, store_id: str) -> dict:
        return await self._get_price().get_store_price(offer_id, store_id)

    async def _fetch_merloc(self, offer_id: str, store_id: str) -> dict:
        return await self._get_merloc().get_locations(offer_id, store_id)

    async def _fetch_inventory(self, offer_id: str, store_id: str) -> dict:
        return await self._get_inventory().get_inventory_signals(offer_id, store_id)

    async def _fetch_hat_path(self, offer_id: str) -> dict:
        return await self._get_hat_path().get_hat_path_ids(offer_id)

    # ── Single offer triage ───────────────────────────────────────────

    async def triage_offer(
        self,
        offer_id: str,
        store_id: str,
        mart_id: str = "0",
    ) -> TriageResult:
        """Full deterministic triage for one offer+store."""
        result = TriageResult(
            offer_id=offer_id,
            store_id=store_id,
            mart_id=mart_id,
            listing_status="UNKNOWN",
        )

        # Step 1: Get listing status
        try:
            ol_response = await self._get_ol_api().get_listing_status(offer_id, store_id, mart_id)
        except Exception as exc:
            logger.error(f"core.triage.ol_api_failed error={exc}")
            result.errors.append(f"OL API call failed: {exc}")
            return result

        result.listing_status = ol_response.get("listing_status", "UNKNOWN")
        result.matched_rule_ids = ol_response.get("matched_rule_ids", [])
        result.reason_codes = ol_response.get("reason_codes", [])

        # If LISTED → done, no rules to evaluate
        if result.listing_status == "LISTED":
            result.overall_verdict = "LISTED"
            return result

        # Step 2: Evaluate each matched rule
        if not result.matched_rule_ids:
            result.overall_verdict = "NO_MATCHED_RULES"
            result.errors.append("DELISTED but no matched rule IDs found in OL response")
            return result

        rule_tasks = [
            self._evaluate_single_rule(rule_id, offer_id, store_id, ol_response)
            for rule_id in result.matched_rule_ids
        ]
        rule_results = await asyncio.gather(*rule_tasks, return_exceptions=True)
        for rule_id, rv in zip(result.matched_rule_ids, rule_results):
            if isinstance(rv, Exception):
                logger.error(f"core.triage.rule_eval_failed rule={rule_id} error={rv}")
                continue
            result.rule_verdicts.append(rv)

        # Step 3: Compute overall verdict
        verdicts = [rv.verdict for rv in result.rule_verdicts]
        if verdicts and all(v == "VALID" for v in verdicts):
            result.overall_verdict = "ALL_VALID"
        elif any(v == "INVALID" for v in verdicts):
            result.overall_verdict = "HAS_INVALID"
        elif any(v == "PARTIAL" for v in verdicts):
            result.overall_verdict = "PARTIAL"
        else:
            result.overall_verdict = "CANNOT_EVALUATE"

        logger.info(
            f"core.triage.done offer={offer_id} store={store_id} "
            f"status={result.listing_status} verdict={result.overall_verdict} "
            f"rules_evaluated={len(result.rule_verdicts)}"
        )

        return result

    async def _evaluate_single_rule(
        self,
        rule_id: str,
        offer_id: str,
        store_id: str,
        ol_response: dict,
    ) -> RuleVerdict:
        """Evaluate a single rule: load definition → resolve facts → evaluate."""
        registry = self._get_registry()
        rule_def = registry.get_rule(rule_id)

        if rule_def is None:
            return RuleVerdict(
                rule_id=rule_id,
                rule_name="UNKNOWN",
                rule_group="UNKNOWN",
                reason_code="",
                verdict="CANNOT_EVALUATE",
                expression_result=None,
                evaluated_count=0,
                skipped_count=0,
                total_conditions=0,
                cannot_evaluate_fields=[
                    {
                        "field": "ALL",
                        "tier": "MISSING",
                        "reason": f"Rule {rule_id} not found in registry",
                    }
                ],
            )

        entry_fields = rule_def.get("entry_fields_required", [])
        expression = rule_def.get("expression", "")
        conditions = rule_def.get("conditions", [])

        try:
            facts = await self._resolve_facts(offer_id, store_id, entry_fields, ol_response)
        except Exception as exc:
            logger.error(f"core.triage.fact_resolution_failed rule={rule_id} error={exc}")
            return RuleVerdict(
                rule_id=rule_id,
                rule_name=rule_def.get("rule_name", ""),
                rule_group=rule_def.get("rule_group", ""),
                reason_code=rule_def.get("reason_code", ""),
                verdict="CANNOT_EVALUATE",
                expression_result=None,
                evaluated_count=0,
                skipped_count=0,
                total_conditions=len(conditions),
                cannot_evaluate_fields=[
                    {"field": "ALL", "tier": "ERROR", "reason": f"Fact resolution failed: {exc}"}
                ],
            )

        evaluator_mod = self._get_evaluator()
        eval_result = evaluator_mod.evaluate_rule(
            rule_id=rule_id,
            expression=expression,
            conditions=conditions,
            facts=facts,
            engine_said_delist=True,
        )

        return RuleVerdict(
            rule_id=rule_id,
            rule_name=rule_def.get("rule_name", ""),
            rule_group=rule_def.get("rule_group", ""),
            reason_code=rule_def.get("reason_code", ""),
            verdict=eval_result["verdict"],
            expression_result=eval_result.get("expression_result"),
            evaluated_count=eval_result["evaluated_count"],
            skipped_count=eval_result["skipped_count"],
            total_conditions=eval_result["total_conditions"],
            cannot_evaluate_fields=eval_result.get("cannot_evaluate_fields", []),
            per_condition_results=eval_result.get("per_condition_results", []),
        )

    # ── Batch triage ──────────────────────────────────────────────────

    async def triage_batch(
        self,
        items: list[dict],
        concurrency: int = 10,
    ) -> list[TriageResult]:
        """Triage multiple offer+store pairs concurrently."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _triage_one(item: dict) -> TriageResult:
            async with semaphore:
                try:
                    return await self.triage_offer(
                        offer_id=item["offer_id"],
                        store_id=item["store_id"],
                        mart_id=item.get("mart_id", "0"),
                    )
                except Exception as exc:
                    logger.error(f"core.triage.batch_item_failed item={item} error={exc}")
                    return TriageResult(
                        offer_id=item.get("offer_id", ""),
                        store_id=item.get("store_id", ""),
                        mart_id=item.get("mart_id", "0"),
                        listing_status="ERROR",
                        overall_verdict="ERROR",
                        errors=[str(exc)],
                    )

        return await asyncio.gather(*[_triage_one(item) for item in items])


# Module-level singleton for pack tool wiring
_engine: OLTriageEngine | None = None


def get_engine() -> OLTriageEngine:
    global _engine
    if _engine is None:
        _engine = OLTriageEngine()
    return _engine
