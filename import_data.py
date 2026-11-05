from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from app import DATABASE, SHIRT_PATTERNS, infer_shirt_colors_from_logo, init_db

DIVISIONS = {"Primera División", "Primera Nacional"}


def validate_dataset(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("El archivo debe contener un objeto JSON.")
    if data.get("season") != 2026:
        raise ValueError("Este importador solo acepta datos de la temporada 2026.")
    if not isinstance(data.get("source"), str) or not data["source"].strip():
        raise ValueError("Indicá el proveedor o la URL de origen en 'source'.")
    for key in ("clubs", "players", "fixtures"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"El campo '{key}' debe ser una lista.")

    club_divisions: dict[str, str] = {}
    for index, club in enumerate(data["clubs"], start=1):
        if not isinstance(club, dict):
            raise ValueError(f"Club #{index}: se esperaba un objeto.")
        provider_id = str(club.get("provider_id", "")).strip()
        name = str(club.get("name", "")).strip()
        division = club.get("division")
        if not provider_id or not name or division not in DIVISIONS:
            raise ValueError(
                f"Club #{index}: provider_id, name y una division válida son obligatorios."
            )
        if provider_id in club_divisions:
            raise ValueError(f"ID de club duplicado: {provider_id}.")
        for field in ("shirt_primary", "shirt_secondary"):
            color = club.get(field)
            if color is not None and (
                not isinstance(color, str)
                or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color)
            ):
                raise ValueError(
                    f"Club #{index}: '{field}' debe ser un color hexadecimal #RRGGBB."
                )
        shirt_pattern = club.get("shirt_pattern")
        if shirt_pattern is not None and shirt_pattern not in SHIRT_PATTERNS:
            raise ValueError(f"Club #{index}: 'shirt_pattern' no es válido.")
        club_divisions[provider_id] = division

    player_ids: set[str] = set()
    for index, player in enumerate(data["players"], start=1):
        if not isinstance(player, dict):
            raise ValueError(f"Jugador #{index}: se esperaba un objeto.")
        provider_id = str(player.get("provider_id", "")).strip()
        name = str(player.get("name", "")).strip()
        if not provider_id or not name or str(player.get("club_provider_id", "")) not in club_divisions:
            raise ValueError(
                f"Jugador #{index}: provider_id, name y club_provider_id existente son obligatorios."
            )
        if provider_id in player_ids:
            raise ValueError(f"ID de jugador duplicado: {provider_id}.")
        player_ids.add(provider_id)
        for field, low, high in (("age", 14, 60), ("overall", 1, 100)):
            value = player.get(field)
            if value is not None and (not isinstance(value, int) or not low <= value <= high):
                raise ValueError(f"Jugador #{index}: '{field}' debe ser un entero entre {low} y {high}.")
        for field in ("market_value", "wage"):
            value = player.get(field, 0)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Jugador #{index}: '{field}' debe ser un entero no negativo.")

    for index, fixture in enumerate(data["fixtures"], start=1):
        if not isinstance(fixture, dict):
            raise ValueError(f"Partido #{index}: se esperaba un objeto.")
        division = fixture.get("division")
        if division not in DIVISIONS:
            raise ValueError(f"Partido #{index}: division inválida.")
        home_id = str(fixture.get("home_provider_id", ""))
        away_id = str(fixture.get("away_provider_id", ""))
        if home_id not in club_divisions or away_id not in club_divisions:
            raise ValueError(f"Partido #{index}: los equipos deben existir en la lista de clubes.")
        if home_id == away_id or club_divisions[home_id] != division or club_divisions[away_id] != division:
            raise ValueError(f"Partido #{index}: los equipos deben ser distintos y de la categoría indicada.")
        try:
            played_on = date.fromisoformat(str(fixture.get("played_on", "")))
        except ValueError as error:
            raise ValueError(f"Partido #{index}: 'played_on' debe usar el formato AAAA-MM-DD.") from error
        if played_on.year != 2026:
            raise ValueError(f"Partido #{index}: la fecha debe corresponder al año 2026.")
        if not isinstance(fixture.get("matchday"), int) or fixture["matchday"] < 1:
            raise ValueError(f"Partido #{index}: 'matchday' debe ser un entero positivo.")
    return data


def import_dataset(path: Path, database: Path = DATABASE) -> tuple[int, int, int]:
    try:
        data = validate_dataset(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as error:
        raise ValueError(f"JSON inválido: {error}") from error

    init_db(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        progress = connection.execute(
            "SELECT current_season FROM tournament_progress WHERE id = 1"
        ).fetchone()
        preserve_career_divisions = bool(progress and progress[0] > 1)
        with connection:
            for club in data["clubs"]:
                logo_val = str(club.get("logo") or "").strip() or None
                inferred_colors = infer_shirt_colors_from_logo(logo_val)
                shirt_primary = (
                    inferred_colors[0]
                    if inferred_colors
                    else club.get("shirt_primary")
                )
                shirt_secondary = (
                    inferred_colors[1]
                    if inferred_colors
                    else club.get("shirt_secondary")
                )
                shirt_pattern = "solid" if inferred_colors else club.get("shirt_pattern")
                existing = connection.execute(
                    "SELECT id FROM clubs WHERE provider_id = ? OR name = ?",
                    (str(club["provider_id"]), club["name"].strip()),
                ).fetchone()
                if existing:
                    division = club["division"]
                    if preserve_career_divisions:
                        stored_club = connection.execute(
                            "SELECT division FROM clubs WHERE id = ?",
                            (existing[0],),
                        ).fetchone()
                        division = stored_club[0]
                    connection.execute(
                        """UPDATE clubs SET
                           provider_id = ?, name = ?, division = ?, province = ?,
                           logo = COALESCE(?, logo),
                           shirt_primary = COALESCE(?, shirt_primary),
                           shirt_secondary = COALESCE(?, shirt_secondary),
                           shirt_pattern = COALESCE(?, shirt_pattern)
                           WHERE id = ?""",
                        (
                            str(club["provider_id"]),
                            club["name"].strip(),
                            division,
                            str(club.get("province") or "Argentina").strip(),
                            logo_val,
                            shirt_primary.lower() if shirt_primary else None,
                            shirt_secondary.lower() if shirt_secondary else None,
                            shirt_pattern,
                            existing[0],
                        ),
                    )
                else:
                    connection.execute(
                        """INSERT INTO clubs
                           (provider_id, name, division, province, logo,
                            shirt_primary, shirt_secondary, shirt_pattern)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            str(club["provider_id"]),
                            club["name"].strip(),
                            club["division"],
                            str(club.get("province") or "Argentina").strip(),
                            logo_val,
                            shirt_primary.lower() if shirt_primary else None,
                            shirt_secondary.lower() if shirt_secondary else None,
                            shirt_pattern,
                        ),
                    )
            club_map = dict(
                connection.execute(
                    "SELECT provider_id, id FROM clubs WHERE provider_id IS NOT NULL"
                ).fetchall()
            )
            for player in data["players"]:
                connection.execute(
                    """INSERT INTO players
                       (provider_id, club_id, name, position, age, nationality,
                        overall, base_overall, market_value, wage)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(provider_id) DO UPDATE SET
                       club_id=excluded.club_id, name=excluded.name, position=excluded.position,
                       age=excluded.age, nationality=excluded.nationality,
                       overall=excluded.overall, base_overall=excluded.base_overall,
                       market_value=excluded.market_value, wage=excluded.wage""",
                    (
                        str(player["provider_id"]),
                        club_map[str(player["club_provider_id"])],
                        player["name"].strip(),
                        str(player.get("position") or "SD").strip(),
                        player.get("age"),
                        str(player.get("nationality") or "Argentina").strip(),
                        int(player.get("overall", 60)),
                        int(player.get("overall", 60)),
                        player.get("market_value", 0),
                        player.get("wage", 0),
                    ),
                )
            for fixture in data["fixtures"]:
                connection.execute(
                    """INSERT INTO fixtures
                       (season, division, matchday, played_on, home_club_id, away_club_id)
                       VALUES (2026, ?, ?, ?, ?, ?)
                       ON CONFLICT(season, division, matchday, home_club_id, away_club_id)
                       DO UPDATE SET played_on=excluded.played_on""",
                    (
                        fixture["division"],
                        fixture["matchday"],
                        fixture["played_on"],
                        club_map[str(fixture["home_provider_id"])],
                        club_map[str(fixture["away_provider_id"])],
                    ),
                )
            connection.execute(
                """INSERT INTO data_imports
                   (season, source, clubs_count, players_count, fixtures_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (2026, data["source"].strip(), len(data["clubs"]), len(data["players"]), len(data["fixtures"])),
            )
        return len(data["clubs"]), len(data["players"]), len(data["fixtures"])
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa clubes, planteles y fixture 2026 desde un JSON autorizado."
    )
    parser.add_argument("json_file", type=Path, help="Archivo JSON normalizado")
    args = parser.parse_args()
    clubs, players, fixtures = import_dataset(args.json_file)
    print(
        f"Importación completada: {clubs} clubes, {players} jugadores y "
        f"{fixtures} partidos."
    )


if __name__ == "__main__":
    main()
