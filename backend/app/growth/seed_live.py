"""One-time, attributable public evidence collected during the initial live mission.

Run explicitly after deployment: python -m app.growth.seed_live
These are attributed paraphrases, not independent proof of business identity.
"""
import time
from datetime import datetime, timezone

from app.db.session import SessionLocal
from .discovery import ingest_opportunity
from .models import Experiment
from .store import enqueue, get_memory, insert_once, record, remember
from .worker import initialize


def seed(factory=SessionLocal):
    with factory() as db:
        prior = get_memory(db, "strategic", "initial_market_check")
        if prior:
            return prior
        sources = [
            {"url": "https://www.reddit.com/r/AutomateShopify/comments/1w0sta4/does_anyone_actually_let_inventory_planning/",
             "author": "jadedjayedess", "channel": "reddit", "date": "2026-08-28",
             "text": "A merchant says they still handle purchasing manually for their store. They ask whether demand forecasting gives useful results and which seasonal/promotion failure points to watch. Evidence supports a trust-and-review problem, not authorization to email or a verified need for Skubase."},
            {"url": "https://community.shopify.com/t/looking-for-inventory-adjustment-alternatives/639382",
             "author": "maryjapanla", "channel": "shopify_community", "date": "2026-06-24",
             "text": "A merchant requests custom reasons and notes on inventory adjustments for auditability. Later replies promote several apps. This is a stock-adjustment workflow request; it is not evidence that forecasting is their buying priority. Original request is older than the recent vendor replies."},
            {"url": "https://community.shopify.com/t/stocky-alternative-recommendation/553677/42",
             "author": "RunninWildKids.co", "channel": "shopify_community", "date": "2026-06-24",
             "text": "A children's shoes and toys reseller reports many SKUs but little need for detailed SKU forecasting because shoe lines change seasonally and are ordered months ahead. They want stock counts, receiving and supplier-payment visibility. Counterexample to treating high SKU count alone as strong forecasting fit."},
        ]
        ids = []
        for item in sources:
            date = item.pop("date")
            event = ingest_opportunity(db, **item, published_at=datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())
            ids.append(event.id)
        observation = record(db, "initial-market-judgment-20260906", "MARKET_INTERPRETATION", "mission",
            {"evidence_ids": ids, "finding": "Reviewable reorder decisions look more relevant than broad Stocky replacement. High SKU count and inventory pain alone do not establish fit.",
             "sample_size": 3, "confidence": "low", "date_precision": "Dates taken from source page or search index; source extracts retained as attributed paraphrases."}, epistemic="INFERENCE")
        strategy = get_memory(db, "strategic", "strategy")
        remember(db, "strategic", "strategy", {**strategy,
            "icp": "Provisional: Shopify operators buying repeat-selling physical SKUs who want reviewable reorder priorities. Verify seasonality, purchasing responsibility and data coverage; high SKU count alone is insufficient.",
            "positioning": "Free Shopify Inventory Health Check, with explainable priorities and merchant-controlled purchasing",
            "next_action": "Test the free reorder calculator and find recent, legitimate merchant contact paths",
            "evidence_ids": ids, "positioning_confidence": "low; three purposively selected public observations"})
        remember(db, "beliefs", "high-sku-count-fit", {"type": "BELIEF", "claim": "High SKU count alone does not establish forecasting fit.",
            "supporting_evidence": [ids[2]], "contradictory_evidence": [], "confidence": .5,
            "confidence_meaning": "Provisional confidence in a segment qualification caveat; not a measured response probability.",
            "credible_interval_95": [0, 1], "sample_size": 1, "source_experiments": [], "last_updated": time.time()})
        experiment, _ = insert_once(db, Experiment, key="reorder-calculator-v1", stop_at=time.time() + 28 * 86400,
            specification={"hypothesis": "A free, explainable reorder calculator generates qualified health-check requests and connected stores.",
                "channel": "organic_search", "target_customer": "Shopify operators calculating ordering triggers", "message_positioning": "Reviewable reorder point, not automatic purchasing",
                "action": "Publish one useful calculator and link it from the existing safety-stock article",
                "primary_metric": "distinct connected stores attributed to reorder-calculator-v1", "secondary_metrics": ["health-check requests", "calculator use", "signup", "activation", "payment"],
                "cost": {"advertising_usd": 0, "model_api_usd": 0, "owner_attention_minutes": None},
                "stop_condition": "Review after 28 days; stop expansion if visits produce no qualified intent", "success_condition": "At least one attributable connected store",
                "variables_changed": ["new useful tool"], "max_contacts": 0})
        record(db, "tool-experiment-start", "EXPERIMENT_STARTED", experiment.id, experiment.specification, epistemic="HYPOTHESIS")
        result = {"evidence_ids": ids, "interpretation_id": observation.id, "tool_experiment_id": experiment.id}
        remember(db, "strategic", "initial_market_check", result, source="initial_live_research")
        enqueue(db, "initial-live-observe", "observe", priority=100)
        db.commit()
        return result


if __name__ == "__main__":
    # Production startup owns schema creation; do not race its DDL from this command.
    print(seed())
