import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as game
from import_data import import_dataset
from live_football_api import LiveFootballAPIClient, ensure_football_data_loaded


class CareerFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        game.DATABASE = Path(self.temp_dir.name) / "career.sqlite3"
        game.init_db(game.DATABASE)
        game.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = game.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_career(self, division="Primera División", **form_data):
        data = {
            "manager_name": "Entrenador",
            "club_name": "Deportivo Sur",
            "province": "Buenos Aires",
            "division": division,
        }
        data.update(form_data)
        return self.client.post(
            "/",
            data=data,
            follow_redirects=True,
        )

    def test_create_career_and_apply_all_twenty_daily_decisions(self):
        response = self.create_career()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Día 1".encode(), response.data)
        self.assertEqual(response.data.count(b'class="decision-option"'), 3)

        with game.app.app_context():
            career = game.get_career()
            first_budget = career["budget"]
            first_options = game.get_daily_options(game.get_db(), 1)
            self.assertEqual(first_budget, 0)
            self.assertEqual(len(first_options), 3)
            self.assertEqual(len({option["decision_key"] for option in first_options}), 3)
            self.assertGreaterEqual(len(game.DECISIONS), 50)

        refreshed = self.client.get("/club")
        self.assertEqual(refreshed.data.count(b'class="decision-option"'), 3)
        with game.app.app_context():
            refreshed_options = game.get_daily_options(game.get_db(), 1)
            self.assertEqual(
                [option["decision_key"] for option in first_options],
                [option["decision_key"] for option in refreshed_options],
            )

        for day in range(1, 21):
            with game.app.app_context():
                daily_options = game.get_daily_options(game.get_db(), day)
                daily_keys = [option["decision_key"] for option in daily_options]
                recent_options = game.get_db().execute(
                    """SELECT decision_key FROM daily_options
                       WHERE day BETWEEN ? AND ?""",
                    (max(1, day - 5), day - 1),
                ).fetchall()
                recent_keys = {option["decision_key"] for option in recent_options}
                self.assertEqual(len(daily_keys), 3)
                self.assertEqual(len(set(daily_keys)), 3)
                self.assertTrue(set(daily_keys).isdisjoint(recent_keys))
                decision_key = daily_keys[0]
            response = self.client.post(
                "/club/decision",
                data={"decision": decision_key},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            if day < 20:
                self.assertIn(f"Día {day + 1}".encode(), response.data)

        with game.app.app_context():
            career = game.get_career()
            self.assertEqual(career["phase"], "market")
            self.assertEqual(career["day"], 20)
            self.assertEqual(game.get_db().execute("SELECT COUNT(*) FROM decisions").fetchone()[0], 20)
        self.assertIn("mercado".encode(), self.client.get("/mercado").data.lower())

    def test_custom_kit_is_persisted_and_available_in_match_dashboard(self):
        setup = self.client.get("/")
        self.assertIn(b'name="shirt_primary"', setup.data)
        self.assertIn(b'name="shirt_secondary"', setup.data)
        self.assertIn(b'id="shirt-preview"', setup.data)

        self.create_career(
            shirt_primary="#112233",
            shirt_secondary="#ddeeff",
            shirt_pattern="diagonal",
        )
        with game.app.app_context():
            db = game.get_db()
            career = game.get_career()
            opponent_id = db.execute(
                """INSERT INTO clubs
                   (name, division, shirt_primary, shirt_secondary, shirt_pattern)
                   VALUES ('Camiseta Rival', 'Primera División',
                           '#aa1100', '#ffee00', 'halves')
                   RETURNING id"""
            ).fetchone()["id"]
            dashboard = game.build_match_dashboard(
                db,
                career,
                {
                    "home_club_id": None,
                    "away_club_id": opponent_id,
                    "round_number": 1,
                    "played_on": "2026-01-24",
                    "home_score": None,
                    "away_score": None,
                    "match_events": "[]",
                },
                "4-3-3",
                1,
            )

        self.assertEqual(dashboard["home"]["shirt_primary"], "#112233")
        self.assertEqual(dashboard["home"]["shirt_secondary"], "#ddeeff")
        self.assertEqual(dashboard["home"]["shirt_pattern"], "diagonal")
        self.assertEqual(dashboard["away"]["shirt_primary"], "#aa1100")
        self.assertEqual(dashboard["away"]["shirt_pattern"], "halves")

    def test_only_offered_choices_are_accepted_and_effects_are_moderate(self):
        self.create_career()
        with game.app.app_context():
            offered = game.get_daily_options(game.get_db(), 1)
        unoffered_key = next(key for key in game.DECISIONS if key not in {
            option["decision_key"] for option in offered
        })
        self.assertEqual(
            self.client.post("/club/decision", data={"decision": unoffered_key}).status_code,
            400,
        )
        with game.app.app_context():
            self.assertEqual(game.get_career()["day"], 1)
            self.assertEqual(game.get_career()["budget"], 0)
        positive_budget_changes = [
            effects["budget"]
            for choice in game.DECISIONS.values()
            if (effects := choice["effects"])["budget"] > 0
        ]
        self.assertTrue(positive_budget_changes)
        self.assertLessEqual(max(positive_budget_changes), 3_100_000)
        self.assertNotEqual(len(set(positive_budget_changes)), 1)

    def test_market_and_fixture_render_after_import(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "fixture test",
            "clubs": [
                {"provider_id": "a", "name": "Club A", "division": "Primera División"},
                {
                    "provider_id": "b",
                    "name": "Club B",
                    "division": "Primera División",
                    "shirt_primary": "#123456",
                    "shirt_secondary": "#abcdef",
                    "shirt_pattern": "stripes",
                },
            ],
            "players": [
                {
                    "provider_id": "p1",
                    "club_provider_id": "a",
                    "name": "Jugador Real",
                    "position": "ARQ",
                    "age": 23,
                    "overall": 65,
                    "market_value": 1000000,
                    "wage": 10000,
                }
            ],
            "fixtures": [
                {
                    "division": "Primera División",
                    "matchday": 1,
                    "played_on": "2026-01-24",
                    "home_provider_id": "a",
                    "away_provider_id": "b",
                }
            ],
        }
        source = Path(self.temp_dir.name) / "data.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (2, 1, 1))
        self.assertEqual(import_dataset(source, game.DATABASE), (2, 1, 1))
        with game.app.app_context():
            imports = game.get_db().execute("SELECT COUNT(*) FROM data_imports").fetchone()[0]
            career = game.get_career()
            opponent_id = game.get_db().execute(
                "SELECT id FROM clubs WHERE name = 'Club B'"
            ).fetchone()["id"]
            dashboard = game.build_match_dashboard(
                game.get_db(),
                career,
                {
                    "home_club_id": None,
                    "away_club_id": opponent_id,
                    "round_number": 1,
                    "played_on": "2026-01-24",
                    "home_score": None,
                    "away_score": None,
                    "match_events": "[]",
                },
                "4-3-3",
                1,
            )
        self.assertEqual(imports, 2)
        self.assertEqual(dashboard["away"]["shirt_primary"], "#123456")
        self.assertEqual(dashboard["away"]["shirt_secondary"], "#abcdef")
        self.assertEqual(dashboard["away"]["shirt_pattern"], "stripes")

        for day in range(1, 21):
            with game.app.app_context():
                decision_key = game.get_daily_options(game.get_db(), day)[0]["decision_key"]
            self.client.post("/club/decision", data={"decision": decision_key})
        with game.app.app_context():
            game.get_db().execute("UPDATE career SET budget = 2000000 WHERE id = 1")
            game.get_db().commit()
        response = self.client.get("/mercado")
        self.assertIn(b"Jugador Real", response.data)
        response = self.client.post("/mercado", data={"player_id": "1"}, follow_redirects=True)
        self.assertIn(b"nuevo jugador", response.data)
        response = self.client.get("/calendario")
        self.assertIn(b"Club A", response.data)
        self.assertIn(b"Club B", response.data)

    def test_copa_argentina_draw_reveals_pairs_and_eliminates_to_a_champion(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, ?)",
                [
                    ("Copa First Alpha", "Primera División"),
                    ("Copa First Beta", "Primera División"),
                    ("Copa Nacional Alpha", "Primera Nacional"),
                    ("Copa Nacional Beta", "Primera Nacional"),
                ],
            )
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            career = game.get_career()
            game.ensure_tournament_schedule(db, career)
            game.ensure_copa_argentina(db, career)
            initial_matches = db.execute(
                """SELECT * FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 1
                   ORDER BY match_number"""
            ).fetchall()
            self.assertEqual(len(initial_matches), 4)
            self.assertEqual(
                sum(bool(match["is_bye"]) for match in initial_matches), 3
            )
            participating_teams = {
                team_name
                for match in initial_matches
                for team_name in (match["home_team"], match["away_team"])
                if team_name != "Pasa libre"
            }
            self.assertEqual(len(participating_teams), 5)
            self.assertIn(career["club_name"], participating_teams)
            self.assertIn("Copa First Alpha", participating_teams)
            self.assertIn("Copa Nacional Alpha", participating_teams)
            db.execute(
                "UPDATE tournament_matches SET home_score = 0, away_score = 0"
            )
            total_league_rounds = db.execute(
                "SELECT MAX(round_number) FROM tournament_matches"
            ).fetchone()[0]
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (total_league_rounds,),
            )
            db.commit()
            self.assertTrue(game.season_is_complete(db))

        page = self.client.get("/copa-argentina")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Copa Argentina", page.data)
        self.assertIn(b"copa-bracket-layout", page.data)
        self.assertIn(b"copa-bracket-final", page.data)
        self.assertIn(b"REVELAR CRUCE 1", page.data)
        self.assertIn(b"SIMULAR TODA LA RONDA", page.data)
        self.client.post("/copa-argentina/sorteo", follow_redirects=True)
        with game.app.app_context():
            db = game.get_db()
            progress = db.execute(
                "SELECT draw_revealed FROM copa_argentina_progress WHERE id = 1"
            ).fetchone()
            self.assertEqual(progress["draw_revealed"], 1)
        drawn = self.client.post(
            "/copa-argentina/sorteo-completo", follow_redirects=True
        )
        self.assertEqual(drawn.status_code, 200)
        self.assertIn(b"Los partidos todav\xc3\xada no se jugaron", drawn.data)
        with game.app.app_context():
            db = game.get_db()
            round_matches = db.execute(
                """SELECT id, revealed, winner_team, is_bye FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 1"""
            ).fetchall()
            self.assertTrue(all(match["revealed"] for match in round_matches))
            self.assertTrue(
                all(
                    match["winner_team"] is None
                    for match in round_matches
                    if not match["is_bye"]
                )
            )
            first_playable_match_id = next(
                match["id"] for match in round_matches if not match["is_bye"]
            )
        simulated_one = self.client.post(
            f"/copa-argentina/jugar/{first_playable_match_id}",
            follow_redirects=True,
        )
        self.assertEqual(simulated_one.status_code, 200)
        with game.app.app_context():
            db = game.get_db()
            round_matches = db.execute(
                """SELECT winner_team, is_bye FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 1"""
            ).fetchall()
            self.assertEqual(
                sum(
                    match["winner_team"] is not None
                    for match in round_matches
                    if not match["is_bye"]
                ),
                1,
            )

        while True:
            with game.app.app_context():
                db = game.get_db()
                progress = db.execute(
                    """SELECT season_number, current_round, draw_revealed, is_complete
                       FROM copa_argentina_progress WHERE id = 1"""
                ).fetchone()
                if progress["is_complete"]:
                    break
                match_count = db.execute(
                    """SELECT COUNT(*) FROM copa_argentina_matches
                       WHERE season_number = ? AND round_number = ?""",
                    (progress["season_number"], progress["current_round"]),
                ).fetchone()[0]
                revealed = progress["draw_revealed"]
            if revealed < match_count:
                self.client.post("/copa-argentina/sorteo-completo")
            with game.app.app_context():
                db = game.get_db()
                pending_match_ids = [
                    row["id"]
                    for row in db.execute(
                        """SELECT id FROM copa_argentina_matches
                           WHERE season_number = ? AND round_number = ?
                             AND winner_team IS NULL AND is_bye = 0
                           ORDER BY match_number""",
                        (progress["season_number"], progress["current_round"]),
                    ).fetchall()
                ]
            for match_id in pending_match_ids:
                played = self.client.post(
                    f"/copa-argentina/jugar/{match_id}", follow_redirects=True
                )
                self.assertEqual(played.status_code, 200)
            advanced = self.client.post(
                "/copa-argentina/avanzar", follow_redirects=True
            )
            self.assertEqual(advanced.status_code, 200)

        with game.app.app_context():
            db = game.get_db()
            progress = db.execute(
                """SELECT is_complete, champion_team
                   FROM copa_argentina_progress WHERE id = 1"""
            ).fetchone()
            self.assertTrue(progress["is_complete"])
            self.assertTrue(progress["champion_team"])
            self.assertTrue(game.season_is_complete(db))
            self.assertIn(progress["champion_team"].encode(), advanced.data)

    def test_market_can_start_tournament_without_signing_all_affordable_players(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "early season test",
            "clubs": [
                {"provider_id": provider_id, "name": name, "division": "Primera División"}
                for provider_id, name in (("a", "Club A"), ("b", "Club B"))
            ],
            "players": [
                {
                    "provider_id": "p1",
                    "club_provider_id": "a",
                    "name": "Jugador Costoso",
                    "position": "DEF",
                    "age": 23,
                    "overall": 65,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "early-season.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        import_dataset(source, game.DATABASE)

        with game.app.app_context():
            game.get_db().execute(
                "UPDATE career SET phase = 'market', budget = 2_000_000 WHERE id = 1"
            )
            game.get_db().commit()
        can_still_sign = self.client.get("/mercado")
        self.assertIn(b"COMENZAR TEMPORADA", can_still_sign.data)
        started = self.client.post(
            "/mercado",
            data={"action": "start_tournament", "formation": "4-3-3"},
            follow_redirects=True,
        )
        self.assertEqual(started.status_code, 200)
        self.assertIn("Los cruces se revelan uno por uno".encode(), started.data)
        with game.app.app_context():
            self.assertEqual(game.get_career()["phase"], "season")
            self.assertEqual(
                game.get_db().execute(
                    "SELECT formation FROM tournament_progress WHERE id = 1"
                ).fetchone()["formation"],
                "4-3-3",
            )
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM signings").fetchone()[0],
                0,
            )

    def test_auto_build_market_team_uses_budget_and_builds_position_balanced_squad(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "automatic team test",
            "clubs": [
                {"provider_id": "a", "name": "Club A", "division": "Primera División"},
                {"provider_id": "b", "name": "Club B", "division": "Primera División"},
                {"provider_id": "c", "name": "Club C", "division": "Primera División"},
            ],
            "players": [
                {
                    "provider_id": f"p{number}",
                    "club_provider_id": "a",
                    "name": f"Jugador {number}",
                    "position": ("ARQ", "DEF", "MED", "DEL")[number % 4],
                    "age": 23,
                    "overall": 65 + number % 15,
                    "market_value": 500_000,
                    "wage": 10_000,
                }
                for number in range(1, 21)
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "automatic-team.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (3, 20, 0))
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                "INSERT INTO signings (player_id, fee) VALUES (1, 600000)"
            )
            db.execute(
                "UPDATE career SET phase = 'market', budget = 8000000 WHERE id = 1"
            )
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            market_page = self.client.get("/mercado")
        self.assertIn("ARMAR EQUIPO AL AZAR".encode(), market_page.data)
        assembled = self.client.post(
            "/mercado",
            data={
                "action": "auto_build_and_start",
                "formation": "4-3-3",
            },
            follow_redirects=True,
        )
        self.assertEqual(assembled.status_code, 200)
        self.assertIn("Equipo armado al azar".encode(), assembled.data)
        self.assertIn("Podés cambiar la alineación".encode(), assembled.data)
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(game.get_career()["phase"], "market")
            self.assertEqual(game.get_career()["budget"], 800_000)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM signings").fetchone()[0], 13)
            signed_positions = {
                row["position"]: row["count"]
                for row in db.execute(
                    """SELECT p.position, COUNT(*) AS count
                       FROM signings s JOIN players p ON p.id = s.player_id
                       GROUP BY p.position"""
                ).fetchall()
            }
            self.assertEqual(signed_positions, {"ARQ": 1, "DEF": 4, "DEL": 4, "MED": 4})
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM squad_lineup WHERE formation = '4-3-3'"
                ).fetchone()[0],
                11,
            )
            self.assertEqual(
                db.execute(
                    "SELECT formation FROM tournament_progress WHERE id = 1"
                ).fetchone()["formation"],
                "4-3-3",
            )
        started = self.client.post(
            "/mercado",
            data={"action": "start_tournament", "formation": "4-3-3"},
            follow_redirects=True,
        )
        self.assertEqual(started.status_code, 200)
        league = self.client.get("/calendario")
        self.assertEqual(league.status_code, 200)
        self.assertIn(b"4-3-3", league.data)

    def test_first_division_loan_costs_budget_and_expires_next_season(self):
        self.create_career("Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            club_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Loan Test Primera', 'Primera División')"""
            ).lastrowid
            player_id = db.execute(
                """INSERT INTO players
                   (club_id, provider_id, name, position, overall, market_value)
                   VALUES (?, 'loan-test-player', 'Jugador a préstamo',
                           'MED', 70, 1_000_000)""",
                (club_id,),
            ).lastrowid
            db.execute(
                "UPDATE career SET phase = 'market', budget = 200000 WHERE id = 1"
            )
            db.commit()

        market = self.client.get("/mercado")
        self.assertEqual(market.status_code, 200)
        self.assertIn(b"BUSCAR PR\xc3\x89STAMOS DESDE PRIMERA DIVISI\xc3\x93N", market.data)
        self.assertIn(b"$100.000", market.data)

        signed = self.client.post(
            "/mercado",
            data={"action": "request_loan", "player_id": str(player_id)},
            follow_redirects=True,
        )
        self.assertEqual(signed.status_code, 200)
        self.assertIn(b"lleg\xc3\xb3 a pr\xc3\xa9stamo", signed.data)
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(
                db.execute("SELECT budget FROM career WHERE id = 1").fetchone()[0],
                100_000,
            )
            signing = db.execute(
                "SELECT loan_season_number FROM signings WHERE player_id = ?",
                (player_id,),
            ).fetchone()
            self.assertEqual(signing["loan_season_number"], 1)

        sold = self.client.post(
            "/mercado",
            data={"action": "sell_player", "player_id": str(player_id)},
            follow_redirects=True,
        )
        self.assertIn(b"vuelve a su club", sold.data)
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team,
                    home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'Deportivo Sur', 'Rival Nacional',
                           60, 60, 0, 0)"""
            )
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.commit()
            self.assertTrue(game.season_is_complete(db))
            game.start_next_season(db)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM signings").fetchone()[0], 0
            )
            self.assertEqual(game.get_career()["phase"], "market")

    def test_copa_advances_odd_winners_and_can_be_played_from_fixtures(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, 'Primera División')",
                [("Club de liga A",), ("Club de liga B",)],
            )
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            career = game.get_career()
            game.ensure_tournament_schedule(db, career)
            season_number = game.current_season_number(db)
            db.execute("DELETE FROM copa_argentina_matches")
            db.execute("DELETE FROM copa_argentina_progress")
            db.execute(
                """INSERT INTO copa_argentina_progress
                   (id, season_number, current_round, draw_revealed, is_complete)
                   VALUES (1, ?, 1, 0, 0)""",
                (season_number,),
            )
            teams = [
                {"name": f"Club de prueba {index}", "club_id": None, "overall": 60}
                for index in range(50)
            ]
            game.create_copa_argentina_round(db, season_number, 1, teams)
            total_league_rounds = db.execute(
                "SELECT MAX(round_number) FROM tournament_matches"
            ).fetchone()[0]
            copa_matchday = game.copa_argentina_league_matchday(
                db, season_number, 1, total_league_rounds
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (copa_matchday,),
            )
            db.execute(
                """UPDATE copa_argentina_matches
                   SET revealed = 1, home_score = 1, away_score = 0,
                       winner_team = home_team, winner_club_id = home_club_id,
                       winner_overall = home_overall
                   WHERE season_number = ? AND round_number = 1""",
                (season_number,),
            )
            db.execute(
                """UPDATE copa_argentina_progress
                   SET draw_revealed = (
                       SELECT COUNT(*) FROM copa_argentina_matches
                       WHERE season_number = ? AND round_number = 1
                   )
                   WHERE id = 1""",
                (season_number,),
            )
            db.commit()

        fixture_page = self.client.get("/calendario")
        self.assertEqual(fixture_page.status_code, 200)
        self.assertIn(b"COPA ARGENTINA", fixture_page.data)
        self.assertIn(b"SORTEAR SIGUIENTE RONDA", fixture_page.data)
        advanced = self.client.post(
            "/copa-argentina/avanzar",
            data={"return_to": "fixtures"},
            follow_redirects=True,
        )
        self.assertEqual(advanced.status_code, 200)
        with game.app.app_context():
            db = game.get_db()
            next_matchday = game.copa_argentina_league_matchday(
                db,
                season_number,
                2,
                db.execute(
                    "SELECT MAX(round_number) FROM tournament_matches"
                ).fetchone()[0],
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (next_matchday,),
            )
            db.commit()
            round_two = db.execute(
                """SELECT is_bye FROM copa_argentina_matches
                   WHERE season_number = ? AND round_number = 2""",
                (season_number,),
            ).fetchall()
            self.assertEqual(len(round_two), 13)
            self.assertEqual(sum(bool(match["is_bye"]) for match in round_two), 1)
        next_fixture_page = self.client.get("/calendario")
        self.assertIn(b"Ronda 2", next_fixture_page.data)
        self.assertIn(b"VER LLAVE COMPLETA", next_fixture_page.data)

    def test_copa_prize_scale_and_payment_are_idempotent(self):
        self.create_career()
        self.assertEqual(game.copa_argentina_prize(1, 6), 250_000)
        self.assertEqual(game.copa_argentina_prize(2, 6), 250_000)
        self.assertEqual(game.copa_argentina_prize(3, 6), 350_000)
        self.assertEqual(game.copa_argentina_prize(4, 6), 500_000)
        self.assertEqual(game.copa_argentina_prize(5, 6), 1_000_000)
        self.assertEqual(game.copa_argentina_prize(6, 6), 2_000_000)
        self.assertEqual(game.copa_argentina_prize(6, 6, champion=True), 3_500_000)
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                """INSERT INTO copa_argentina_progress
                   (id, season_number, current_round) VALUES (1, 1, 1)"""
            )
            db.commit()
            self.assertTrue(game.pay_copa_argentina_prize(db, 3_500_000))
            self.assertFalse(game.pay_copa_argentina_prize(db, 3_500_000))
            self.assertEqual(game.get_career()["budget"], 3_500_000)

    def test_copa_bracket_fills_the_64_team_draw_with_byes(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            teams = [
                {"name": f"Club {number}", "club_id": None, "overall": 60}
                for number in range(49)
            ]
            bracket_size = 1 << (len(teams) - 1).bit_length()
            game.create_copa_argentina_round(
                db, 1, 1, teams, bye_count=bracket_size - len(teams)
            )
            match_count, bye_count = db.execute(
                """SELECT COUNT(*), SUM(is_bye)
                   FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 1"""
            ).fetchone()
            self.assertEqual(match_count, 32)
            self.assertEqual(bye_count, 15)
            self.assertEqual(game.copa_argentina_final_round(db, 1), 6)
            self.assertEqual(
                [
                    game.copa_argentina_league_matchday(db, 1, cup_round, 30)
                    for cup_round in range(1, 7)
                ],
                [4, 8, 13, 17, 22, 26],
            )

    def test_copa_round_of_16_pairs_winners_of_adjacent_round_of_32_matches(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            teams = [
                {"name": f"Club {number}", "club_id": None, "overall": 60}
                for number in range(1, 65)
            ]
            with patch("app.random.shuffle", side_effect=lambda drawn_teams: None):
                game.create_copa_argentina_round(db, 1, 1, teams)
            first_round = db.execute(
                """SELECT match_number, home_team, home_club_id, home_overall
                   FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 1
                   ORDER BY match_number"""
            ).fetchall()
            for match in first_round:
                db.execute(
                    """UPDATE copa_argentina_matches
                       SET winner_team = ?, winner_club_id = ?, winner_overall = ?,
                           revealed = 1
                       WHERE season_number = 1 AND round_number = 1
                         AND match_number = ?""",
                    (
                        f"Ganador {match['match_number']}",
                        match["home_club_id"],
                        match["home_overall"],
                        match["match_number"],
                    ),
                )
            db.execute(
                """INSERT INTO copa_argentina_progress
                   (id, season_number, current_round, draw_revealed)
                   VALUES (1, 1, 1, ?)""",
                (len(first_round),),
            )

            next_round, complete = game.advance_copa_argentina_round(db)

            self.assertEqual(next_round, 2)
            self.assertFalse(complete)
            round_of_16_match = db.execute(
                """SELECT home_team, away_team FROM copa_argentina_matches
                   WHERE season_number = 1 AND round_number = 2 AND match_number = 16"""
            ).fetchone()
            self.assertEqual(
                (round_of_16_match["home_team"], round_of_16_match["away_team"]),
                ("Ganador 31", "Ganador 32"),
            )

    def test_copa_round_is_playable_on_its_league_matchday_and_can_simulate_all(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, 'Primera División')",
                [("Club de Copa A",), ("Club de Copa B",), ("Club de Copa C",)],
            )
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            career = game.get_career()
            game.ensure_tournament_schedule(db, career)
            game.ensure_copa_argentina(db, career)
            league_rounds = db.execute(
                "SELECT MAX(round_number) FROM tournament_matches"
            ).fetchone()[0]
            due_matchday = game.copa_argentina_league_matchday(
                db, 1, 1, league_rounds
            )
            self.assertEqual(due_matchday, 1)
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (due_matchday,),
            )
            db.execute(
                """UPDATE tournament_matches SET home_score = 0, away_score = 0
                   WHERE round_number = ?""",
                (due_matchday,),
            )
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            page = self.client.get("/calendario")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"FECHA 01 \xc2\xb7 COPA ARGENTINA", page.data)
        self.assertIn(b"REVELAR CRUCE", page.data)
        blocked = self.client.post("/torneo/avanzar", follow_redirects=True)
        self.assertIn(b"Termin\xc3\xa1 y avanz\xc3\xa1 la ronda de Copa Argentina", blocked.data)
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute(
                    "SELECT current_round FROM tournament_progress WHERE id = 1"
                ).fetchone()[0],
                due_matchday,
            )

        revealed = self.client.post(
            "/copa-argentina/sorteo-completo",
            data={"return_to": "fixtures"},
            follow_redirects=True,
        )
        self.assertIn(b"JUGAR", revealed.data)
        simulated = self.client.post(
            "/copa-argentina/simular-ronda",
            data={"return_to": "fixtures"},
            follow_redirects=True,
        )
        self.assertEqual(simulated.status_code, 200)
        self.assertIn(b"Se simularon todos los partidos de la ronda 1", simulated.data)
        self.assertIn(b"Pr\xc3\xb3xima Copa Argentina: fecha 02, ronda 2.", simulated.data)
        with game.app.app_context():
            db = game.get_db()
            progress = db.execute(
                "SELECT current_round, is_complete FROM copa_argentina_progress WHERE id = 1"
            ).fetchone()
            self.assertEqual(progress["current_round"], 2)
            self.assertFalse(progress["is_complete"])
            self.assertEqual(
                db.execute(
                    """SELECT COUNT(*) FROM copa_argentina_matches
                       WHERE season_number = 1 AND round_number = 1
                         AND winner_team IS NULL"""
                ).fetchone()[0],
                0,
            )

        advanced = self.client.post("/torneo/avanzar", follow_redirects=True)
        self.assertEqual(advanced.status_code, 200)
        self.assertIn(b"FECHA 02 \xc2\xb7 COPA ARGENTINA", advanced.data)
        self.assertIn(b"SIMULAR TODA LA RONDA", advanced.data)
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute(
                    "SELECT current_round FROM tournament_progress WHERE id = 1"
                ).fetchone()[0],
                2,
            )

    def test_copa_champion_page_shows_supplied_trophy_image(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.execute(
                """INSERT INTO copa_argentina_progress
                   (id, season_number, current_round, is_complete, champion_team)
                   VALUES (1, 1, 1, 1, 'Deportivo Sur')"""
            )
            db.execute(
                """INSERT INTO copa_argentina_matches
                   (season_number, round_number, match_number, home_team, away_team,
                    home_overall, away_overall, home_score, away_score, winner_team,
                    winner_overall, revealed)
                   VALUES (1, 1, 1, 'Deportivo Sur', 'Rival', 60, 60, 2, 1,
                           'Deportivo Sur', 60, 1)"""
            )
            db.commit()
        page = self.client.get("/copa-argentina")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"copa-argentina-trophy-cutout.png", page.data)
        self.assertIn(b"Trofeo de la Copa Argentina", page.data)
        self.assertIn(b'class="copa-champion-icon"', page.data)

    def test_season_awards_use_competition_trophies_and_red_relegation_arrow(self):
        self.create_career()
        award_rows = [
            ("champion_1", "Campeón de liga", "Campeón de la liga"),
            ("promotion_1", "Ascendido directo", "Ascenso directo a Primera División"),
            ("playoff_promotion_1", "Ascendido por playoff", "Ascenso a Primera División por playoff"),
            ("copa_argentina_champion_1", "Campeón de Copa", "Campeón de la Copa Argentina"),
            ("relegation_1", "Descendido", "Descenso a Primera Nacional"),
        ]
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                "UPDATE career SET phase = 'season', club_name = 'Campeón de liga' WHERE id = 1"
            )
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, ?)",
                [
                    ("Club de Primera", "Primera División"),
                    ("Club Nacional", "Primera Nacional"),
                ],
            )
            db.executemany(
                """INSERT INTO tournament_awards (award_type, team_name, description)
                   VALUES (?, ?, ?)""",
                award_rows,
            )
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            page = self.client.get("/calendario")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"/static/competitions/league-trophy-cutout.png", page.data)
        self.assertIn(b"/static/competitions/primera-division-trophy-cutout.png", page.data)
        self.assertIn(b"/static/competitions/copa-argentina-trophy-cutout.png", page.data)
        self.assertRegex(
            page.data,
            re.compile(
                b'primera-division-trophy-cutout\\.png" alt="Trofeo de la Primera Divisi\xc3\xb3n">.*?<h2>Campe\xc3\xb3n de liga</h2>',
                re.DOTALL,
            ),
        )
        self.assertRegex(
            page.data,
            re.compile(
                b'league-trophy-cutout\\.png" alt="Trofeo de ascenso">.*?<h2>Ascendido directo</h2>',
                re.DOTALL,
            ),
        )
        self.assertIn(b'alt="Trofeo de la Copa Argentina"', page.data)
        self.assertIn(b'class="award-relegation-arrow"', page.data)
        self.assertIn(b"Ganador del playoff de ascenso", page.data)
        self.assertNotIn(b"gan\xc3\xb3 el playoff y ascendi\xc3\xb3 a Primera Divisi\xc3\xb3n", page.data)
        self.assertIn(b"Campe\xc3\xb3n de la Copa Argentina.", page.data)

    def test_new_career_restores_official_divisions_and_saves_custom_crest(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                """INSERT INTO clubs (provider_id, name, division)
                   VALUES ('arg-river', 'River Plate', 'Primera Nacional')"""
            )
            player_id = db.execute(
                """INSERT INTO players (club_id, name, position)
                   SELECT id, 'Jugador histórico', 'DEF' FROM clubs
                   WHERE provider_id = 'arg-river'"""
            ).lastrowid
            db.execute(
                """INSERT INTO player_match_stats
                   (season_number, competition, match_id, player_id, goals)
                   VALUES (1, 'league', 1, ?, 1)""",
                (player_id,),
            )
            db.execute(
                "INSERT INTO player_development_runs (season_number) VALUES (1)"
            )
            db.execute(
                "INSERT INTO season_decisions (season_number, after_round, event_key) "
                "VALUES (1, 2, 'fatigue')"
            )
            db.commit()

        reset = self.client.post("/reiniciar", follow_redirects=True)
        self.assertEqual(reset.status_code, 200)
        self.assertIn(b"Color principal", reset.data)
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(
                db.execute(
                    "SELECT division FROM clubs WHERE provider_id = 'arg-river'"
                ).fetchone()["division"],
                "Primera División",
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM season_decisions").fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM player_match_stats").fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM player_development_runs").fetchone()[0],
                0,
            )

        created = self.client.post(
            "/",
            data={
                "manager_name": "Nueva DT",
                "club_name": "Estrella Sur",
                "province": "Córdoba",
                "division": "Primera Nacional",
                "crest_primary": "#123456",
                "crest_secondary": "#abcdef",
                "crest_symbol": "stripes",
                "crest_shape": "round",
            },
            follow_redirects=True,
        )
        self.assertEqual(created.status_code, 200)
        with game.app.app_context():
            career = game.get_career()
            self.assertEqual(career["crest_primary"], "#123456")
            self.assertEqual(career["crest_secondary"], "#abcdef")
            self.assertEqual(career["crest_symbol"], "stripes")
            self.assertEqual(career["crest_shape"], "round")
        crest = self.client.get("/escudo-club.svg")
        self.assertEqual(crest.status_code, 200)
        self.assertIn(b"#123456", crest.data)
        self.assertIn(b"#abcdef", crest.data)
        self.assertIn(b"clip-path", crest.data)
        self.assertIn(b"<circle", crest.data)

    def test_all_crest_symbols_are_offered_and_render_distinctly(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(game.CREST_SYMBOLS), 12)
        rendered_crests = {
            game.build_club_crest_svg(
                "Club de prueba", "#123456", "#abcdef", symbol
            )
            for symbol in game.CREST_SYMBOLS
        }
        self.assertEqual(len(rendered_crests), len(game.CREST_SYMBOLS))
        for label in game.CREST_SYMBOLS.values():
            self.assertIn(label.encode(), page.data)
        self.assertEqual(len(game.CREST_SHAPES), 4)
        rendered_shapes = {
            game.build_club_crest_svg(
                "Club de prueba", "#123456", "#abcdef", "star", shape
            )
            for shape in game.CREST_SHAPES
        }
        self.assertEqual(len(rendered_shapes), len(game.CREST_SHAPES))
        for label in game.CREST_SHAPES.values():
            self.assertIn(label.encode(), page.data)

    def test_squad_limit_is_25_for_existing_and_new_careers(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE tournament_progress SET signing_limit = 16 WHERE id = 1")
            db.commit()

        game.init_db(game.DATABASE)
        with game.app.app_context():
            self.assertEqual(game.current_squad_limit(game.get_db()), 25)

        self.client.post("/reiniciar")
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(game.current_squad_limit(db), 25)
            self.assertEqual(
                db.execute(
                    "SELECT signing_limit FROM tournament_progress WHERE id = 1"
                ).fetchone()["signing_limit"],
                25,
            )

    def test_market_prices_filter_and_squad_limit_start_the_season(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "market rules test",
            "clubs": [
                {"provider_id": "a", "name": "Club A", "division": "Primera División"},
                {"provider_id": "b", "name": "Club B", "division": "Primera División"},
            ],
            "players": [
                {
                    "provider_id": f"p{number}",
                    "club_provider_id": "b" if number == 2 else "a",
                    "name": f"Jugador {number}",
                    "position": "ARQ" if number % 2 else "DEF",
                    "age": 23,
                    "overall": 55 + number,
                    "market_value": 5_000_000 if number == 1 else 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 28)
            ],
            "fixtures": [
                {
                    "division": "Primera División",
                    "matchday": 1,
                    "played_on": "2026-01-24",
                    "home_provider_id": "a",
                    "away_provider_id": "b",
                }
            ],
        }
        source = Path(self.temp_dir.name) / "market-rules.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (2, 27, 1))
        with game.app.app_context():
            game.get_db().execute(
                "UPDATE career SET phase = 'market', budget = 100000000 WHERE id = 1"
            )
            game.get_db().commit()

        filtered = self.client.get("/mercado?position=ARQ&name=Jugador%201")
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(b"<strong>Jugador 1</strong>", filtered.data)
        self.assertNotIn(b"<strong>Jugador 2</strong>", filtered.data)
        self.assertIn(b'id="position-filter"', filtered.data)
        self.assertIn(b'id="team-filter"', filtered.data)
        self.assertIn(b'id="player-name-filter"', filtered.data)
        self.assertIn(b'id="overall-filter"', filtered.data)
        self.assertIn(b"$5.000.000", filtered.data)
        defenders = self.client.get("/mercado?position=DEF&page=2")
        self.assertIn(b"<strong>Jugador 2</strong>", defenders.data)
        self.assertNotIn(b"<strong>Jugador 1</strong>", defenders.data)
        team_b = self.client.get("/mercado?team=2")
        self.assertIn(b"<strong>Jugador 2</strong>", team_b.data)
        self.assertNotIn(b"<strong>Jugador 3</strong>", team_b.data)
        by_name = self.client.get("/mercado?name=Jugador%201")
        self.assertIn(b"<strong>Jugador 1</strong>", by_name.data)
        self.assertNotIn(b"<strong>Jugador 2</strong>", by_name.data)
        by_overall = self.client.get("/mercado?overall_max=60")
        self.assertEqual(by_overall.status_code, 200)
        self.assertIn(b"OVR m\xc3\xa1ximo", by_overall.data)
        self.assertIn(b'name="overall_max"', by_overall.data)
        self.assertIn(b'value="60"', by_overall.data)
        self.assertIn(b"<strong>Jugador 1</strong>", by_overall.data)
        self.assertNotIn(b"<strong>Jugador 27</strong>", by_overall.data)
        self.assertEqual(
            self.client.get("/mercado?overall_max=100").status_code,
            400,
        )

        for player_id in range(1, 26):
            response = self.client.post("/mercado", data={"player_id": str(player_id)})
            if player_id < 25:
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location.partition("?")[0], "/mercado")
        self.assertEqual(response.location.partition("?")[0], "/mercado")
        with game.app.app_context():
            career = game.get_career()
            signings = game.get_db().execute(
                "SELECT COUNT(*) FROM signings"
            ).fetchone()[0]
            first_fee = game.get_db().execute(
                "SELECT fee FROM signings WHERE player_id = 1"
            ).fetchone()[0]
        self.assertEqual(career["phase"], "market")
        self.assertEqual(signings, game.MAX_SQUAD_SIZE)
        self.assertEqual(first_fee, game.MAX_FIRST_DIVISION_TRANSFER_FEE)

        rejected = self.client.post(
            "/mercado",
            data={"player_id": "26"},
            follow_redirects=True,
        )
        self.assertTrue(rejected.request.path.endswith("/mercado"))
        self.assertIn("Vendé jugadores para poder incorporar".encode(), rejected.data)
        self.assertIn(b"Vender jugadores", rejected.data)
        with game.app.app_context():
            budget_before_sale = game.get_career()["budget"]
        sold = self.client.post(
            "/mercado",
            data={"action": "sell_player", "player_id": "1"},
            follow_redirects=True,
        )
        self.assertIn("Recibiste $500.000".encode(), sold.data)
        with game.app.app_context():
            self.assertEqual(game.get_career()["budget"], budget_before_sale + 500_000)
        purchased_after_sale = self.client.post(
            "/mercado", data={"player_id": "26"}, follow_redirects=True
        )
        self.assertIn("Jugador 26 ya es nuevo jugador".encode(), purchased_after_sale.data)
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM signings").fetchone()[0],
                game.MAX_SQUAD_SIZE,
            )
            db = game.get_db()
            db.execute("DROP TRIGGER limit_signings_before_insert")
            db.execute(
                "INSERT INTO signings (player_id, fee) VALUES (27, 200000)"
            )
            db.execute(
                "UPDATE career SET phase = 'market', budget = 123 WHERE id = 1"
            )
            db.commit()
        game.init_db(game.DATABASE)
        with game.app.app_context():
            career = game.get_career()
            self.assertEqual(career["phase"], "market")
            self.assertEqual(career["budget"], 200123)
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM signings").fetchone()[0],
                game.MAX_SQUAD_SIZE,
            )
            with self.assertRaises(game.sqlite3.IntegrityError):
                game.get_db().execute(
                    "INSERT INTO signings (player_id, fee) VALUES (1, 200000)"
                )
            game.get_db().rollback()

    def test_market_paginates_twelve_players_and_preserves_filters(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "pagination test",
            "clubs": [
                {"provider_id": "page-a", "name": "Club Página", "division": "Primera División"}
            ],
            "players": [
                {
                    "provider_id": f"page-player-{number}",
                    "club_provider_id": "page-a",
                    "name": f"Jugador Página {number:02}",
                    "position": "DEF",
                    "age": 20 + number % 10,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 26)
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "pagination.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        import_dataset(source, game.DATABASE)
        with game.app.app_context():
            game.get_db().execute(
                "UPDATE career SET phase = 'market', budget = 100000000 WHERE id = 1"
            )
            game.get_db().commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            first_page = self.client.get("/mercado?position=DEF")
            second_page = self.client.get(
                "/mercado?position=DEF&overall_max=70&page=2"
            )
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.data.count(b'class="position-tag">DEF</span>'), 12)
        self.assertIn(b"Mostrando 1", first_page.data)
        self.assertIn(b"P\xc3\x81GINA 1 DE 3", first_page.data)
        self.assertIn(b"position=DEF", first_page.data)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.data.count(b'class="position-tag">DEF</span>'), 12)
        self.assertIn(b"P\xc3\x81GINA 2 DE 3", second_page.data)
        self.assertIn(b"Jugador P\xc3\xa1gina 13", second_page.data)
        self.assertNotIn(b"Jugador P\xc3\xa1gina 01", second_page.data)
        self.assertIn(b'name="overall_max"', second_page.data)
        self.assertIn(b'value="70"', second_page.data)

    def test_market_shows_selected_formation_and_bench(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            club_id = db.execute(
                """INSERT INTO clubs (name, division) VALUES
                   ('Club de prueba', 'Primera División') RETURNING id"""
            ).fetchone()["id"]
            positions = ["ARQ"] + ["DEF"] * 5 + ["MED"] * 5 + ["DEL"] * 5
            player_ids = []
            for number, position in enumerate(positions, start=1):
                player_id = db.execute(
                    """INSERT INTO players
                       (club_id, name, position, overall, market_value)
                       VALUES (?, ?, ?, ?, ?) RETURNING id""",
                    (club_id, f"Plantel {number:02}", position, 70 + number, 500_000),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO signings (player_id, fee) VALUES (?, ?)",
                    (player_id, 600_000),
                )
                player_ids.append(player_id)
            db.execute("UPDATE career SET phase = 'market' WHERE id = 1")
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            response = self.client.get("/mercado?formation=4-3-3")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Formaci\xc3\xb3n y plantel", response.data)
        self.assertIn(b"4-4-2", response.data)
        self.assertIn(b"4-3-3", response.data)
        self.assertIn(b"4-2-3-1", response.data)
        self.assertIn(b'class="formation-option active"', response.data)
        self.assertIn(b'aria-label="Formaci\xc3\xb3n 4-3-3"', response.data)
        self.assertEqual(response.data.count(b'class="pitch-player"'), 11)
        self.assertEqual(response.data.count(b'class="lineup-player"'), 16)
        self.assertEqual(response.data.count(b'class="lineup-player-value"'), 11)
        self.assertNotIn(b"<select name=\"starter_id\"", response.data)
        self.assertIn(b"/static/lineup.js?v=20261028.2", response.data)
        self.assertEqual(response.data.count(b'class="substitute-player"'), 5)
        self.assertIn(b"Banco de suplentes", response.data)
        self.assertIn(b"Plantel 16", response.data)
        with game.app.app_context():
            db = game.get_db()
            signed_squad = db.execute(
                """SELECT p.*, s.fee, c.name AS origin_club_name,
                          c.logo AS origin_club_logo
                   FROM signings s JOIN players p ON p.id = s.player_id
                   LEFT JOIN clubs c ON c.id = p.club_id"""
            ).fetchall()
            initial_lines, initial_bench = game.arrange_squad(signed_squad, "4-3-3")
        initial_starters = [
            player["id"] for line in initial_lines for player in line["players"]
        ]
        promoted_player = initial_bench[0]["id"]
        replaced_player = initial_starters[0]
        updated_starters = [promoted_player, *initial_starters[1:]]

        invalid = self.client.post(
            "/mercado/alineacion",
            data={"formation": "4-3-3", "starter_id": [*updated_starters[:-1], updated_starters[0]]},
        )
        self.assertEqual(invalid.status_code, 400)
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM squad_lineup").fetchone()[0],
                0,
            )

        with patch("live_football_api.ensure_football_data_loaded"):
            saved = self.client.post(
                "/mercado/alineacion",
                data={"formation": "4-3-3", "starter_id": updated_starters},
                follow_redirects=True,
            )
            self.assertEqual(saved.status_code, 200)
            self.assertIn(b"Alineaci\xc3\xb3n guardada", saved.data)
            with game.app.app_context():
                db = game.get_db()
                saved_rows = db.execute(
                    """SELECT slot_number, player_id FROM squad_lineup
                       WHERE formation = '4-3-3' ORDER BY slot_number"""
                ).fetchall()
                saved_squad = db.execute(
                    """SELECT p.*, s.fee, c.name AS origin_club_name,
                              c.logo AS origin_club_logo
                       FROM signings s JOIN players p ON p.id = s.player_id
                       LEFT JOIN clubs c ON c.id = p.club_id"""
                ).fetchall()
                stored_lines, stored_bench = game.arrange_squad(
                    saved_squad,
                    "4-3-3",
                    {row["slot_number"]: row["player_id"] for row in saved_rows},
                )
        self.assertEqual([row["player_id"] for row in saved_rows], updated_starters)
        self.assertNotIn(promoted_player, [player["id"] for player in stored_bench])
        self.assertIn(replaced_player, [player["id"] for player in stored_bench])
        self.assertEqual(sum(len(line["players"]) for line in stored_lines), 11)

    def test_transfer_caps_and_continental_qualification_by_division_and_place(self):
        self.assertEqual(
            game.transfer_fee(10_000_000, "Primera División"),
            game.MAX_FIRST_DIVISION_TRANSFER_FEE,
        )
        self.assertEqual(
            game.transfer_fee(10_000_000, "Primera Nacional"),
            game.MAX_TRANSFER_FEE,
        )
        self.assertEqual(game.continental_qualification("Primera División", 1), "libertadores")
        self.assertEqual(game.continental_qualification("Primera División", 3), "libertadores")
        self.assertEqual(game.continental_qualification("Primera División", 4), "sudamericana")
        self.assertEqual(game.continental_qualification("Primera División", 9), "sudamericana")
        self.assertIsNone(game.continental_qualification("Primera División", 10))
        self.assertIsNone(game.continental_qualification("Primera Nacional", 1))

    def test_first_division_champion_sees_libertadores_qualification(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                "UPDATE career SET phase = 'season', club_name = 'Aardvark FC' WHERE id = 1"
            )
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, 'Primera División')",
                [("Club A",), ("Club B",), ("Club C",)],
            )
            career = game.get_career()
            game.ensure_tournament_schedule(db, career)
            db.execute(
                "UPDATE tournament_matches SET home_score = 0, away_score = 0"
            )
            total_rounds = db.execute(
                "SELECT MAX(round_number) FROM tournament_matches"
            ).fetchone()[0]
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (total_rounds,),
            )
            db.commit()

        response = self.client.get("/calendario")
        self.assertEqual(response.status_code, 200)
        self.assertIn("¡Campeón y clasificado a la Libertadores!".encode(), response.data)
        self.assertIn(b"competitions/libertadores.png", response.data)
        self.assertIn("Saliste campeón del torneo".encode(), response.data)
        with game.app.app_context():
            game.get_db().execute(
                "UPDATE career SET club_name = 'ZZZ FC' WHERE id = 1"
            )
            game.get_db().commit()
        sudamericana = self.client.get("/calendario")
        self.assertIn("¡Clasificado a la Sudamericana!".encode(), sudamericana.data)
        self.assertIn(b"competitions/sudamericana.png", sudamericana.data)

    def test_tournament_runs_weekly_rounds_and_updates_league_table(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "tournament test",
            "clubs": [
                {"provider_id": provider_id, "name": name, "division": "Primera División"}
                for provider_id, name in (
                    ("a", "Club A"),
                    ("b", "Club B"),
                    ("c", "Club C"),
                )
            ],
            "players": [
                {
                    "provider_id": f"p{number}",
                    "club_provider_id": "a",
                    "name": f"Jugador {number}",
                    "position": "DEF",
                    "age": 23,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 17)
            ],
            "fixtures": [
                {
                    "division": "Primera División",
                    "matchday": 1,
                    "played_on": "2026-02-01",
                    "home_provider_id": "a",
                    "away_provider_id": "b",
                }
            ],
        }
        source = Path(self.temp_dir.name) / "tournament.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (3, 16, 1))
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.executemany(
                "INSERT INTO signings (player_id, fee) VALUES (?, 1)",
                [(player_id,) for player_id in range(1, 17)],
            )
            db.commit()

        page = self.client.get("/calendario")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Jugar el torneo", page.data)
        self.assertIn(b"JUGAR PARTIDO", page.data)
        self.assertIn(b"class=\"tournament-dashboard-grid\"", page.data)
        self.assertIn(b"class=\"tournament-standings tournament-standings-side\"", page.data)
        self.assertIn(b"class=\"match-dashboard", page.data)
        self.assertIn(b"Deportivo Sur", page.data)
        self.assertIn(b"Club A", page.data)
        self.assertIn(b"4-4-2", page.data)
        self.assertIn(b"Jugador 1", page.data)
        self.assertIn(b"Partidos de la fecha 1", page.data)
        self.assertNotIn(b"Partidos de la fecha 2", page.data)
        self.assertEqual(page.data.count(b'class="fixture-row'), 2)
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM tournament_matches").fetchone()[0],
                6,
            )
            self.assertEqual(
                db.execute(
                    """SELECT COUNT(*) FROM tournament_matches
                       WHERE home_club_id IS NULL OR away_club_id IS NULL"""
                ).fetchone()[0],
                3,
            )

        cannot_skip = self.client.post("/torneo/avanzar", follow_redirects=True)
        self.assertIn(b"Disput\xc3\xa1 todos los partidos", cannot_skip.data)
        self.assertIn(b"Partidos de la fecha 1", cannot_skip.data)
        for round_number in range(1, 4):
            played = self.client.post("/torneo/jugar", follow_redirects=True)
            self.assertEqual(played.status_code, 200)
            self.assertIn(f"Fecha {round_number} disputada".encode(), played.data)
            self.assertIn(
                f"Resultados de la fecha {round_number}".encode(),
                played.data,
            )
            if round_number == 1:
                self.assertIn("SIMULACIÓN EN VIVO".encode(), played.data)
                self.assertIn(b"RELATO DEL PARTIDO", played.data)
                self.assertIn(b"match-dashboard-played", played.data)
                with game.app.app_context():
                    db = game.get_db()
                    player_match = db.execute(
                        """SELECT home_score, away_score, match_events
                           FROM tournament_matches
                           WHERE round_number = 1
                             AND (home_club_id IS NULL OR away_club_id IS NULL)"""
                    ).fetchone()
                    events = json.loads(player_match["match_events"])
                    goal_events = [
                        event for event in events if event["type"] == "goal"
                    ]
                    self.assertEqual(
                        len(goal_events),
                        player_match["home_score"] + player_match["away_score"],
                    )
                    self.assertTrue(
                        all(
                            event["assist"]
                            and event["assist_player_id"] != event["player_id"]
                            for event in goal_events
                        )
                    )
                    self.assertEqual(
                        sum(
                            event["type"] == "goal" and event["side"] == "home"
                            for event in events
                        ),
                        player_match["home_score"],
                    )
                    self.assertEqual(
                        sum(
                            event["type"] == "goal" and event["side"] == "away"
                            for event in events
                        ),
                        player_match["away_score"],
                    )
                    self.assertTrue(
                        any(event["type"] in ("yellow", "red") for event in events)
                    )
                    self.assertTrue(all(event["player"] for event in events))
                    self.assertGreater(
                        db.execute(
                            """SELECT COUNT(*) FROM player_match_stats
                               WHERE season_number = 1 AND match_id = (
                                   SELECT id FROM tournament_matches
                                   WHERE round_number = 1
                                     AND (home_club_id IS NULL OR away_club_id IS NULL)
                               )"""
                        ).fetchone()[0],
                        0,
                    )
                    player_stats = db.execute(
                        """SELECT SUM(goals) AS goals, SUM(assists) AS assists
                           FROM player_match_stats
                           WHERE season_number = 1 AND match_id = (
                               SELECT id FROM tournament_matches
                               WHERE round_number = 1
                                 AND (home_club_id IS NULL OR away_club_id IS NULL)
                           )"""
                    ).fetchone()
                    self.assertEqual(
                        player_stats["goals"],
                        player_match["home_score"] + player_match["away_score"],
                    )
                    self.assertEqual(player_stats["assists"], len(goal_events))
            self.assertNotIn(
                f"Partidos de la fecha {round_number + 1}".encode(),
                played.data,
            )
            repeated = self.client.post("/torneo/jugar", follow_redirects=True)
            self.assertIn(
                f"La fecha {round_number} ya fue disputada".encode(),
                repeated.data,
            )
            if round_number == 1:
                self.assertIn(b"RESULTADO FINAL", repeated.data)
                self.assertIn(b"RELATO DEL PARTIDO", repeated.data)
                self.assertNotIn("SIMULACIÓN EN VIVO".encode(), repeated.data)
            with game.app.app_context():
                db = game.get_db()
                copa_progress = db.execute(
                    """SELECT season_number, current_round, is_complete
                       FROM copa_argentina_progress WHERE id = 1"""
                ).fetchone()
                league_rounds = db.execute(
                    "SELECT MAX(round_number) FROM tournament_matches"
                ).fetchone()[0]
                copa_due = (
                    copa_progress is not None
                    and not copa_progress["is_complete"]
                    and game.copa_argentina_league_matchday(
                        db,
                        copa_progress["season_number"],
                        copa_progress["current_round"],
                        league_rounds,
                    )
                    == round_number
                )
            if copa_due:
                copa_simulated = self.client.post(
                    "/copa-argentina/simular-ronda",
                    data={"return_to": "fixtures"},
                    follow_redirects=True,
                )
                self.assertEqual(copa_simulated.status_code, 200)
            if round_number < 3:
                if round_number % 2 == 0:
                    self.assertIn("DECISIÓN DE TEMPORADA".encode(), played.data)
                    with game.app.app_context():
                        decision = game.get_db().execute(
                            """SELECT event_key FROM season_decisions
                               WHERE season_number = 1 AND after_round = ?""",
                            (round_number,),
                        ).fetchone()
                    decision_key = next(
                        iter(game.SEASON_DECISIONS[decision["event_key"]]["options"])
                    )
                    chosen = self.client.post(
                        "/torneo/decision",
                        data={"choice": decision_key},
                        follow_redirects=True,
                    )
                    self.assertEqual(chosen.status_code, 200)
                advanced = self.client.post(
                    "/torneo/avanzar", follow_redirects=True
                )
                self.assertIn(
                    f"Avanzaste a la fecha {round_number + 1}".encode(),
                    advanced.data,
                )
                self.assertIn(
                    b"JUGAR PARTIDO",
                    advanced.data,
                )
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM tournament_matches WHERE home_score IS NOT NULL"
                ).fetchone()[0],
                6,
            )
            custom_team = db.execute(
                """SELECT played, points FROM (
                       SELECT COUNT(*) AS played,
                              SUM(CASE WHEN home_club_id IS NULL AND home_score > away_score
                                         OR away_club_id IS NULL AND away_score > home_score
                                       THEN 3
                                       WHEN home_club_id IS NULL AND home_score = away_score
                                         OR away_club_id IS NULL AND away_score = home_score
                                       THEN 1 ELSE 0 END) AS points
                       FROM tournament_matches
                       WHERE (home_club_id IS NULL OR away_club_id IS NULL)
                         AND home_score IS NOT NULL
                   )"""
            ).fetchone()
            self.assertEqual(custom_team["played"], 3)
            self.assertGreaterEqual(custom_team["points"], 0)
        final_page = self.client.get("/calendario")
        self.assertIn(b"TORNEO FINALIZADO", final_page.data)
        self.assertIn(b"Tabla de posiciones", final_page.data)
        self.assertIn(b"standing-champion", final_page.data)
        self.assertIn(b"standing-libertadores", final_page.data)
        self.assertIn(b"standing-sudamericana", final_page.data)
        self.client.post("/torneo/jugar")
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute(
                    "SELECT COUNT(*) FROM tournament_matches WHERE home_score IS NOT NULL"
                ).fetchone()[0],
                6,
            )

    def test_simulate_full_season_pauses_for_decisions_every_two_rounds(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "automatic season simulation",
            "clubs": [
                {"provider_id": provider_id, "name": name, "division": "Primera División"}
                for provider_id, name in (
                    ("auto-a", "Auto Club A"),
                    ("auto-b", "Auto Club B"),
                    ("auto-c", "Auto Club C"),
                )
            ],
            "players": [
                {
                    "provider_id": f"auto-player-{number}",
                    "club_provider_id": "auto-a",
                    "name": f"Auto Player {number}",
                    "position": "MED",
                    "age": 23,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 17)
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "auto-season.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        import_dataset(source, game.DATABASE)
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.executemany(
                "INSERT INTO signings (player_id, fee) VALUES (?, 1)",
                [(player_id,) for player_id in range(1, 17)],
            )
            db.commit()

        paused = self.client.post(
            "/torneo/simular-temporada", follow_redirects=True
        )
        self.assertEqual(paused.status_code, 200)
        self.assertIn("DECISIÓN DE TEMPORADA".encode(), paused.data)
        with game.app.app_context():
            db = game.get_db()
            progress = db.execute(
                """SELECT current_round, auto_simulation FROM tournament_progress
                   WHERE id = 1"""
            ).fetchone()
            copa_progress = db.execute(
                """SELECT current_round, is_complete, champion_team
                   FROM copa_argentina_progress WHERE id = 1"""
            ).fetchone()
            total_played_rounds = db.execute(
                """SELECT COUNT(DISTINCT round_number) FROM tournament_matches
                   WHERE home_score IS NOT NULL AND away_score IS NOT NULL"""
            ).fetchone()[0]
            decision = db.execute(
                """SELECT event_key FROM season_decisions
                   WHERE season_number = 1 AND after_round = 2"""
            ).fetchone()
        self.assertEqual(progress["current_round"], 2)
        self.assertEqual(progress["auto_simulation"], 1)
        self.assertEqual(total_played_rounds, 2)
        self.assertIsNotNone(decision)
        self.assertTrue(copa_progress["is_complete"])
        self.assertTrue(copa_progress["champion_team"])

        decision_key = next(
            iter(game.SEASON_DECISIONS[decision["event_key"]]["options"])
        )
        complete = self.client.post(
            "/torneo/decision",
            data={"choice": decision_key},
            follow_redirects=True,
        )
        self.assertEqual(complete.status_code, 200)
        self.assertIn(b"Se complet", complete.data)
        with game.app.app_context():
            db = game.get_db()
            progress = db.execute(
                """SELECT current_round, auto_simulation FROM tournament_progress
                   WHERE id = 1"""
            ).fetchone()
            self.assertEqual(progress["current_round"], 3)
            self.assertEqual(
                db.execute(
                    """SELECT COUNT(*) FROM tournament_matches
                       WHERE home_score IS NULL OR away_score IS NULL"""
                ).fetchone()[0],
                0,
            )
            self.assertEqual(progress["auto_simulation"], 0)
            copa_progress = db.execute(
                "SELECT is_complete FROM copa_argentina_progress WHERE id = 1"
            ).fetchone()
            self.assertTrue(copa_progress["is_complete"])

    def test_playoff_penalties_can_be_simulated_and_revealed(self):
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            opponent_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Penalty Opponent', 'Primera Nacional') RETURNING id"""
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO promotion_playoff_progress (id, current_stage)
                   VALUES (1, 'quarterfinal')"""
            )
            db.execute(
                """INSERT INTO promotion_playoff_matches
                   (stage, match_number, home_seed, away_seed, home_team, away_team,
                    home_club_id, away_club_id, home_overall, away_overall,
                    home_score, away_score)
                   VALUES ('quarterfinal', 1, 2, 3, 'Deportivo Sur',
                           'Penalty Opponent', NULL, ?, 60, 60, 0, 0)""",
                (opponent_id,),
            )
            db.commit()

        page = self.client.get("/calendario")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"SIMULAR PENALES", page.data)
        self.assertIn(b"ESPERANDO DEFINICI\xc3\x93N", page.data)
        self.assertIn(b"Definici\xc3\xb3n en curso", page.data)
        self.assertNotIn(b"Penales 0 \xe2\x80\x93 0", page.data)
        simulated = self.client.post(
            "/torneo/playoff/penal",
            data={"action": "simulate"},
            follow_redirects=True,
        )
        self.assertEqual(simulated.status_code, 200)
        self.assertEqual(simulated.request.args.get("penalty_live"), "1")
        self.assertIn(b"SIMULACI\xc3\x93N DE LA TANDA", simulated.data)
        self.assertIn(b'data-simulate="true"', simulated.data)
        self.assertIn(b'data-direction="', simulated.data)
        with game.app.app_context():
            match = game.get_db().execute(
                """SELECT winner_team, home_penalties, away_penalties, shootout_state
                   FROM promotion_playoff_matches
                   WHERE stage = 'quarterfinal' AND match_number = 1"""
            ).fetchone()
            shootout_state = json.loads(match["shootout_state"])
        self.assertTrue(shootout_state["complete"])
        self.assertGreater(len(shootout_state["kicks"]), 0)
        self.assertIn(match["winner_team"], ("Deportivo Sur", "Penalty Opponent"))

    def test_season_decisions_respect_their_context(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            clubs = {}
            for name in ("Club A", "Club B", "Club C", "Club D"):
                cursor = db.execute(
                    """INSERT INTO clubs (name, division)
                       VALUES (?, 'Primera División')""",
                    (name,),
                )
                clubs[name] = cursor.lastrowid
            club_names = {club_id: name for name, club_id in clubs.items()}

            def add_match(round_number, home, away, score=None):
                db.execute(
                    """INSERT INTO tournament_matches
                       (round_number, played_on, home_team, away_team,
                        home_club_id, away_club_id, home_overall, away_overall,
                        home_score, away_score)
                       VALUES (?, '2026-01-01', ?, ?, ?, ?, 60, 60, ?, ?)""",
                    (
                        round_number,
                        "Deportivo Sur" if home is None else club_names[home],
                        "Deportivo Sur" if away is None else club_names[away],
                        home,
                        away,
                        *(score if score else (None, None)),
                    ),
                )

            add_match(1, None, clubs["Club A"], (0, 1))
            add_match(1, clubs["Club B"], clubs["Club C"], (0, 1))
            add_match(2, clubs["Club B"], None, (2, 0))
            add_match(2, clubs["Club A"], clubs["Club D"], (1, 1))
            add_match(3, None, clubs["Club C"])
            add_match(3, clubs["Club B"], clubs["Club D"])
            add_match(4, clubs["Club B"], clubs["Club A"])
            add_match(5, clubs["Club C"], clubs["Club D"])
            add_match(6, clubs["Club A"], clubs["Club D"])
            db.commit()

            career = game.get_career()
            upcoming = db.execute(
                """SELECT home_team, away_team, home_club_id, away_club_id
                   FROM tournament_matches WHERE round_number = 3
                     AND (home_club_id IS NULL OR away_club_id IS NULL)"""
            ).fetchone()
            self.assertEqual(upcoming["away_team"], "Club C")
            self.assertIsNone(upcoming["home_club_id"])
            available = game.available_season_decisions(db, career, 2, 6)
            self.assertIn("fatigue", available)
            self.assertIn("rivalry", available)
            self.assertIn("referee", available)
            self.assertIn("rain", available)
            self.assertIn("supporters", available)
            self.assertIn("stadium", available)
            self.assertNotIn("transfer_rumor", available)

            player_id = db.execute(
                """INSERT INTO players (name, position, overall)
                   VALUES ('Mediocampista titular', 'MED', 75)"""
            ).lastrowid
            db.execute(
                "INSERT INTO signings (player_id, fee) VALUES (?, 1)",
                (player_id,),
            )
            after_midseason = game.available_season_decisions(db, career, 3, 6)
            self.assertIn("transfer_rumor", after_midseason)
            self.assertTrue(
                {
                    "training",
                    "player_bonus",
                    "travel",
                    "media",
                    "academy",
                    "facilities",
                }.issubset(after_midseason)
            )
            db.executemany(
                """INSERT INTO season_decisions
                   (season_number, after_round, event_key, choice_key)
                   VALUES (1, ?, ?, 'previous_choice')""",
                [(-4, "fatigue"), (-2, "stadium"), (0, "training")],
            )
            with patch.object(
                game.random, "choice", side_effect=lambda candidates: candidates[0]
            ):
                pending = game.get_pending_season_decision(db, 1, 2, career)
            self.assertIsNotNone(pending)
            self.assertNotIn(
                pending["event_key"], {"fatigue", "stadium", "training"}
            )

    def test_every_season_decision_option_applies_and_records_its_outcome(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            after_round = 2
            for event_key, event in game.SEASON_DECISIONS.items():
                for choice_key, option in event["options"].items():
                    db.execute(
                        """INSERT INTO season_decisions
                           (season_number, after_round, event_key)
                           VALUES (1, ?, ?)""",
                        (after_round, event_key),
                    )
                    outcome = game.apply_season_decision(
                        db,
                        game.get_career(),
                        1,
                        after_round,
                        choice_key,
                    )
                    self.assertTrue(outcome)
                    self.assertEqual(
                        outcome,
                        option.get("effects", {}).get("outcome", outcome),
                    )
                    recorded = db.execute(
                        """SELECT choice_key, outcome FROM season_decisions
                           WHERE season_number = 1 AND after_round = ?""",
                        (after_round,),
                    ).fetchone()
                    self.assertEqual(recorded["choice_key"], choice_key)
                    self.assertEqual(recorded["outcome"], outcome)
                    after_round += 2

    def test_national_champion_receives_trophy_and_direct_promotion(self):
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            career = game.get_career()
            standings = [
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 1,
                    "played": 20,
                },
                {
                    "name": "Subcampeón",
                    "is_career": False,
                    "position": 2,
                    "played": 20,
                },
            ]
            game.setup_league_outcome(game.get_db(), career, standings)
            awards = game.get_db().execute(
                "SELECT award_type, team_name FROM tournament_awards ORDER BY award_type"
            ).fetchall()
            playoff_count = game.get_db().execute(
                "SELECT COUNT(*) FROM promotion_playoff_matches"
            ).fetchone()[0]
        self.assertEqual(
            [(award["award_type"], award["team_name"]) for award in awards],
            [
                ("champion_1", "Deportivo Sur"),
                ("league_prize_1", "Deportivo Sur"),
                ("promotion_1", "Deportivo Sur"),
            ],
        )
        with game.app.app_context():
            self.assertEqual(game.get_career()["budget"], 7_000_000)
            game.setup_league_outcome(game.get_db(), game.get_career(), standings)
            self.assertEqual(game.get_career()["budget"], 7_000_000)
        self.assertEqual(playoff_count, 0)

    def test_national_league_prize_decreases_by_place_and_is_paid_once(self):
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Campeón', 'Primera Nacional')"""
            )
            career = game.get_career()
            standings = [
                {"name": "Campeón", "is_career": False, "position": 1, "played": 10},
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 2,
                    "played": 10,
                },
                {"name": "Último", "is_career": False, "position": 3, "played": 10},
            ]
            game.setup_league_outcome(db, career, standings)
            self.assertEqual(game.get_career()["budget"], 3_500_000)
            game.setup_league_outcome(db, game.get_career(), standings)
            self.assertEqual(game.get_career()["budget"], 3_500_000)
        self.assertEqual(game.first_national_prize(1, 3), 7_000_000)
        self.assertEqual(game.first_national_prize(2, 3), 3_500_000)
        self.assertEqual(game.first_national_prize(3, 3), 0)
        self.assertEqual(game.first_national_prize(2, 1), 0)

    def test_first_division_prize_decreases_by_place_and_is_paid_once(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET division = 'Primera División' WHERE id = 1")
            career = game.get_career()
            standings = [
                {"name": "Campeón", "is_career": False, "position": 1, "played": 10},
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 2,
                    "played": 10,
                },
                *[
                    {
                        "name": f"Club {position}",
                        "is_career": False,
                        "position": position,
                        "played": 10,
                    }
                    for position in range(3, 10)
                ],
            ]
            game.setup_league_outcome(db, career, standings)
            self.assertEqual(
                game.get_career()["budget"],
                game.first_division_prize(2),
            )
            game.setup_league_outcome(db, game.get_career(), standings)
            self.assertEqual(
                game.get_career()["budget"],
                game.first_division_prize(2),
            )
        self.assertEqual(game.first_division_prize(1), 20_000_000)
        self.assertGreater(game.first_division_prize(28), 0)
        self.assertEqual(game.first_division_prize(29), 0)
        self.assertEqual(game.first_division_prize(30), 0)

    def test_player_overall_develops_from_season_performance_once(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                """INSERT INTO players (name, position, overall)
                   VALUES (?, 'DEL', ?)""",
                [
                    ("Jugador destacado", 70),
                    ("Jugador regular", 70),
                    ("Jugador con bajo rendimiento", 70),
                ],
            )
            player_ids = {
                row["name"]: row["id"]
                for row in db.execute(
                    """SELECT id, name FROM players
                       WHERE name IN (?, ?, ?)""",
                    (
                        "Jugador destacado",
                        "Jugador regular",
                        "Jugador con bajo rendimiento",
                    ),
                ).fetchall()
            }
            for name in player_ids:
                player_id = player_ids[name]
                goals = 15 if name == "Jugador destacado" else (
                    1 if name == "Jugador regular" else 0
                )
                yellow_cards = 9 if name == "Jugador con bajo rendimiento" else 0
                for match_id in range(10):
                    db.execute(
                        """INSERT INTO player_match_stats
                           (season_number, match_id, player_id, goals, yellow_cards)
                           VALUES (1, ?, ?, ?, ?)""",
                        (
                            match_id,
                            player_id,
                            goals if match_id == 0 else 0,
                            yellow_cards if match_id == 0 else 0,
                        ),
                    )

            changed = game.apply_season_player_development(db, 1)
            self.assertEqual(changed, 3)
            ratings = {
                row["name"]: row["overall"]
                for row in db.execute(
                    """SELECT name, overall FROM players
                       WHERE id IN (?, ?, ?)""",
                    tuple(player_ids.values()),
                ).fetchall()
            }
            self.assertEqual(ratings["Jugador destacado"], 72)
            self.assertEqual(ratings["Jugador regular"], 71)
            self.assertEqual(ratings["Jugador con bajo rendimiento"], 69)
            self.assertEqual(game.apply_season_player_development(db, 1), 0)

    def test_new_career_restores_players_to_their_base_overall(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            player_id = db.execute(
                """INSERT INTO players (name, position, overall, base_overall)
                   VALUES ('Jugador con OVR alterado', 'MED', 77, 65)"""
            ).lastrowid
            db.commit()

        self.client.post("/reiniciar", follow_redirects=True)
        self.create_career()

        with game.app.app_context():
            player = game.get_db().execute(
                "SELECT overall, base_overall FROM players WHERE id = ?",
                (player_id,),
            ).fetchone()
            self.assertEqual(player["overall"], 65)
            self.assertEqual(player["base_overall"], 65)

    def test_ferro_shirt_palette_uses_crest_colors(self):
        logo = "/static/crests/ferro.svg"

        self.assertEqual(
            game.infer_shirt_colors_from_logo(logo),
            ("#1b5e20", "#ffffff"),
        )
        self.assertEqual(
            game.team_shirt_style("Ferro Carril Oeste", logo=logo),
            {
                "shirt_primary": "#1b5e20",
                "shirt_secondary": "#ffffff",
                "shirt_pattern": "solid",
            },
        )

    def test_league_leaders_are_limited_to_current_season_division_and_competition(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            club_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Club de Primera', 'Primera División')"""
            ).lastrowid
            national_club_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Club Nacional', 'Primera Nacional')"""
            ).lastrowid
            scorer_id = db.execute(
                """INSERT INTO players (club_id, name, position)
                   VALUES (?, 'Goleador', 'DEL')""",
                (club_id,),
            ).lastrowid
            assistant_id = db.execute(
                """INSERT INTO players (club_id, name, position)
                   VALUES (?, 'Asistente', 'MED')""",
                (club_id,),
            ).lastrowid
            other_division_id = db.execute(
                """INSERT INTO players (club_id, name, position)
                   VALUES (?, 'Goleador Nacional', 'DEL')""",
                (national_club_id,),
            ).lastrowid
            db.executemany(
                """INSERT INTO player_match_stats
                   (season_number, competition, match_id, player_id, goals, assists)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (1, "league", 1, scorer_id, 2, 0),
                    (1, "league", 2, scorer_id, 1, 0),
                    (1, "league", 1, assistant_id, 0, 2),
                    (1, "league", 1, other_division_id, 8, 0),
                    (1, "copa_argentina", 3, scorer_id, 7, 0),
                    (2, "league", 4, scorer_id, 6, 0),
                ],
            )

            scorers, assisters = game.get_league_leaders(
                db, game.get_career(), season_number=1
            )

            self.assertEqual([(row["name"], row["goals"]) for row in scorers], [("Goleador", 3)])
            self.assertEqual(
                [(row["name"], row["assists"]) for row in assisters],
                [("Asistente", 2)],
            )

    def test_season_individual_awards_rank_players_and_goalkeepers(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            rival_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Rival de Primera', 'Primera División')"""
            ).lastrowid
            match_id = db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'Deportivo Sur', 'Rival de Primera',
                           NULL, ?, 70, 70, 2, 1)""",
                (rival_id,),
            ).lastrowid
            player_rows = [
                (None, "Figura", "DEL", 25, 70, "Deportivo Sur", 2, 1),
                (None, "Joven", "MED", 20, 64, "Deportivo Sur", 0, 2),
                (None, "Arquero titular", "ARQ", 30, 80, "Deportivo Sur", 0, 0),
                (None, "Arquero joven", "ARQ", 19, 70, "Deportivo Sur", 0, 0),
                (rival_id, "Arquero rival", "ARQ", 28, 82, "Rival de Primera", 0, 0),
            ]
            for club_id, name, position, age, overall, team_name, goals, assists in player_rows:
                player_id = db.execute(
                    """INSERT INTO players (club_id, name, position, age, overall)
                       VALUES (?, ?, ?, ?, ?)""",
                    (club_id, name, position, age, overall),
                ).lastrowid
                db.execute(
                    """INSERT INTO player_match_stats
                       (season_number, competition, match_id, player_id, goals,
                        assists, club_id, team_name, division)
                       VALUES (1, 'league', ?, ?, ?, ?, ?, ?, 'Primera División')""",
                    (match_id, player_id, goals, assists, club_id, team_name),
                )

            awards = game.get_season_individual_awards(
                db, game.get_career(), season_number=1
            )

            self.assertEqual(
                [(award["title"], award["name"]) for award in awards],
                [
                    ("Mejor jugador del año", "Figura"),
                    ("Mejor arquero", "Arquero titular"),
                    ("Mejor jugador joven · Sub-21", "Joven"),
                    ("Mejor arquero joven · Sub-21", "Arquero joven"),
                ],
            )

    def test_completed_league_shows_individual_awards_beside_leaderboards(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            rival_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Rival de Primera', 'Primera División')"""
            ).lastrowid
            match_id = db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'Deportivo Sur', 'Rival de Primera',
                           NULL, ?, 70, 70, 2, 0)""",
                (rival_id,),
            ).lastrowid
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            for name, position, age, goals, assists in (
                ("Goleador", "DEL", 25, 2, 0),
                ("Arquero", "ARQ", 30, 0, 0),
                ("Joven", "MED", 20, 0, 2),
            ):
                player_id = db.execute(
                    """INSERT INTO players (name, position, age, overall)
                       VALUES (?, ?, ?, 70)""",
                    (name, position, age),
                ).lastrowid
                db.execute(
                    """INSERT INTO player_match_stats
                       (season_number, competition, match_id, player_id, goals,
                        assists, team_name, division)
                       VALUES (1, 'league', ?, ?, ?, ?, 'Deportivo Sur',
                               'Primera División')""",
                    (match_id, player_id, goals, assists),
                )
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            page = self.client.get("/calendario")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b"league-awards-table", page.data)
        self.assertIn("Mejor jugador del año".encode(), page.data)
        self.assertIn("Mejor arquero joven".encode(), page.data)

    def test_first_division_champion_receives_twenty_million(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET division = 'Primera División' WHERE id = 1")
            career = game.get_career()
            standings = [
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 1,
                    "played": 10,
                },
                *[
                    {
                        "name": f"Club {position}",
                        "is_career": False,
                        "position": position,
                        "played": 10,
                    }
                    for position in range(2, 10)
                ],
            ]
            game.setup_league_outcome(db, career, standings)
            self.assertEqual(game.get_career()["budget"], 20_000_000)

    def test_first_division_relegation_and_national_promotions_apply_next_season(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, 'Primera División')",
                [(f"First Division Club {number}",) for number in range(1, 29)],
            )
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, 'Primera Nacional')",
                [("National Champion",), ("Playoff Promoted",)],
            )
            db.execute(
                "UPDATE career SET division = 'Primera División', phase = 'season' WHERE id = 1"
            )
            career = game.get_career()
            standings = [
                {
                    "name": f"First Division Club {number}",
                    "is_career": False,
                    "position": number,
                    "played": 20,
                }
                for number in range(1, 28)
            ]
            standings.extend(
                [
                    {
                        "name": career["club_name"],
                        "is_career": True,
                        "position": 28,
                        "played": 20,
                    },
                    {
                        "name": "First Division Club 28",
                        "is_career": False,
                        "position": 29,
                        "played": 20,
                    },
                ]
            )
            game.setup_league_outcome(db, career, standings)
            relegation_awards = db.execute(
                """SELECT team_name FROM tournament_awards
                   WHERE award_type LIKE 'relegation_1%' ORDER BY team_name"""
            ).fetchall()
            self.assertEqual(
                [row["team_name"] for row in relegation_awards],
                ["Deportivo Sur", "First Division Club 28"],
            )
            first_division_club_id = db.execute(
                "SELECT id FROM clubs WHERE name = 'First Division Club 1'"
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'League Club', 'Deportivo Sur',
                           ?, NULL, 60, 60, 0, 0)""",
                (first_division_club_id,),
            )
            db.commit()
            game.start_next_season(db)
            updated_divisions = {
                row["name"]: row["division"]
                for row in db.execute(
                    """SELECT name, division FROM clubs
                       WHERE name IN ('First Division Club 28',
                                      'National Champion', 'Playoff Promoted')"""
                ).fetchall()
            }
            self.assertEqual(game.get_career()["division"], "Primera Nacional")
        self.assertEqual(
            updated_divisions,
            {
                "First Division Club 28": "Primera Nacional",
                "National Champion": "Primera División",
                "Playoff Promoted": "Primera División",
            },
        )

    def test_first_division_schedule_has_thirty_teams_and_records_bottom_two_relegations(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                """INSERT INTO clubs (name, division)
                   VALUES (?, 'Primera División')""",
                [(f"First Club {number:02}",) for number in range(1, 32)],
            )
            db.executemany(
                """INSERT INTO clubs (name, division)
                   VALUES (?, 'Primera Nacional')""",
                [(f"National Club {number:02}",) for number in range(1, 5)],
            )
            db.execute(
                "UPDATE career SET division = 'Primera División', phase = 'season' WHERE id = 1"
            )
            career = game.get_career()
            game.ensure_tournament_schedule(db, career)

            standings = game.calculate_tournament_standings(db, career)
            self.assertEqual(len(standings), game.FIRST_DIVISION_TEAM_COUNT)
            self.assertEqual(
                db.execute(
                    """SELECT COUNT(*) FROM clubs
                       WHERE division = 'Primera División'"""
                ).fetchone()[0],
                game.FIRST_DIVISION_TEAM_COUNT - 1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT MAX(round_number) FROM tournament_matches"
                ).fetchone()[0],
                game.FIRST_DIVISION_TEAM_COUNT - 1,
            )

            completed_standings = [
                {**team, "position": position, "played": 10}
                for position, team in enumerate(standings, start=1)
            ]
            game.setup_league_outcome(db, career, completed_standings)
            relegated = [
                movement["team_name"]
                for movement in game.get_season_movements(db, 1)
                if movement["description"].startswith("Descenso")
            ]
            self.assertEqual(
                set(relegated),
                {
                    completed_standings[-2]["name"],
                    completed_standings[-1]["name"],
                },
            )

    def test_national_season_records_and_applies_ai_first_division_relegations(self):
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO clubs (name, division) VALUES (?, ?)",
                [
                    ("AI First Club A", "Primera División"),
                    ("AI First Club B", "Primera División"),
                    ("National Runner-up", "Primera Nacional"),
                    ("National Club", "Primera Nacional"),
                ],
            )
            runner_up_id = db.execute(
                "SELECT id FROM clubs WHERE name = 'National Runner-up'"
            ).fetchone()["id"]
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            career = game.get_career()
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', ?, ?, NULL, ?, 60, 60, 0, 0)""",
                (career["club_name"], "National Runner-up", runner_up_id),
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            standings = [
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 1,
                    "played": 1,
                },
                {
                    "name": "National Runner-up",
                    "is_career": False,
                    "position": 2,
                    "played": 1,
                },
            ]
            game.setup_league_outcome(db, career, standings)
            game.setup_league_outcome(db, career, standings)

            movements = game.get_season_movements(db, 1)
            relegated = {
                movement["team_name"]
                for movement in movements
                if movement["description"].startswith("Descenso")
            }
            self.assertEqual(len(relegated), 2)
            for name in relegated:
                self.assertIn(name, {
                    row["name"]
                    for row in db.execute(
                        "SELECT name FROM clubs WHERE division = 'Primera División'"
                    ).fetchall()
                })
            with patch("live_football_api.ensure_football_data_loaded"):
                page = self.client.get("/calendario")
            self.assertEqual(page.status_code, 200)
            for name in relegated:
                self.assertIn(name.encode(), page.data)

            game.start_next_season(db)
            movements = game.get_season_movements(db, 1)
            promoted_club = next(
                movement["team_name"]
                for movement in movements
                if movement["description"].startswith("Ascenso")
                and movement["team_name"] != career["club_name"]
            )
            updated_divisions = {
                row["name"]: row["division"]
                for row in db.execute(
                    "SELECT name, division FROM clubs WHERE name IN (?, ?, ?)",
                    (*relegated, promoted_club),
                ).fetchall()
            }
            for name in relegated:
                self.assertEqual(updated_divisions[name], "Primera Nacional")
            self.assertEqual(updated_divisions[promoted_club], "Primera División")
            self.assertEqual(game.get_career()["division"], "Primera División")

    def test_final_first_division_round_displays_current_relegations(self):
        self.create_career(division="Primera División")
        with game.app.app_context():
            db = game.get_db()
            club_a = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Club A', 'Primera División') RETURNING id"""
            ).fetchone()["id"]
            club_b = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Club B', 'Primera División') RETURNING id"""
            ).fetchone()["id"]
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.executemany(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', ?, ?, ?, ?, 60, 60, ?, ?)""",
                [
                    ("Deportivo Sur", "Club A", None, club_a, 0, 2),
                    ("Club A", "Club B", club_a, club_b, 0, 0),
                    ("Club B", "Deportivo Sur", club_b, None, 1, 0),
                ],
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            db.commit()

        page = self.client.get("/calendario")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Ascensos y descensos entre ligas", page.data)
        self.assertIn(b"TEMPORADA 1", page.data)
        self.assertIn(b"Club B", page.data)
        self.assertIn(b"Deportivo Sur", page.data)
        with game.app.app_context():
            movements = game.get_season_movements(game.get_db(), 1)
            relegated = {
                movement["team_name"]
                for movement in movements
                if movement["description"].startswith("Descenso")
            }
        self.assertEqual(relegated, {"Club B", "Deportivo Sur"})

    def test_completed_first_division_season_moves_two_clubs_each_way(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            first_division_ids = {}
            for name in ("Primera Club Descenso A", "Primera Club Descenso B"):
                first_division_ids[name] = db.execute(
                    """INSERT INTO clubs (name, division)
                       VALUES (?, 'Primera División') RETURNING id""",
                    (name,),
                ).fetchone()["id"]
            for name in (
                "Nacional Promovido A",
                "Nacional Promovido B",
                "Nacional Z Club C",
            ):
                db.execute(
                    """INSERT INTO clubs (name, division)
                       VALUES (?, 'Primera Nacional')""",
                    (name,),
                )
            db.execute(
                "UPDATE career SET division = 'Primera División', phase = 'season' WHERE id = 1"
            )
            career = game.get_career()
            standings = [
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 1,
                    "played": 10,
                },
                {
                    "name": "Primera Club Descenso A",
                    "is_career": False,
                    "position": 2,
                    "played": 10,
                },
                {
                    "name": "Primera Club Descenso B",
                    "is_career": False,
                    "position": 3,
                    "played": 10,
                },
            ]
            game.setup_league_outcome(db, career, standings)
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', ?, ?, ?, NULL, 60, 60, 2, 0)""",
                (
                    career["club_name"],
                    "Primera Club Descenso A",
                    first_division_ids["Primera Club Descenso A"],
                ),
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            db.commit()
            movements = game.get_season_movements(db, 1)
            promoted = {
                row["team_name"]
                for row in movements
                if row["description"].startswith("Ascenso")
            }
            relegated = {
                row["team_name"]
                for row in movements
                if row["description"].startswith("Descenso")
            }
            self.assertEqual(
                promoted,
                {"Nacional Promovido A", "Nacional Promovido B"},
            )
            self.assertEqual(
                relegated,
                {"Primera Club Descenso A", "Primera Club Descenso B"},
            )

        page = self.client.get("/calendario")
        self.assertIn(b"Ascensos y descensos entre ligas", page.data)
        for team in promoted | relegated:
            self.assertIn(team.encode(), page.data)

        with game.app.app_context():
            db = game.get_db()
            game.start_next_season(db)
            divisions = {
                row["name"]: row["division"]
                for row in db.execute(
                    """SELECT name, division FROM clubs
                       WHERE name IN (?, ?, ?, ?)""",
                    tuple(sorted(promoted | relegated)),
                ).fetchall()
            }
        self.assertEqual(
            divisions,
            {
                "Nacional Promovido A": "Primera División",
                "Nacional Promovido B": "Primera División",
                "Primera Club Descenso A": "Primera Nacional",
                "Primera Club Descenso B": "Primera Nacional",
            },
        )

    def test_only_first_division_positions_28_and_29_are_marked_for_relegation(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                """INSERT INTO clubs (name, division)
                   VALUES (?, 'Primera División')""",
                [(f"Club {number:02}",) for number in range(1, 29)],
            )
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.commit()

        with patch("live_football_api.ensure_football_data_loaded"):
            response = self.client.get("/calendario")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Máximos goleadores", html)
        self.assertIn("Máximos asistentes", html)
        standings_table = re.search(
            r'<table class="standings-table">.*?</table>', html, re.DOTALL
        )
        self.assertIsNotNone(standings_table)
        self.assertIn('class="standing-crest"', standings_table.group())
        self.assertNotIn('class="team-shirt"', standings_table.group())
        for position, team_name, is_relegated in (
            (27, "Club 27", False),
            (28, "Club 28", True),
            (29, "Deportivo Sur", True),
        ):
            row = re.search(
                rf'<tr class="([^"]*)">\s*<td>{position}</td>\s*'
                rf'<td>.*?{re.escape(team_name)}.*?</td>.*?</tr>',
                html,
                re.DOTALL,
            )
            self.assertIsNotNone(row, f"Missing standings position {position}")
            self.assertEqual(
                "standing-relegation" in row.group(1),
                is_relegated,
                f"Unexpected relegation style for position {position}",
            )

    def test_previous_promotions_join_current_standings_without_being_relegated(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            db.execute(
                "UPDATE tournament_progress SET current_season = 2 WHERE id = 1"
            )
            incoming_ids = {}
            for name in ("Promoted Club A", "Promoted Club B"):
                incoming_ids[name] = db.execute(
                    """INSERT INTO clubs (name, division)
                       VALUES (?, 'Primera Nacional') RETURNING id""",
                    (name,),
                ).fetchone()["id"]
                db.execute(
                    """INSERT INTO tournament_awards
                       (award_type, team_name, description)
                       VALUES (?, ?, 'Ascenso directo a Primera División')""",
                    (f"promotion_1_club_{incoming_ids[name]}", name),
                )
            first_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Active Club A', 'Primera División') RETURNING id"""
            ).fetchone()["id"]
            second_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Active Club B', 'Primera División') RETURNING id"""
            ).fetchone()["id"]
            db.executemany(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (?, '2026-01-01', ?, ?, ?, ?, 60, 60, ?, ?)""",
                [
                    (1, "Deportivo Sur", "Active Club A", None, first_id, 1, 0),
                    (2, "Active Club A", "Active Club B", first_id, second_id, 0, 2),
                ],
            )
            career = game.get_career()
            standings = game.calculate_tournament_standings(db, career)
            self.assertEqual(len(standings), 5)
            self.assertEqual(
                [team["name"] for team in standings[-2:]],
                ["Promoted Club A", "Promoted Club B"],
            )
            self.assertTrue(all(team["played"] == 0 for team in standings[-2:]))

            game.setup_league_outcome(db, career, standings)
            relegated = {
                row["team_name"]
                for row in db.execute(
                    """SELECT team_name FROM tournament_awards
                       WHERE award_type LIKE 'relegation_2%'"""
                ).fetchall()
            }
            self.assertFalse(relegated & {"Promoted Club A", "Promoted Club B"})

    def test_missing_promotions_exclude_clubs_relegated_in_same_season(self):
        self.create_career()
        with game.app.app_context():
            db = game.get_db()
            clubs = {}
            for name in (
                "A National Club",
                "B National Club",
                "C National Club",
                "D National Club",
            ):
                clubs[name] = db.execute(
                    """INSERT INTO clubs (name, division)
                       VALUES (?, 'Primera Nacional') RETURNING id""",
                    (name,),
                ).fetchone()["id"]
            for name in ("C National Club", "D National Club"):
                db.execute(
                    """INSERT INTO tournament_awards
                       (award_type, team_name, description)
                       VALUES (?, ?, 'Descenso a Primera Nacional')""",
                    (f"relegation_1_club_{clubs[name]}", name),
                )
            db.execute(
                """INSERT INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES (?, ?, 'Ascenso directo a Primera División')""",
                ("promotion_1_club_{}".format(clubs["C National Club"]),
                 "C National Club"),
            )

            game.ensure_two_division_movements(db, 1)
            movements = game.get_season_movements(db, 1)
            promoted = {
                row["team_name"]
                for row in movements
                if row["description"].startswith("Ascenso")
            }
            relegated = {
                row["team_name"]
                for row in movements
                if row["description"].startswith("Descenso")
            }

        self.assertEqual(len(promoted), 2)
        self.assertEqual(len(relegated), 2)
        self.assertFalse(promoted & relegated)
        self.assertNotIn("C National Club", promoted)
        self.assertNotIn("D National Club", promoted)

    def test_data_sync_preserves_career_promotions_after_first_season(self):
        self.create_career()
        dataset = {
            "season": 2026,
            "source": "career division preservation",
            "clubs": [
                {
                    "provider_id": "promoted-club",
                    "name": "Promoted Club",
                    "division": "Primera Nacional",
                }
            ],
            "players": [],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "division-preservation.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        import_dataset(source, game.DATABASE)
        with game.app.app_context():
            db = game.get_db()
            club_id = db.execute(
                "SELECT id FROM clubs WHERE name = 'Promoted Club'"
            ).fetchone()["id"]
            db.execute("UPDATE clubs SET division = 'Primera División' WHERE id = ?", (club_id,))
            db.execute(
                "UPDATE tournament_progress SET current_season = 2 WHERE id = 1"
            )
            db.commit()

        import_dataset(source, game.DATABASE)
        with game.app.app_context():
            division = game.get_db().execute(
                "SELECT division FROM clubs WHERE id = ?", (club_id,)
            ).fetchone()["division"]
        self.assertEqual(division, "Primera División")

    def test_national_places_two_to_nine_play_promotion_quarterfinals_semis_and_final(self):
        self.create_career(division="Primera Nacional")
        other_teams = ["Campeón"] + [f"Club {number}" for number in range(3, 10)]
        dataset = {
            "season": 2026,
            "source": "promotion playoff test",
            "clubs": [
                {
                    "provider_id": f"team-{number}",
                    "name": name,
                    "division": "Primera Nacional",
                }
                for number, name in enumerate(other_teams, start=1)
            ],
            "players": [
                {
                    "provider_id": f"playoff-player-{number}",
                    "club_provider_id": "team-1",
                    "name": f"Jugador {number}",
                    "position": "DEF",
                    "age": 23,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 17)
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "promotion-playoff.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (8, 16, 0))
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            db.executemany(
                "INSERT INTO signings (player_id, fee) VALUES (?, 1)",
                [(player_id,) for player_id in range(1, 17)],
            )
            db.commit()
            career = game.get_career()
            standings = [
                {
                    "name": "Campeón",
                    "is_career": False,
                    "position": 1,
                    "played": 20,
                },
                {
                    "name": career["club_name"],
                    "is_career": True,
                    "position": 2,
                    "played": 20,
                },
                *[
                    {
                        "name": f"Club {position}",
                        "is_career": False,
                        "position": position,
                        "played": 20,
                    }
                    for position in range(3, 10)
                ],
            ]
            game.setup_league_outcome(db, career, standings)
            self.assertEqual(
                db.execute(
                    """SELECT COUNT(*) FROM promotion_playoff_matches
                       WHERE stage = 'quarterfinal'"""
                ).fetchone()[0],
                4,
            )
            champion_id = db.execute(
                "SELECT id FROM clubs WHERE name = 'Campeón'"
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', ?, 'Campeón', NULL, ?, 60, 60, 1, 0)""",
                (career["club_name"], champion_id),
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            db.commit()

        page = self.client.get("/calendario")
        self.assertIn(b"Playoff de promoci\xc3\xb3n", page.data)
        self.assertIn(b'id="promotion-playoff"', page.data)
        self.assertIn(b"cuartos de final", page.data)
        self.assertIn(b"JUGAR PARTIDO", page.data)
        cannot_skip = self.client.post(
            "/torneo/playoff/avanzar", follow_redirects=True
        )
        self.assertIn(b"Disput\xc3\xa1 todos los partidos", cannot_skip.data)

        for stage, next_stage in (
            ("quarterfinal", "semifinales"),
            ("semifinal", "la final"),
            ("final", None),
        ):
            with game.app.app_context():
                user_fixture = game.get_db().execute(
                    """SELECT match_number, home_club_id FROM promotion_playoff_matches
                       WHERE stage = ?
                         AND (home_club_id IS NULL OR away_club_id IS NULL)""",
                    (stage,),
                ).fetchone()
            if stage == "quarterfinal":
                goal_results = patch.object(
                    game, "simulate_goals", return_value=(1, 1)
                )
            else:
                scores_by_match = [(1, 0)] * 4
                scores_by_match[user_fixture["match_number"] - 1] = (
                    (2, 0) if user_fixture["home_club_id"] is None else (0, 2)
                )
                goal_results = patch.object(
                    game, "simulate_goals", side_effect=scores_by_match
                )
            with goal_results:
                played = self.client.post(
                    "/torneo/playoff/jugar", follow_redirects=True
                )
            self.assertEqual(played.status_code, 200)
            self.assertIn("#promotion-playoff", played.history[0].location)
            self.assertIn(b"RELATO DEL PLAYOFF", played.data)
            self.assertIn(b"SIMULACI\xc3\x93N EN VIVO", played.data)
            self.assertEqual(played.request.args.get("playoff_live"), "1")
            self.assertNotIn(b'class="playoff-matches"', played.data)
            self.assertNotIn(b'tournament-panel', played.data)
            self.assertNotIn(b"Clasifica:", played.data)
            self.assertIn(
                b"const matchRoot = isPlayoffMatch",
                played.data,
            )
            self.assertIn(
                b"panel.querySelectorAll('.match-event[data-minute]')",
                played.data,
            )
            with game.app.app_context():
                db = game.get_db()
                player_match = db.execute(
                    """SELECT id, home_score, away_score, home_penalties, winner_team,
                              home_club_id, away_club_id
                       FROM promotion_playoff_matches
                       WHERE stage = ?
                         AND (home_club_id IS NULL OR away_club_id IS NULL)""",
                    (stage,),
                ).fetchone()
                if stage == "quarterfinal":
                    self.assertEqual(player_match["home_score"], 1)
                    self.assertEqual(player_match["away_score"], 1)
                    self.assertIsNone(player_match["winner_team"])
                else:
                    self.assertNotEqual(
                        player_match["home_score"], player_match["away_score"]
                    )
                    self.assertEqual(player_match["winner_team"], "Deportivo Sur")
                    self.assertIsNone(player_match["home_penalties"])
                self.assertIn(
                    f'data-home-score="{player_match["home_score"]}"'.encode(),
                    played.data,
                )
                self.assertIn(
                    f'data-away-score="{player_match["away_score"]}"'.encode(),
                    played.data,
                )
            if stage == "quarterfinal":
                self.assertIn(b"DEFINICI", played.data)
                self.assertIn(b"EJECUTAR PENAL", played.data)
                self.assertIn(
                    b"Vos defin\xc3\xads los remates de tu equipo", played.data
                )
                self.assertIn(b"class=\"penalty-goalkeeper\"", played.data)
                self.assertEqual(
                    played.data.count(b'class="penalty-direction-option"'), 3
                )
                self.assertIn(b'data-action="shot"', played.data)

                for _ in range(50):
                    with game.app.app_context():
                        db = game.get_db()
                        player_match = db.execute(
                            """SELECT id, home_score, away_score, home_club_id,
                                      away_club_id, shootout_state, winner_team
                               FROM promotion_playoff_matches
                               WHERE stage = ?
                                 AND (home_club_id IS NULL OR away_club_id IS NULL)""",
                            (stage,),
                        ).fetchone()
                        saved_score = (
                            player_match["home_score"],
                            player_match["away_score"],
                        )
                        if player_match["winner_team"] is not None:
                            break
                        kicks = json.loads(player_match["shootout_state"]).get(
                            "kicks", []
                        )
                        turn = "home" if len(kicks) % 2 == 0 else "away"
                        user_side = (
                            "home" if player_match["home_club_id"] is None else "away"
                        )
                        direction = "left" if turn == user_side else "right"
                    with patch.object(game.random, "choice", return_value="right"):
                        played = self.client.post(
                            "/torneo/playoff/penal",
                            data={"direction": direction},
                            follow_redirects=True,
                        )
                    self.assertEqual(played.status_code, 200)
                    self.assertIn("#promotion-playoff", played.history[0].location)
                    self.assertIsNone(played.request.args.get("playoff_live"))
                    self.assertNotIn(b"SIMULACI\xc3\x93N EN VIVO", played.data)
                    if b"Clasifica:" not in played.data:
                        self.assertIn(
                            b"class=\"penalty-shootout-scene\"", played.data
                        )
                        kicks_played = len(kicks) + 1
                        next_side = "home" if kicks_played % 2 == 0 else "away"
                        expected_action = (
                            "shot" if next_side == user_side else "save"
                        )
                        self.assertIn(
                            f'data-action="{expected_action}"'.encode(),
                            played.data,
                        )
                    with game.app.app_context():
                        persisted_match = game.get_db().execute(
                            """SELECT home_score, away_score FROM promotion_playoff_matches
                               WHERE id = ?""",
                            (player_match["id"],),
                        ).fetchone()
                        self.assertEqual(
                            (
                                persisted_match["home_score"],
                                persisted_match["away_score"],
                            ),
                            saved_score,
                        )
                else:
                    self.fail("La tanda de penales no terminó después de 50 remates.")
                self.assertIn(b"Clasifica:", played.data)
                self.assertIn(b'class="playoff-matches"', played.data)
            else:
                self.assertNotIn(b"Gan\xc3\xb3 en los 90", played.data)
                completed = self.client.get("/calendario")
                self.assertIn(b"Clasifica:", completed.data)
                self.assertIn(b"Gan\xc3\xb3 en los 90", completed.data)
            if next_stage:
                advanced = self.client.post(
                    "/torneo/playoff/avanzar", follow_redirects=True
                )
                self.assertIn("#promotion-playoff", advanced.history[0].location)
                self.assertIn(f"Avanzaste a {next_stage}".encode(), advanced.data)
            else:
                final = self.client.post(
                    "/torneo/playoff/avanzar", follow_redirects=True
                )
                self.assertIn(b"logr\xc3\xb3 el ascenso a Primera Divisi\xc3\xb3n", final.data)
                self.assertIn(b"COMENZAR TEMPORADA", final.data)
                with game.app.app_context():
                    self.assertEqual(game.get_career()["budget"], 8_625_000)
                    self.assertEqual(game.get_career()["division"], "Primera División")
                    self.assertEqual(game.get_career()["phase"], "market")
                    self.assertEqual(game.current_season_number(game.get_db()), 2)
                    promotion_movements = {
                        movement["team_name"]
                        for movement in game.get_season_movements(
                            game.get_db(), 1
                        )
                        if movement["description"].startswith("Ascenso")
                    }
                    self.assertEqual(
                        promotion_movements, {"Campeón", "Deportivo Sur"}
                    )
        with game.app.app_context():
            db = game.get_db()
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM promotion_playoff_matches WHERE stage='quarterfinal'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM promotion_playoff_matches WHERE stage='semifinal'"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) FROM promotion_playoff_matches WHERE stage='final'"
                ).fetchone()[0],
                0,
            )
            promotion = db.execute(
                "SELECT team_name FROM tournament_awards WHERE award_type='playoff_promotion_1'"
            ).fetchone()
        self.assertIsNotNone(promotion)
        self.assertIn(promotion["team_name"], (["Deportivo Sur"] + other_teams))

    def test_confirming_ai_playoff_promotion_does_not_error_and_allows_next_season(self):
        self.create_career(division="Primera Nacional")
        with game.app.app_context():
            db = game.get_db()
            db.execute("UPDATE career SET phase = 'season' WHERE id = 1")
            winner_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Playoff Winner', 'Primera Nacional') RETURNING id"""
            ).fetchone()["id"]
            opponent_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('Playoff Opponent', 'Primera Nacional') RETURNING id"""
            ).fetchone()["id"]
            champion_id = db.execute(
                """INSERT INTO clubs (name, division)
                   VALUES ('League Champion', 'Primera Nacional') RETURNING id"""
            ).fetchone()["id"]
            db.execute(
                """INSERT INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES ('promotion_1_club_' || ?, 'League Champion',
                           'Ascenso directo a Primera División')""",
                (champion_id,),
            )
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'Playoff Winner', 'Deportivo Sur',
                           ?, NULL, 70, 60, 2, 0)""",
                (winner_id,),
            )
            db.execute(
                """INSERT INTO promotion_playoff_progress (id, current_stage)
                   VALUES (1, 'final')"""
            )
            db.execute(
                """INSERT INTO promotion_playoff_matches
                   (stage, match_number, home_seed, away_seed, home_team, away_team,
                    home_club_id, away_club_id, home_overall, away_overall,
                    home_score, away_score, winner_seed, winner_team,
                    winner_club_id, winner_overall)
                   VALUES ('final', 1, 2, 3, 'Playoff Winner', 'Playoff Opponent',
                           ?, ?, 70, 60, 2, 0, 2, 'Playoff Winner', ?, 70)""",
                (winner_id, opponent_id, winner_id),
            )
            db.execute(
                "UPDATE tournament_progress SET current_round = 1 WHERE id = 1"
            )
            db.commit()

        confirmed = self.client.post(
            "/torneo/playoff/avanzar", follow_redirects=True
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertIn(b"Playoff Winner logr\xc3\xb3 el ascenso", confirmed.data)
        self.assertIn(b"COMENZAR TEMPORADA 2", confirmed.data)
        with game.app.app_context():
            db = game.get_db()
            award = db.execute(
                """SELECT team_name FROM tournament_awards
                   WHERE award_type = 'playoff_promotion_1_club_' || ?""",
                (winner_id,),
            ).fetchone()
            self.assertEqual(award["team_name"], "Playoff Winner")
            promoted = {
                movement["team_name"]
                for movement in game.get_season_movements(db, 1)
                if movement["description"].startswith("Ascenso")
            }
            self.assertEqual(
                promoted, {"League Champion", "Playoff Winner"}
            )

        next_season = self.client.post(
            "/temporada/nueva", follow_redirects=True
        )
        self.assertEqual(next_season.status_code, 200)
        with game.app.app_context():
            self.assertEqual(game.current_season_number(game.get_db()), 2)
            self.assertEqual(game.get_career()["phase"], "market")
            self.assertEqual(game.get_career()["division"], "Primera Nacional")

    def test_next_season_preserves_squad_and_keeps_roster_limit_at_25(self):
        self.create_career(division="Primera Nacional")
        dataset = {
            "season": 2026,
            "source": "next season test",
            "clubs": [
                {"provider_id": "national", "name": "Club Nacional", "division": "Primera Nacional"},
                {"provider_id": "first", "name": "Club Primera", "division": "Primera División"},
                {"provider_id": "first-low-a", "name": "Club Baja A", "division": "Primera División"},
                {"provider_id": "first-low-b", "name": "Club Baja B", "division": "Primera División"},
            ],
            "players": [
                {
                    "provider_id": f"national-{number}",
                    "club_provider_id": "national",
                    "name": f"Titular {number}",
                    "position": "DEF",
                    "age": 25,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 17)
            ] + [
                {
                    "provider_id": f"first-{number}",
                    "club_provider_id": "first",
                    "name": f"Refuerzo {number}",
                    "position": "MED",
                    "age": 22,
                    "overall": 70,
                    "market_value": 1_000_000,
                    "wage": 10_000,
                }
                for number in range(1, 10)
            ],
            "fixtures": [],
        }
        source = Path(self.temp_dir.name) / "next-season.json"
        source.write_text(json.dumps(dataset), encoding="utf-8")
        self.assertEqual(import_dataset(source, game.DATABASE), (4, 25, 0))
        with game.app.app_context():
            db = game.get_db()
            db.executemany(
                "INSERT INTO signings (player_id, fee) VALUES (?, 1)",
                [(player_id,) for player_id in range(1, 17)],
            )
            club_id = db.execute(
                "SELECT id FROM clubs WHERE name = 'Club Nacional'"
            ).fetchone()[0]
            db.execute(
                """INSERT INTO tournament_matches
                   (round_number, played_on, home_team, away_team, home_club_id,
                    away_club_id, home_overall, away_overall, home_score, away_score)
                   VALUES (1, '2026-01-01', 'Club Nacional', 'Deportivo Sur',
                           ?, NULL, 60, 70, 0, 1)""",
                (club_id,),
            )
            db.execute(
                "UPDATE tournament_progress SET current_round=1 WHERE id=1"
            )
            db.execute(
                "INSERT INTO promotion_playoff_progress (id, current_stage) VALUES (1, 'complete')"
            )
            db.execute(
                """INSERT INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES ('playoff_promotion_1', 'Deportivo Sur',
                           'Ascenso a Primera División por playoff')"""
            )
            db.execute(
                "UPDATE career SET phase='season', budget=20000000 WHERE id=1"
            )
            db.commit()

        response = self.client.post("/temporada/nueva")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.endswith("/mercado"))
        with game.app.app_context():
            db = game.get_db()
            career = game.get_career()
            self.assertEqual(career["phase"], "market")
            self.assertEqual(career["division"], "Primera División")
            self.assertEqual(career["season_start"], "2027-01-01")
            self.assertEqual(career["budget"], 20000000)
            self.assertEqual(game.current_season_number(db), 2)
            self.assertEqual(game.current_squad_limit(db), 25)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM signings").fetchone()[0], 16)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tournament_matches").fetchone()[0], 0)

        for player_id in range(17, 26):
            response = self.client.post("/mercado", data={"player_id": str(player_id)})
            self.assertIn(response.status_code, (302,), f"player_id={player_id}; {response.get_data(as_text=True)[:500]}")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location.partition("?")[0], "/mercado")
        with game.app.app_context():
            self.assertEqual(game.get_career()["phase"], "market")
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM signings").fetchone()[0],
                25,
            )
        self.client.post(
            "/mercado",
            data={"action": "start_tournament"},
        )
        with game.app.app_context():
            self.assertEqual(game.get_career()["phase"], "season")
        self.client.post("/mercado", data={"player_id": "22"})
        with game.app.app_context():
            self.assertEqual(
                game.get_db().execute("SELECT COUNT(*) FROM signings").fetchone()[0],
                25,
            )

    def test_live_football_api_sync_and_market_with_crests(self):
        """Test full sync with API dataset, checking Primera División and crests in market and fixture."""
        self.create_career(division="Primera División")
        client = LiveFootballAPIClient()
        result = client.sync_to_database(game.DATABASE)
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["clubs"], 48)
        self.assertGreaterEqual(result["players"], 400)
        self.assertGreaterEqual(result["fixtures"], 500)

        # Complete 20 days
        for day in range(1, 21):
            with game.app.app_context():
                decision_key = game.get_daily_options(game.get_db(), day)[0]["decision_key"]
            self.client.post("/club/decision", data={"decision": decision_key})

        # Market view
        response = self.client.get("/mercado")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"River Plate", response.data)
        self.assertIn(b"Boca Juniors", response.data)
        self.assertIn(b"club-crest-icon", response.data)
        self.assertIn(b"/static/crests/", response.data)

        # Fixtures view
        cal_resp = self.client.get("/calendario")
        self.assertEqual(cal_resp.status_code, 200)
        self.assertIn(b"FECHA", cal_resp.data)
        self.assertIn(b"fixture-crest-mini", cal_resp.data)

    def test_primera_nacional_sync_and_market(self):
        """Test Primera Nacional club flow and player display with escudos."""
        self.create_career(division="Primera Nacional")
        ensure_football_data_loaded(database_path=game.DATABASE)

        for day in range(1, 21):
            with game.app.app_context():
                decision_key = game.get_daily_options(game.get_db(), day)[0]["decision_key"]
            self.client.post("/club/decision", data={"decision": decision_key})

        response = self.client.get("/mercado")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Quilmes AC", response.data)
        self.assertIn(b"Ferro Carril Oeste", response.data)
        self.assertIn(b"club-crest-icon", response.data)

        cal_resp = self.client.get("/calendario")
        self.assertEqual(cal_resp.status_code, 200)
        self.assertIn(b"Primera Nacional", cal_resp.data)


if __name__ == "__main__":
    unittest.main()
