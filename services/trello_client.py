"""Lightweight client to consume Trello-related HTTP endpoints"""
import json
from typing import Any, Dict, Optional

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

class TrelloApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _post_json(self, path: str, body: dict | None = None, timeout: int = 10) -> dict:
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError

        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        req = Request(url=url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {"error": {"message": str(e)}}
            raise RuntimeError(payload.get("error", {}).get("message", f"HTTP {e.code}")) from e
        except URLError as e:
            raise RuntimeError(f"Network error contacting {url}: {e}") from e

    def get_next_card(self, timeout: int = 10):
        payload = self._post_json("/api/trello/getNextCard", None, timeout)
        if not payload.get("success"):
            raise RuntimeError(payload.get("error", {}).get("message", "Request failed"))
        return payload.get("data")

    def completed_card(self, card_id: str, result: bool, message: str, timeout: int = 10):
        payload = self._post_json("/api/trello/completedCard", {"cardId": card_id, "result": result, "message": message}, timeout)
        if not payload.get("success"):
            raise RuntimeError(payload.get("error", {}).get("message", "Request failed"))
        return payload.get("data")

    def delete_machine(self, timeout: int = 10):
        payload = self._post_json("/api/vast/destroyMachine", timeout)
        if not payload.get("success"):
            raise RuntimeError(payload.get("error", {}).get("message", "Request failed"))
        return payload.get("data")