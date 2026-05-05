import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.init_db import init_db

logger = logging.getLogger(__name__)

from app.api.routes.actions import auth_scoped_router as auth_scoped_actions_router, router as actions_router
from app.api.routes.admin import router as admin_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router, webhook_router as stripe_webhook_router
from app.api.routes.bundles import router as bundles_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.health import router as health_router
from app.api.routes.liquidation import router as liquidation_router
from app.api.routes.reorder import router as reorder_router
from app.api.routes.shipstation_import import router as shipstation_import_router
from app.api.routes.shop_settings import router as shop_settings_router
from app.api.routes.shopify_ingestion import router as shopify_ingestion_router
from app.api.routes.skus import router as skus_router
from app.api.routes.stocky_import import router as stocky_import_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.transfers import router as transfers_router
from app.api.routes.waitlist import router as waitlist_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception:
        # Log the error but don't crash — the /health endpoint must stay up
        # so Railway's healthcheck passes and deploy logs are visible.
        logger.exception("init_db failed at startup — DB may not be reachable yet.")
    yield


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

    allowed_origins = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # auth + admin (always loaded first)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(billing_router)
    app.include_router(stripe_webhook_router)

    # v1 surfaces
    app.include_router(health_router)
    app.include_router(actions_router)
    app.include_router(auth_scoped_actions_router)
    app.include_router(shopify_ingestion_router)
    app.include_router(stocky_import_router)
    app.include_router(shipstation_import_router)
    app.include_router(waitlist_router)
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

    return app


app = create_app()
