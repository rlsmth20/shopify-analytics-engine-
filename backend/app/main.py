import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db.init_db import init_db

logger = logging.getLogger(__name__)

from app.api.routes.actions import auth_scoped_router as auth_scoped_actions_router, router as actions_router
from app.api.routes.ai_chat import router as ai_chat_router
from app.api.routes.admin import router as admin_router
from app.api.routes.audit import router as audit_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router, webhook_router as stripe_webhook_router
from app.api.routes.bundles import router as bundles_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory_risk_snapshot import router as inventory_risk_snapshot_router
from app.api.routes.liquidation import router as liquidation_router
from app.api.routes.reorder import router as reorder_router
from app.api.routes.report_schedules import router as report_schedules_router
from app.api.routes.shipstation_import import router as shipstation_import_router
from app.api.routes.shop_settings import router as shop_settings_router
from app.api.routes.shopify_ingestion import router as shopify_ingestion_router
from app.api.routes.shopify_privacy_webhooks import router as shopify_privacy_webhooks_router
from app.api.routes.skus import router as skus_router
from app.api.routes.stocky_import import router as stocky_import_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.transfers import router as transfers_router
from app.api.routes.waitlist import router as waitlist_router
from app.api.routes.contact import router as contact_router
from app.services.alert_scheduler import start_alert_scheduler, stop_alert_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception:
        # Log the error but don't crash — the /health endpoint must stay up
        # so Railway's healthcheck passes and deploy logs are visible.
        logger.exception("init_db failed at startup — DB may not be reachable yet.")
    start_alert_scheduler()
    try:
        yield
    finally:
        await stop_alert_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="skubase API",
        version="0.3.0",
        description=(
            "Forecasting, replenishment, alerting, and supplier intelligence "
            "for Shopify merchants."
        ),
        lifespan=lifespan,
    )

    default_origins = [
        "http://localhost:3000",
        "https://skubase.io",
        "https://www.skubase.io",
    ]
    allowed_origins = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGIN", ",".join(default_origins)).split(",")
        if origin.strip()
    ]
    for origin in default_origins:
        if origin not in allowed_origins:
            allowed_origins.append(origin)

    @app.middleware("http")
    async def log_auth_cors_context(request: Request, call_next):
        if request.url.path.startswith("/auth"):
            origin = request.headers.get("origin")
            logger.info(
                "auth_request path=%s method=%s origin=%s cors_allowed=%s",
                request.url.path,
                request.method,
                origin,
                origin in allowed_origins if origin else None,
            )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Cache CORS preflights (Chrome caps at 2h). Without this every API
        # call from the app pays an extra OPTIONS round trip every 10 min.
        max_age=7200,
    )

    # auth + admin (always loaded first)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(stripe_webhook_router)
    app.include_router(shopify_privacy_webhooks_router)

    # v1 surfaces
    app.include_router(health_router)
    app.include_router(actions_router)
    app.include_router(auth_scoped_actions_router)
    app.include_router(ai_chat_router)
    app.include_router(shopify_ingestion_router)
    app.include_router(stocky_import_router)
    app.include_router(shipstation_import_router)
    app.include_router(waitlist_router)
    app.include_router(contact_router)
    app.include_router(inventory_risk_snapshot_router)
    app.include_router(shop_settings_router)
    app.include_router(skus_router)

    # v2 intelligence surfaces
    app.include_router(dashboard_router)
    app.include_router(forecast_router)
    app.include_router(analytics_router)
    app.include_router(reorder_router)
    app.include_router(suppliers_router)
    app.include_router(bundles_router)
    app.include_router(transfers_router)
    app.include_router(liquidation_router)
    app.include_router(alerts_router)
    app.include_router(audit_router)
    app.include_router(report_schedules_router)

    return app


app = create_app()
