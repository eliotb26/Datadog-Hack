"""Lightdash REST API client for SIGNAL.

Provides async access to a self-hosted Lightdash instance.
Falls back silently when LIGHTDASH_URL / LIGHTDASH_API_KEY are not set,
allowing all callers to degrade gracefully in local dev.

Lightdash REST API reference:
  https://docs.lightdash.com/api/v1/
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth / session helpers
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 15.0


class LightdashAuthError(Exception):
    """Raised when Lightdash authentication fails."""


class LightdashClient:
    """Async client for the Lightdash REST API (v1).

    Usage::

        async with LightdashClient() as client:
            dashboards = await client.list_dashboards()

    When LIGHTDASH_URL is not configured the client operates in *stub mode*:
    every method returns an empty result and logs a debug message instead of
    raising an error.  This keeps all callers working during local dev.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        project_uuid: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = (base_url or os.getenv("LIGHTDASH_URL", "")).rstrip("/")
        self._api_key = api_key or os.getenv("LIGHTDASH_API_KEY", "")
        self._project_uuid = project_uuid or os.getenv("LIGHTDASH_PROJECT_UUID", "")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._session_token: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "LightdashClient":
        await self._open()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._close()

    async def _open(self) -> None:
        if not self._base_url:
            return
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"ApiKey {self._api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    async def _close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Availability check
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return bool(self._base_url and self._api_key)

    async def health_check(self) -> bool:
        """Return True if the Lightdash instance is reachable and healthy."""
        if not self.is_available:
            return False
        try:
            resp = await self._get("/api/v1/health")
            return resp.get("status") == "ok"
        except Exception as exc:
            log.debug("lightdash_health_check_failed", exc_info=exc)
            return False

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            log.debug("lightdash_client_not_open path=%s", path)
            return {}
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data)

    async def _post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self._client:
            log.debug("lightdash_client_not_open path=%s", path)
            return {}
        resp = await self._client.post(path, json=body or {})
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data)

    # ------------------------------------------------------------------
    # Project / Dashboard API
    # ------------------------------------------------------------------

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all Lightdash projects the API key has access to."""
        if not self.is_available:
            return []
        try:
            result = await self._get("/api/v1/projects")
            return result if isinstance(result, list) else []
        except Exception as exc:
            log.warning("lightdash_list_projects_failed error=%s", exc)
            return []

    async def list_dashboards(
        self, project_uuid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List dashboards in the given project."""
        pid = project_uuid or self._project_uuid
        if not (self.is_available and pid):
            return []
        try:
            result = await self._get(f"/api/v1/projects/{pid}/dashboards")
            return result if isinstance(result, list) else []
        except Exception as exc:
            log.warning("lightdash_list_dashboards_failed error=%s", exc)
            return []

    async def get_dashboard(
        self, dashboard_uuid: str, project_uuid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch a single dashboard definition."""
        pid = project_uuid or self._project_uuid
        if not (self.is_available and pid):
            return {}
        try:
            return await self._get(f"/api/v1/projects/{pid}/dashboards/{dashboard_uuid}")
        except Exception as exc:
            log.warning("lightdash_get_dashboard_failed uuid=%s error=%s", dashboard_uuid, exc)
            return {}

    # ------------------------------------------------------------------
    # Saved Charts API
    # ------------------------------------------------------------------

    async def list_charts(
        self, project_uuid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List saved charts in the project."""
        pid = project_uuid or self._project_uuid
        if not (self.is_available and pid):
            return []
        try:
            result = await self._get(f"/api/v1/projects/{pid}/charts")
            return result if isinstance(result, list) else []
        except Exception as exc:
            log.warning("lightdash_list_charts_failed error=%s", exc)
            return []

    async def get_chart_results(
        self, saved_chart_uuid: str, project_uuid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch the latest query results for a saved chart.

        Returns a dict with ``rows`` (list of row dicts) and ``fields``
        (column metadata).  Falls back to ``{"rows": [], "fields": {}}``
        on any error.
        """
        pid = project_uuid or self._project_uuid
        empty: Dict[str, Any] = {"rows": [], "fields": {}}
        if not (self.is_available and pid):
            return empty
        try:
            result = await self._get(
                f"/api/v1/saved/{saved_chart_uuid}/results"
            )
            return result if isinstance(result, dict) else empty
        except Exception as exc:
            log.warning(
                "lightdash_get_chart_results_failed uuid=%s error=%s",
                saved_chart_uuid,
                exc,
            )
            return empty

    # ------------------------------------------------------------------
    # Explore / ad-hoc query API
    # ------------------------------------------------------------------

    async def run_metric_query(
        self,
        explore_name: str,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[List[Dict[str, Any]]] = None,
        limit: int = 500,
        project_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run an ad-hoc metric query against a Lightdash explore.

        Parameters
        ----------
        explore_name:
            The dbt model / explore name (e.g. ``"campaigns"``).
        dimensions:
            List of field references, e.g. ``["campaigns_created_at_date"]``.
        metrics:
            List of metric references, e.g. ``["campaigns_avg_confidence"]``.
        filters:
            Optional filter dict following Lightdash filter format.
        sort_by:
            Optional sort list, e.g. ``[{"fieldId": "...", "descending": True}]``.
        limit:
            Maximum rows to return.

        Returns
        -------
        Dict with ``rows`` list and ``fields`` metadata, or empty on failure.
        """
        pid = project_uuid or self._project_uuid
        empty: Dict[str, Any] = {"rows": [], "fields": {}}
        if not (self.is_available and pid):
            return empty
        body: Dict[str, Any] = {
            "exploreName": explore_name,
            "dimensions": dimensions,
            "metrics": metrics,
            "filters": filters or {},
            "sorts": sort_by or [],
            "limit": limit,
            "tableCalculations": [],
            "additionalMetrics": [],
        }
        try:
            return await self._post(
                f"/api/v1/projects/{pid}/explores/{explore_name}/runQuery",
                body,
            )
        except Exception as exc:
            log.warning(
                "lightdash_run_metric_query_failed explore=%s error=%s",
                explore_name,
                exc,
            )
            return empty

    # ------------------------------------------------------------------
    # Webhook / Scheduler API
    # ------------------------------------------------------------------

    async def list_scheduled_deliveries(
        self, dashboard_uuid: str, project_uuid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List scheduled deliveries (alerts / webhooks) for a dashboard."""
        pid = project_uuid or self._project_uuid
        if not (self.is_available and pid):
            return []
        try:
            result = await self._get(
                f"/api/v1/projects/{pid}/dashboards/{dashboard_uuid}/schedulers"
            )
            return result if isinstance(result, list) else []
        except Exception as exc:
            log.warning("lightdash_list_schedulers_failed error=%s", exc)
            return []

    async def create_alert(
        self,
        saved_chart_uuid: str,
        name: str,
        threshold: float,
        operator: str = "greaterThan",
        cron: str = "0 * * * *",
        webhook_url: Optional[str] = None,
        project_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a threshold-based alert on a saved chart.

        Parameters
        ----------
        saved_chart_uuid:
            UUID of the saved chart to monitor.
        name:
            Human-readable alert name.
        threshold:
            Numeric threshold value.
        operator:
            Comparison operator: ``"greaterThan"`` | ``"lessThan"``.
        cron:
            CRON schedule for evaluation (default: hourly).
        webhook_url:
            Destination URL for the webhook payload.
        """
        pid = project_uuid or self._project_uuid
        if not (self.is_available and pid):
            log.debug("lightdash_create_alert_skipped not_configured")
            return {}
        body: Dict[str, Any] = {
            "name": name,
            "savedChartUuid": saved_chart_uuid,
            "cron": cron,
            "format": "image",
            "options": {
                "threshold": {
                    "operator": operator,
                    "value": threshold,
                }
            },
        }
        if webhook_url:
            body["targets"] = [{"type": "slack", "webhookUrl": webhook_url}]
        try:
            return await self._post(
                f"/api/v1/projects/{pid}/schedulers", body
            )
        except Exception as exc:
            log.warning("lightdash_create_alert_failed error=%s", exc)
            return {}

    # ------------------------------------------------------------------
    # Convenience: embed URL builder
    # ------------------------------------------------------------------

    def get_dashboard_embed_url(
        self, dashboard_uuid: str, project_uuid: Optional[str] = None
    ) -> str:
        """Return the iframe-embeddable URL for a dashboard panel.

        Returns an empty string if Lightdash is not configured.
        """
        pid = project_uuid or self._project_uuid
        if not (self._base_url and pid):
            return ""
        return f"{self._base_url}/projects/{pid}/dashboards/{dashboard_uuid}/view"

    def get_chart_embed_url(self, saved_chart_uuid: str) -> str:
        """Return the iframe-embeddable URL for a saved chart."""
        if not self._base_url:
            return ""
        return f"{self._base_url}/saved/{saved_chart_uuid}/view"
