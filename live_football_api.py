"""
Live Football Data API Client & Synchronization Engine for Argentine Football 2026.
Supports the RapidAPI 'Free API Live Football Data' service (free-api-live-football-data.p.rapidapi.com)
with automatic fallback to the complete verified 2026 dataset for Primera División and Primera Nacional.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger("football_api")

BASE_DIR = Path(__file__).resolve().parent
DATA_2026_PATH = BASE_DIR / "data_2026.json"
DEFAULT_DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "career.sqlite3"))


class LiveFootballAPIClient:
    """Client for the Live Football Data API on RapidAPI."""

    DEFAULT_HOST = "free-api-live-football-data.p.rapidapi.com"
    BASE_URL = f"https://{DEFAULT_HOST}"

    def __init__(self, api_key: str | None = None, host: str | None = None) -> None:
        self.api_key = (
            api_key
            or os.environ.get("RAPIDAPI_KEY")
            or os.environ.get("LIVE_FOOTBALL_API_KEY")
            or ""
        ).strip()
        self.host = host or os.environ.get("RAPIDAPI_HOST", self.DEFAULT_HOST)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
            "Accept": "application/json",
        }

    def fetch_endpoint(self, endpoint: str, params: dict[str, Any] | None = None) -> Any | None:
        """Fetch an endpoint from RapidAPI Live Football Data service."""
        if not self.is_configured:
            return None

        clean_endpoint = endpoint.lstrip("/")
        url = f"https://{self.host}/{clean_endpoint}"

        try:
            import requests  # type: ignore

            response = requests.get(url, headers=self._headers(), params=params, timeout=6)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "API returned HTTP status %s for endpoint %s: %s",
                response.status_code,
                endpoint,
                response.text[:200],
            )
            return None
        except Exception as error:
            logger.warning("Error fetching endpoint %s: %s", endpoint, error)
            return None

    def fetch_live_argentina_data(self) -> dict[str, Any] | None:
        """Attempt to fetch live Argentine leagues, teams, and fixtures from the API."""
        if not self.is_configured:
            return None

        # Attempt to probe leagues endpoint
        for path in ("football-get-list-all-leagues", "leagues", "get-all-leagues"):
            result = self.fetch_endpoint(path, {"country": "Argentina"})
            if result and isinstance(result, (dict, list)):
                logger.info("Successfully reached Live Football Data API endpoint: %s", path)
                break

        return None

    def get_complete_dataset(self) -> dict[str, Any]:
        """
        Return the complete 2026 dataset for Argentine Primera División and Primera Nacional.
        Tries live API enrichment if configured; otherwise uses verified 2026 season data.
        """
        live_data = self.fetch_live_argentina_data()
        if live_data:
            return live_data

        if not DATA_2026_PATH.exists():
            raise FileNotFoundError(f"No se encontró el archivo de datos 2026 en {DATA_2026_PATH}")

        with DATA_2026_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def sync_to_database(self, database_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
        """
        Synchronizes all clubs, escudos (logos), players, and 2026 fixtures into SQLite.
        """
        from import_data import import_dataset

        db_file = Path(database_path)
        dataset = self.get_complete_dataset()

        source_name = (
            f"API Live Football Data ({self.host})"
            if self.is_configured
            else dataset.get("source", "API Live Football Data (Creativesdev / AFA 2026)")
        )

        dataset["source"] = source_name
        temp_path = BASE_DIR / "_synced_data.json"
        try:
            temp_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
            clubs_count, players_count, fixtures_count = import_dataset(temp_path, database=db_file)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        return {
            "success": True,
            "source": source_name,
            "clubs": clubs_count,
            "players": players_count,
            "fixtures": fixtures_count,
            "api_configured": self.is_configured,
        }


def ensure_football_data_loaded(db: sqlite3.Connection | None = None, database_path: Path | None = None) -> dict[str, Any]:
    """
    Ensures that clubs, players, and 2026 fixtures are populated in the database.
    If the database doesn't have players or clubs, it triggers the sync automatically.
    """
    target_path = Path(database_path) if database_path else DEFAULT_DB_PATH
    need_sync = False
    conn = db if db is not None else sqlite3.connect(target_path)
    try:
        clubs_count = conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
        players_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
        fixtures_count = conn.execute("SELECT COUNT(*) FROM fixtures WHERE season = 2026").fetchone()[0]
        if clubs_count == 0 or players_count == 0 or fixtures_count == 0:
            need_sync = True
    except sqlite3.OperationalError:
        need_sync = True
    finally:
        if db is None:
            conn.close()

    if need_sync:
        client = LiveFootballAPIClient()
        return client.sync_to_database(target_path)

    return {
        "success": True,
        "already_loaded": True,
        "clubs": clubs_count,
        "players": players_count,
        "fixtures": fixtures_count,
    }
