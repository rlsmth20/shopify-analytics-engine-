"""Isolated browser verification fixture. Never imported by the production app."""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_optional_user, require_admin
from app.api.routes.growth import router
from app.db.base import Base
from app.db.session import get_db_session
from app.growth.engine import bootstrap
from app.growth.seed_live import seed

temp = tempfile.TemporaryDirectory(prefix="skubase-growth-preview-")
engine = create_engine("sqlite:///" + str(Path(temp.name) / "preview.sqlite"), connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
factory = sessionmaker(engine, expire_on_commit=False)
bootstrap(factory)
seed(factory)
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3010"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
def session():
    with factory() as db:
        yield db
app.dependency_overrides[get_db_session] = session
app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id=1, is_admin=True)
app.dependency_overrides[get_optional_user] = lambda: None
