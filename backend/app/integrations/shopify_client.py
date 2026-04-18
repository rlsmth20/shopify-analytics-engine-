import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ShopifyClientError(RuntimeError):
    """Raised when the Shopify API returns an error or invalid response."""


@dataclass(frozen=True)
class ShopifyClientConfig:
    shopify_domain: str
    access_token: str
    api_version: str = "2025-01"
    timeout_seconds: int = 30


class ShopifyClient:
    def __init__(self, config: ShopifyClientConfig):
        self.config = config

    @property
    def shopify_domain(self) -> str:
        return self.config.shopify_domain

    def get_shop(self) -> dict[str, Any]:
        response = self._get("shop.json")
        return response.get("shop", {})

    def get_products(self, limit: int = 250) -> list[dict[str, Any]]:
        response = self._get("products.json", {"limit": limit})
        return response.get("products", [])

    def get_orders(
        self,
        *,
        limit: int = 250,
        status: str = "any",
        created_at_min: datetime | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "status": status}
        if created_at_min is not None:
            params["created_at_min"] = created_at_min.isoformat()

        response = self._get("orders.json", params)
        return response.get("orders", [])

    def get_inventory_levels(
        self,
        *,
        inventory_item_ids: list[str],
        location_ids: list[str] | None = None,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        if not inventory_item_ids:
            return []

        params: dict[str, Any] = {
            "inventory_item_ids": ",".join(inventory_item_ids),
            "limit": limit,
        }
        if location_ids:
            params["location_ids"] = ",".join(location_ids)

        response = self._get("inventory_levels.json", params)
        return response.get("inventory_levels", [])

    def _get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        url = (
            f"https://{self.config.shopify_domain}/admin/api/"
            f"{self.config.api_version}/{path}{query}"
        )
        request = Request(
            url,
            headers={
                "X-Shopify-Access-Token": self.config.access_token,
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:  # pragma: no cover - network path not exercised locally.
            raise ShopifyClientError(_format_http_error(path, exc)) from exc
        except URLError as exc:  # pragma: no cover - network path not exercised locally.
            reason = getattr(exc.reason, "strerror", None) or str(exc.reason)
            raise ShopifyClientError(
                f"Shopify request failed for {path}: {reason}."
            ) from exc
        except TimeoutError as exc:  # pragma: no cover - network path not exercised locally.
            raise ShopifyClientError(f"Shopify request timed out for {path}.") from exc
        except Exception as exc:  # pragma: no cover - network path not exercised locally.
            raise ShopifyClientError(f"Shopify request failed for {path}.") from exc

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ShopifyClientError(f"Shopify returned invalid JSON for {path}.") from exc

        if not isinstance(parsed, dict):
            raise ShopifyClientError(
                f"Shopify returned an unexpected response shape for {path}."
            )

        return parsed


def _format_http_error(path: str, exc: HTTPError) -> str:
    message = f"Shopify request failed for {path} with status {exc.code}."

    try:
        payload = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # pragma: no cover - defensive fallback.
        payload = ""

    if not payload:
        return message

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return f"{message} {payload}"

    detail = parsed.get("errors") or parsed.get("error")
    if detail is None:
        return message

    if isinstance(detail, dict):
        detail_text = json.dumps(detail, sort_keys=True)
    elif isinstance(detail, list):
        detail_text = ", ".join(str(item) for item in detail)
    else:
        detail_text = str(detail)

    return f"{message} {detail_text}"
