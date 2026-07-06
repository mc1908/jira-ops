"""Shared Jira REST client: auth headers, retries, pagination, error mapping."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

import requests

from .auth import resolve_token
from .config import Profile
from .errors import JiraOpsError

_DEFAULT_TIMEOUT = 30
_MAX_RETRIES = 3
_PAGE_SIZE = 50
_RESULT_CAP = 500


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    out = dict(headers)
    if "Authorization" in out:
        out["Authorization"] = "Bearer ***redacted***"
    return out


class JiraClient:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self._token = resolve_token(profile)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        if profile.proxy:
            self._session.proxies.update({"http": profile.proxy, "https": profile.proxy})

    # ------------------------------------------------------------------ #
    # low-level request
    # ------------------------------------------------------------------ #
    @property
    def _verify(self):
        if not self.profile.verify_tls:
            return False
        if self.profile.ca_cert_path:
            return self.profile.ca_cert_path
        return True

    def _url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.profile.api_base}/{path.lstrip('/')}"

    def guard_no_secret_leak(self, text: str) -> None:
        """Refuse to send a body that contains the live PAT.

        Defense-in-depth so a token can never be written to Jira (e.g. into a
        comment or transition note) even if it was accidentally interpolated
        into user-supplied text.
        """
        if self._token and text and self._token in text:
            raise JiraOpsError(
                "validation",
                "Refusing to send: the request body appears to contain your "
                "Jira token. Remove the secret from the text and retry.",
            )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> requests.Response:
        url = self._url(path)
        idempotent = method.upper() in ("GET", "HEAD")
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self._session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    timeout=_DEFAULT_TIMEOUT,
                    verify=self._verify,
                )
            except requests.exceptions.SSLError as exc:
                raise JiraOpsError("tls", f"TLS verification failed: {exc}") from exc
            except requests.exceptions.ConnectionError as exc:
                if idempotent and attempt < _MAX_RETRIES:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                raise JiraOpsError("network", f"Connection failed: {exc}") from exc
            except requests.exceptions.RequestException as exc:
                raise JiraOpsError("network", f"Request failed: {exc}") from exc

            if resp.status_code in (429, 500, 502, 503, 504) and idempotent and attempt < _MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if (retry_after or "").isdigit() else min(2 ** attempt, 8)
                time.sleep(delay)
                continue

            if resp.status_code >= 400:
                raise self._map_error(resp)
            return resp

    def _map_error(self, resp: requests.Response) -> JiraOpsError:
        status = resp.status_code
        messages: List[str] = []
        try:
            data = resp.json()
            if isinstance(data, dict):
                messages.extend(data.get("errorMessages", []) or [])
                errs = data.get("errors")
                if isinstance(errs, dict):
                    messages.extend(f"{k}: {v}" for k, v in errs.items())
        except ValueError:
            if resp.text:
                messages.append(resp.text[:300])

        joined = "; ".join(messages) if messages else resp.reason
        if status == 401:
            category = "auth"
        elif status == 403:
            category = "authorization"
        elif status == 404:
            category = "not_found"
        elif status == 429:
            category = "rate_limited"
        elif status == 400 and any("jql" in m.lower() for m in messages):
            category = "invalid_jql"
        elif status in (400, 422):
            category = "validation"
        elif status >= 500:
            category = "server"
        else:
            category = "unknown"
        return JiraOpsError(category, joined, status=status, jira_messages=messages)

    # ------------------------------------------------------------------ #
    # typed helpers
    # ------------------------------------------------------------------ #
    def get_json(self, path: str, params: Optional[dict] = None) -> Any:
        return self.request("GET", path, params=params).json()

    def post_json(self, path: str, body: dict) -> Any:
        resp = self.request("POST", path, json_body=body)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def put_json(self, path: str, body: dict) -> Any:
        resp = self.request("PUT", path, json_body=body)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    # ------------------------------------------------------------------ #
    # pagination
    # ------------------------------------------------------------------ #
    def search(
        self,
        jql: str,
        *,
        fields: Optional[Iterable[str]] = None,
        max_results: int = _RESULT_CAP,
        page_size: int = _PAGE_SIZE,
    ) -> List[dict]:
        collected: List[dict] = []
        start_at = 0
        field_list = list(fields) if fields else ["summary", "status", "assignee", "priority", "updated"]
        while len(collected) < max_results:
            batch = min(page_size, max_results - len(collected))
            body = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": batch,
                "fields": field_list,
            }
            data = self.post_json("search", body)
            issues = data.get("issues", [])
            collected.extend(issues)
            total = data.get("total", len(collected))
            start_at += len(issues)
            if not issues or start_at >= total:
                break
        return collected

    def paginate(self, path: str, *, key: str, params: Optional[dict] = None,
                 max_results: int = _RESULT_CAP, page_size: int = _PAGE_SIZE) -> List[dict]:
        """Generic startAt/maxResults pagination for endpoints returning {key: [...]}. """
        collected: List[dict] = []
        start_at = 0
        base_params = dict(params or {})
        while len(collected) < max_results:
            batch = min(page_size, max_results - len(collected))
            page_params = {**base_params, "startAt": start_at, "maxResults": batch}
            data = self.get_json(path, page_params)
            # Some DC endpoints return a bare list (e.g. /project).
            if isinstance(data, list):
                collected.extend(data)
                break
            values = data.get(key, [])
            collected.extend(values)
            total = data.get("total", len(collected))
            start_at += len(values)
            if not values or start_at >= total:
                break
        return collected
