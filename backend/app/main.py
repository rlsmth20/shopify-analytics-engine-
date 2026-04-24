import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.actions import router as actions_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.bundles import router as bundles_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.health import router as health_router
from app.api.routes.liquidation import router as liquidation_router
from app.api.routes.reorder import router as reorder_router
from app.api.routes.shopify_ingestion import router as shopify_ingestion_router
from app.api.routes.shop_settings import router as shop_settings_router
from app.api.routes.skus import router as skus_router
from app.api.routes.suppliers import router as suppliers_router
from app.api.routes.transfers import router as transfers_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Inventory Command API",
        version="0.2.0",
        description=(
            "Forecasting, replenishment, alerting, and supplier intelligence "
            "for Shopify merchants."
        ),
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

    # v1 surfaces
    app.include_router(health_router)
    app.include_router(actions_router)
    app.include_router(shopify_ingestion_router)
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
