import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.actions import router as actions_router
from app.api.routes.health import router as health_router
from app.api.routes.shopify_ingestion import router as shopify_ingestion_router
from app.api.routes.shop_settings import router as shop_settings_router
from app.api.routes.skus import router as skus_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Shopify Inventory Decision Engine API",
        version="0.1.0",
        description="Mock-backed API scaffold for inventory actions and SKU analytics.",
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

    app.include_router(health_router)
    app.include_router(actions_router)
    app.include_router(shopify_ingestion_router)
    app.include_router(shop_settings_router)
    app.include_router(skus_router)
    return app


app = create_app()
