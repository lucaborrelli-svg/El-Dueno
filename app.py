from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, timedelta
from html import escape
from functools import lru_cache
from pathlib import Path
from collections.abc import Callable
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "career.sqlite3"))
SEASON_START = date(2026, 1, 1)
MAX_SQUAD_SIZE = 25
PLAYER_SALE_REVENUE = 500_000
MARKET_PAGE_SIZE = 12
SQUAD_FORMATIONS = {
    "4-4-2": (("DEL", 2), ("MED", 4), ("DEF", 4), ("ARQ", 1)),
    "4-3-3": (("DEL", 3), ("MED", 3), ("DEF", 4), ("ARQ", 1)),
    "4-2-3-1": (("DEL", 1), ("MED", 5), ("DEF", 4), ("ARQ", 1)),
}
AUTO_SQUAD_TARGETS = (("ARQ", 1), ("DEF", 4), ("MED", 4), ("DEL", 4))
POSITION_GROUPS = {
    "ARQ": {"ARQ", "GK", "G", "GOALKEEPER", "PORTERO", "PORTERA"},
    "DEF": {
        "DEF", "DF", "D", "DEFENDER", "DEFENSA", "CB", "LCB", "RCB",
        "LB", "RB", "LWB", "RWB", "DFC", "LI", "LD", "LAT", "LATERAL",
    },
    "MED": {
        "MED", "MF", "M", "MIDFIELDER", "MEDIOCAMPISTA", "CM", "CDM",
        "CAM", "DM", "RM", "LM", "MC", "MCD", "MCO", "MI", "MD", "VOL",
    },
    "DEL": {
        "DEL", "F", "FW", "ST", "CF", "FORWARD", "STRIKER", "ATTACKER",
        "DELANTERO", "DC", "SD", "LW", "RW", "EI", "ED",
    },
}
MAX_TRANSFER_FEE = 2_000_000
MAX_FIRST_DIVISION_TRANSFER_FEE = 5_000_000
DEFAULT_CREST_PRIMARY = "#c6fa57"
DEFAULT_CREST_SECONDARY = "#24334a"
DEFAULT_SHIRT_PRIMARY = "#c6fa57"
DEFAULT_SHIRT_SECONDARY = "#24334a"
SHIRT_PATTERNS = {
    "solid": "Liso",
    "stripes": "Rayas verticales",
    "hoops": "Franjas horizontales",
    "diagonal": "Banda diagonal",
    "halves": "Dos mitades",
}
DEFAULT_TEAM_SHIRT_PRIMARY = "#59636d"
DEFAULT_TEAM_SHIRT_SECONDARY = "#ffffff"
CREST_SYMBOLS = {
    "star": "Estrella",
    "stripes": "Barras",
    "ball": "Pelota",
    "initial": "Iniciales",
    "crown": "Corona",
    "diamond": "Diamante",
    "cross": "Cruz",
    "chevron": "Chevrón",
    "sun": "Sol",
    "mountain": "Montaña",
    "lightning": "Rayo",
    "anchor": "Ancla",
}
CREST_SHAPES = {
    "shield": "Escudo clásico",
    "round": "Redondo",
    "rounded": "Redondeado",
    "square": "Cuadrado",
}
FIRST_DIVISION_CHAMPION_PRIZE = 20_000_000
FIRST_NATIONAL_CHAMPION_PRIZE = 7_000_000
FIRST_DIVISION_TEAM_COUNT = 30
PLAYOFF_STAGE_LABELS = {
    "quarterfinal": "cuartos de final",
    "semifinal": "semifinales",
    "final": "la final",
    "complete": "el ascenso",
}
SEASON_DECISIONS = {
    "fatigue": {
        "title": "Rotación por desgaste físico",
        "context": "Se vienen dos fechas seguidas con poco descanso y un viaje largo.",
        "icon": "⚡",
        "options": {
            "rotate": {
                "title": "Rotar con suplentes",
                "description": "El equipo recupera energías, aunque pierde algo de fuerza en las próximas dos fechas.",
            },
            "play_starters": {
                "title": "Mantener a los titulares",
                "description": "Conservás el mejor equipo, con un 40% de riesgo de que una figura se pierda las próximas dos fechas.",
            },
        },
    },
    "rivalry": {
        "title": "Estrategia contra un rival directo",
        "context": "Un partido clave puede cambiar la pelea por el ascenso o el descenso.",
        "icon": "⚽",
        "options": {
            "defensive": {
                "title": "Planteo defensivo",
                "description": "Buscás asegurar el empate; la hinchada puede reclamar si el equipo juega mal.",
            },
            "offensive": {
                "title": "Salir a buscar los tres puntos",
                "description": "Aumenta la intensidad y también el riesgo de un resultado amplio.",
            },
        },
    },
    "referee": {
        "title": "Declaraciones tras una polémica arbitral",
        "context": "Después de una derrota, la prensa pregunta por un penal discutido.",
        "icon": "🎙",
        "options": {
            "criticize_referee": {
                "title": "Criticar el arbitraje",
                "description": "Ganás apoyo de la hinchada, pero aumenta el riesgo de fallos adversos en las próximas fechas.",
            },
            "diplomatic": {
                "title": "Responder con diplomacia",
                "description": "Baja un poco el apoyo popular y mantenés la calma institucional.",
            },
        },
    },
    "transfer_rumor": {
        "title": "Rumores por tu mediocampista titular",
        "context": "A mitad del torneo, un club europeo pregunta por una de tus figuras.",
        "icon": "↗",
        "options": {
            "untouchable": {
                "title": "Declararlo intransferible",
                "description": "Aumenta el valor de mercado, aunque el jugador puede molestarse y rendir menos.",
            },
            "hear_offers": {
                "title": "Escuchar ofertas públicamente",
                "description": "Entra dinero al club, pero el plantel puede perder concentración durante dos fechas.",
            },
        },
    },
    "rain": {
        "title": "Pronóstico de lluvia para el partido de local",
        "context": "Se espera una tormenta el día del próximo encuentro en casa.",
        "icon": "☂",
        "options": {
            "repair_pitch": {
                "title": "Invertir $8.000 en el drenaje",
                "description": "Mantenés la cancha en condiciones y protegés la recaudación y la localía.",
            },
            "save_money": {
                "title": "No invertir",
                "description": "Ahorrás ahora, pero baja la recaudación y aumenta la posibilidad de empate en el próximo partido de local.",
            },
        },
    },
    "stadium": {
        "title": "Mantenimiento y mejora del estadio",
        "context": "El club puede mejorar la iluminación y la experiencia en la cancha.",
        "icon": "⌂",
        "options": {
            "upgrade_stadium": {
                "title": "Financiar la mejora",
                "description": "Invertís $1.000.000 y sumás permanentemente 500 hinchas.",
            },
            "postpone_stadium": {
                "title": "Postergar la obra",
                "description": "Priorizás el presupuesto para el plantel y no hacés cambios.",
            },
        },
    },
    "supporters": {
        "title": "La hinchada pide hablar con el plantel",
        "context": "Tras dos derrotas, los hinchas piden una reunión con el equipo.",
        "icon": "◉",
        "options": {
            "meet_supporters": {
                "title": "Permitir el diálogo",
                "description": "Recuperás apoyo popular, aunque la tensión puede afectar el próximo partido.",
            },
            "hire_security": {
                "title": "Priorizar la tranquilidad del plantel",
                "description": "Pagás $300.000 en seguridad y aumenta el descontento de la hinchada.",
            },
        },
    },
    "training": {
        "title": "Preparación para el próximo partido",
        "context": "El cuerpo técnico propone ajustar la semana de entrenamientos.",
        "icon": "⚽",
        "options": {
            "tactical_training": {
                "title": "Practicar una variante táctica",
                "description": "Invertís $180.000 en el entrenamiento y el equipo llega mejor preparado al próximo partido.",
                "effects": {
                    "budget": -180000,
                    "performance_modifier": 2,
                    "performance_rounds": 1,
                    "outcome": "El equipo practicó una variante táctica y llega mejor preparado al próximo partido.",
                },
            },
            "recovery_training": {
                "title": "Priorizar la recuperación",
                "description": "Gastás $100.000 en recuperación y el plantel suma un pequeño impulso para la próxima fecha.",
                "effects": {
                    "budget": -100000,
                    "performance_modifier": 1,
                    "performance_rounds": 1,
                    "outcome": "El plantel completó una sesión de recuperación antes de la próxima fecha.",
                },
            },
        },
    },
    "player_bonus": {
        "title": "El plantel pide un incentivo",
        "context": "Los referentes proponen un premio para motivar al equipo en el próximo compromiso.",
        "icon": "$",
        "options": {
            "pay_win_bonus": {
                "title": "Aprobar un bono por rendimiento",
                "description": "Invertís $400.000 y el plantel recibe un impulso de motivación para el próximo partido.",
                "effects": {
                    "budget": -400000,
                    "performance_modifier": 2,
                    "performance_rounds": 1,
                    "outcome": "Aprobaste el bono por rendimiento y el plantel recibió un impulso de motivación.",
                },
            },
            "reject_win_bonus": {
                "title": "Cuidar el presupuesto",
                "description": "No sumás gastos, aunque algunos jugadores pueden perder motivación.",
                "effects": {
                    "fans": -50,
                    "performance_modifier": -1,
                    "performance_rounds": 1,
                    "outcome": "Cuidaste el presupuesto y el plantel quedó algo disconforme con la decisión.",
                },
            },
        },
    },
    "travel": {
        "title": "Organizar el viaje del plantel",
        "context": "El próximo encuentro requiere coordinar el traslado y el descanso del equipo.",
        "icon": "↗",
        "options": {
            "charter_bus": {
                "title": "Contratar un micro especial",
                "description": "Gastás $220.000 para mejorar el descanso y la preparación del plantel.",
                "effects": {
                    "budget": -220000,
                    "performance_modifier": 2,
                    "performance_rounds": 1,
                    "outcome": "Contrataste un micro especial; el equipo llegará mejor descansado al próximo encuentro.",
                },
            },
            "regular_bus": {
                "title": "Usar el traslado habitual",
                "description": "Ahorrás dinero, aunque el viaje puede afectar levemente el rendimiento.",
                "effects": {
                    "performance_modifier": -1,
                    "performance_rounds": 1,
                    "outcome": "Usaste el traslado habitual y mantuviste los gastos del club bajo control.",
                },
            },
        },
    },
    "media": {
        "title": "La prensa pide una definición sobre los objetivos",
        "context": "Una conferencia puede entusiasmar a la hinchada o bajar la presión sobre el equipo.",
        "icon": "🎙",
        "options": {
            "promise_promotion": {
                "title": "Prometer pelear por el ascenso",
                "description": "La hinchada se entusiasma, pero el plantel siente más presión en la próxima fecha.",
                "effects": {
                    "fans": 150,
                    "popularity": 3,
                    "performance_modifier": -1,
                    "performance_rounds": 1,
                    "outcome": "La promesa entusiasmó a la hinchada y elevó las expectativas.",
                },
            },
            "measured_message": {
                "title": "Mantener un mensaje prudente",
                "description": "Conservás la calma institucional y evitás sumar presión al vestuario.",
                "effects": {
                    "popularity": 1,
                    "outcome": "Elegiste un mensaje prudente y mantuviste la calma institucional.",
                },
            },
        },
    },
    "ticketing": {
        "title": "Definir el precio de las entradas",
        "context": "Se acerca un partido de local y el club debe decidir cómo convocar a su gente.",
        "icon": "▤",
        "options": {
            "family_tickets": {
                "title": "Ofrecer entradas populares",
                "description": "Invertís $100.000 en descuentos y sumás hinchas en las tribunas.",
                "effects": {
                    "budget": -100000,
                    "fans": 250,
                    "popularity": 1,
                    "outcome": "Los precios populares acercaron más hinchas al estadio.",
                },
            },
            "premium_tickets": {
                "title": "Subir el precio de las entradas",
                "description": "Ingresan $350.000 extra, aunque algunos hinchas se quedan afuera.",
                "effects": {
                    "budget": 350000,
                    "fans": -100,
                    "popularity": -1,
                    "outcome": "La suba de precios mejoró la recaudación, pero generó malestar entre algunos hinchas.",
                },
            },
        },
    },
    "academy": {
        "title": "Impulsar las divisiones juveniles",
        "context": "El coordinador de inferiores presenta dos propuestas para acercar el club a los jóvenes.",
        "icon": "⌁",
        "options": {
            "fund_academy": {
                "title": "Apoyar una jornada de formación",
                "description": "Invertís $250.000 en las inferiores y fortalecés el vínculo con la comunidad.",
                "effects": {
                    "budget": -250000,
                    "fans": 100,
                    "popularity": 2,
                    "outcome": "Financiaste una jornada de formación para las divisiones juveniles.",
                },
            },
            "youth_showcase": {
                "title": "Organizar una exhibición juvenil",
                "description": "Gastás $120.000 y abrís el club a nuevos simpatizantes.",
                "effects": {
                    "budget": -120000,
                    "fans": 220,
                    "popularity": 2,
                    "outcome": "La exhibición juvenil acercó nuevos vecinos al club.",
                },
            },
        },
    },
    "facilities": {
        "title": "Mejoras en el centro de entrenamiento",
        "context": "El personal detectó detalles que se pueden mejorar en las instalaciones.",
        "icon": "⌂",
        "options": {
            "maintain_training_ground": {
                "title": "Reparar el campo de entrenamiento",
                "description": "Invertís $350.000 y el equipo gana comodidad para preparar los próximos partidos.",
                "effects": {
                    "budget": -350000,
                    "performance_modifier": 1,
                    "performance_rounds": 2,
                    "outcome": "Reparaste el campo de entrenamiento y mejoraste la preparación del equipo.",
                },
            },
            "defer_training_ground": {
                "title": "Postergar las mejoras",
                "description": "Evitás el gasto ahora, aunque las prácticas seguirán con algunas limitaciones.",
                "effects": {
                    "performance_modifier": -1,
                    "performance_rounds": 1,
                    "outcome": "Postergaste las mejoras para cuidar el presupuesto del club.",
                },
            },
        },
    },
}
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

DECISIONS = {
    "local_sponsor": {
        "title": "Cerrar un acuerdo con un comercio local",
        "description": "Un negocio del barrio apuesta por el proyecto.",
        "icon": "✦",
        "effects": {"budget": 1250000, "fans": 80, "popularity": 2},
    },
    "regional_sponsor": {
        "title": "Negociar con una marca regional",
        "description": "Un patrocinador ofrece un aporte más grande, con objetivos de visibilidad.",
        "icon": "✦",
        "effects": {"budget": 3100000, "fans": 120, "popularity": 3},
    },
    "open_training": {
        "title": "Abrir un entrenamiento a los hinchas",
        "description": "Acercá el equipo a la gente y hacé crecer la convocatoria.",
        "icon": "◉",
        "effects": {"budget": -650000, "fans": 420, "popularity": 3},
    },
    "press_day": {
        "title": "Organizar una jornada de prensa",
        "description": "Presentá el proyecto y ganá visibilidad.",
        "icon": "▤",
        "effects": {"budget": -280000, "fans": 90, "popularity": 5},
    },
    "youth_trials": {
        "title": "Probar jugadores juveniles",
        "description": "Una prueba abierta para descubrir talentos de la zona.",
        "icon": "⌁",
        "effects": {"budget": -480000, "fans": 180, "popularity": 1},
    },
    "shirt_launch": {
        "title": "Lanzar la primera camiseta",
        "description": "La venta deja un ingreso acotado y suma nuevos simpatizantes.",
        "icon": "◆",
        "effects": {"budget": 850000, "fans": 260, "popularity": 2},
    },
    "community_day": {
        "title": "Hacer una acción solidaria",
        "description": "El club visita y ayuda a una institución de la comunidad.",
        "icon": "♡",
        "effects": {"budget": -320000, "fans": 240, "popularity": 4},
    },
    "stadium_maintenance": {
        "title": "Poner a punto el estadio",
        "description": "Un mantenimiento básico mejora la cancha para los entrenamientos.",
        "icon": "⌂",
        "effects": {"budget": -1100000, "fans": 40, "popularity": 1},
    },
    "food_stalls": {
        "title": "Dar lugar a puestos de comida",
        "description": "Un acuerdo para los días de entrenamiento suma una recaudación modesta.",
        "icon": "＋",
        "effects": {"budget": 640000, "fans": 110, "popularity": 1},
    },
    "local_campaign": {
        "title": "Hacer una campaña en el barrio",
        "description": "Contá la historia del club y convocá a nuevos hinchas.",
        "icon": "◎",
        "effects": {"budget": -150000, "fans": 330, "popularity": 3},
    },
    "equipment_sale": {
        "title": "Vender equipamiento sin uso",
        "description": "Ordená el depósito y recuperá una pequeña parte de la inversión.",
        "icon": "↗",
        "effects": {"budget": 420000, "fans": 0, "popularity": 0},
    },
    "sponsor_withdrawal": {
        "title": "Perder un patrocinador",
        "description": "Una empresa reduce su apoyo y baja el entusiasmo alrededor del proyecto.",
        "icon": "↘",
        "effects": {"budget": -900000, "fans": -70, "popularity": -2},
    },
    "poor_turnout": {
        "title": "Una convocatoria menor a la esperada",
        "description": "El evento no logra atraer público y deja menos ingresos.",
        "icon": "◌",
        "effects": {"budget": -380000, "fans": -140, "popularity": -2},
    },
    "budget_bonus": {
        "title": "Recibir un aporte de socios",
        "description": "Un grupo de socios fundadores ayuda con un fondo pequeño.",
        "icon": "$",
        "effects": {"budget": 1750000, "fans": 35, "popularity": 1},
    },
    "fan_membership": {
        "title": "Lanzar una campaña de socios",
        "description": "Más vecinos se asocian y ayudan a sostener el club.",
        "icon": "◉",
        "effects": {"budget": 520000, "fans": 290, "popularity": 2},
    },
    "ticket_refunds": {
        "title": "Devolver entradas por una cancelación",
        "description": "Un cambio de planes implica reembolsos y una pequeña caída de popularidad.",
        "icon": "↙",
        "effects": {"budget": -540000, "fans": -45, "popularity": -3},
    },
    "social_campaign": {
        "title": "Publicar contenido del club",
        "description": "Una campaña orgánica suma alcance sin gastar casi nada.",
        "icon": "▤",
        "effects": {"budget": -80000, "fans": 125, "popularity": 4},
    },
    "supply_costs": {
        "title": "Cubrir gastos imprevistos",
        "description": "Suben los costos de transporte y materiales del entrenamiento.",
        "icon": "!",
        "effects": {"budget": -720000, "fans": 0, "popularity": -1},
    },
    "sponsor_delay": {
        "title": "Esperar un pago de patrocinio",
        "description": "Una empresa demora una cuota y complica los gastos de la semana.",
        "icon": "⌛",
        "effects": {"budget": -350000, "fans": 0, "popularity": -1},
    },
    "youth_scouting": {
        "title": "Enviar un captador al interior",
        "description": "Recorré clubes de la zona para encontrar jóvenes talentos.",
        "icon": "⌁",
        "effects": {"budget": -390000, "fans": 80, "popularity": 1},
    },
    "kit_supplier": {
        "title": "Conseguir un proveedor de indumentaria",
        "description": "Un acuerdo con un taller local reduce el costo de la ropa de entrenamiento.",
        "icon": "◆",
        "effects": {"budget": 580000, "fans": 45, "popularity": 1},
    },
    "supporter_store": {
        "title": "Abrir una tienda online para socios",
        "description": "Empezá a vender productos del club por redes sociales.",
        "icon": "▣",
        "effects": {"budget": 720000, "fans": 170, "popularity": 2},
    },
    "fan_festival": {
        "title": "Organizar una fiesta para los hinchas",
        "description": "Una tarde de música y fútbol para reunir a la comunidad.",
        "icon": "♫",
        "effects": {"budget": -460000, "fans": 310, "popularity": 4},
    },
    "former_players": {
        "title": "Invitar a referentes históricos",
        "description": "Exjugadores participan de una charla con las divisiones juveniles.",
        "icon": "★",
        "effects": {"budget": -210000, "fans": 180, "popularity": 3},
    },
    "school_visit": {
        "title": "Visitar una escuela del barrio",
        "description": "Jugadores y cuerpo técnico comparten una mañana con los chicos.",
        "icon": "♡",
        "effects": {"budget": -170000, "fans": 230, "popularity": 3},
    },
    "derby_campaign": {
        "title": "Promocionar el primer clásico",
        "description": "Una campaña local despierta curiosidad por el próximo partido.",
        "icon": "◎",
        "effects": {"budget": -260000, "fans": 200, "popularity": 2},
    },
    "volunteer_network": {
        "title": "Convocar voluntarios para el club",
        "description": "Vecinos ofrecen su tiempo para ayudar con las tareas cotidianas.",
        "icon": "＋",
        "effects": {"budget": 140000, "fans": 110, "popularity": 2},
    },
    "pitch_repair": {
        "title": "Reparar el campo de entrenamiento",
        "description": "Arreglá sectores del terreno para evitar suspender prácticas.",
        "icon": "⌂",
        "effects": {"budget": -880000, "fans": 0, "popularity": 1},
    },
    "medical_checkups": {
        "title": "Hacer chequeos médicos al plantel",
        "description": "Controles de rutina para empezar la temporada con tranquilidad.",
        "icon": "＋",
        "effects": {"budget": -520000, "fans": 0, "popularity": 1},
    },
    "team_bus": {
        "title": "Alquilar un micro para el plantel",
        "description": "Asegurá el traslado para los próximos amistosos.",
        "icon": "↗",
        "effects": {"budget": -760000, "fans": 35, "popularity": 0},
    },
    "budget_review": {
        "title": "Revisar los contratos del club",
        "description": "Encontrá gastos duplicados y ordená las cuentas.",
        "icon": "▤",
        "effects": {"budget": 460000, "fans": 0, "popularity": 1},
    },
    "disciplinary_fine": {
        "title": "Pagar una multa disciplinaria",
        "description": "Una sanción por incidentes en un amistoso golpea las finanzas.",
        "icon": "!",
        "effects": {"budget": -640000, "fans": -60, "popularity": -2},
    },
    "transfer_rumor": {
        "title": "Desmentir un rumor de fichaje",
        "description": "Un rumor que no se concreta genera algo de malestar en la tribuna.",
        "icon": "◌",
        "effects": {"budget": -90000, "fans": -100, "popularity": -2},
    },
    "friendly_cancellation": {
        "title": "Reprogramar un amistoso suspendido",
        "description": "Devolvé entradas y reorganizá el traslado del equipo.",
        "icon": "↙",
        "effects": {"budget": -310000, "fans": -75, "popularity": -1},
    },
    "rain_damage": {
        "title": "Arreglar daños por una tormenta",
        "description": "El mal tiempo provoca reparaciones urgentes en las instalaciones.",
        "icon": "⌂",
        "effects": {"budget": -970000, "fans": 0, "popularity": -1},
    },
    "municipal_support": {
        "title": "Recibir apoyo para el deporte barrial",
        "description": "Un programa local aporta una ayuda puntual al club.",
        "icon": "$",
        "effects": {"budget": 1050000, "fans": 100, "popularity": 2},
    },
    "neighborhood_billboard": {
        "title": "Lanzar una campaña con comercios vecinos",
        "description": "Locales de la zona exhiben los colores del equipo.",
        "icon": "▤",
        "effects": {"budget": -180000, "fans": 270, "popularity": 3},
    },
    "local_radio": {
        "title": "Salir al aire en una radio local",
        "description": "Contá el proyecto y convocá nuevos simpatizantes en una entrevista.",
        "icon": "♫",
        "effects": {"budget": 50000, "fans": 145, "popularity": 3},
    },
    "match_stream": {
        "title": "Transmitir un amistoso por internet",
        "description": "Un sponsor cubre parte de los costos y el club gana audiencia.",
        "icon": "▣",
        "effects": {"budget": 360000, "fans": 185, "popularity": 2},
    },
    "membership_discount": {
        "title": "Ofrecer un descuento para nuevos socios",
        "description": "Una cuota promocional suma socios, aunque recauda un poco menos.",
        "icon": "◉",
        "effects": {"budget": -230000, "fans": 360, "popularity": 3},
    },
    "ticket_promotion": {
        "title": "Hacer una promoción para el amistoso",
        "description": "Una oferta accesible lleva más gente a la cancha.",
        "icon": "＋",
        "effects": {"budget": 390000, "fans": 220, "popularity": 2},
    },
    "food_drive": {
        "title": "Recolectar alimentos en la cancha",
        "description": "Los hinchas colaboran con comedores de la zona.",
        "icon": "♡",
        "effects": {"budget": -120000, "fans": 195, "popularity": 4},
    },
    "coaching_clinic": {
        "title": "Dar una clínica de fútbol infantil",
        "description": "Los entrenadores comparten ejercicios con chicos del barrio.",
        "icon": "⌁",
        "effects": {"budget": -300000, "fans": 245, "popularity": 3},
    },
    "womens_football": {
        "title": "Impulsar el fútbol femenino",
        "description": "Organizá una jornada de prueba y difusión para nuevas jugadoras.",
        "icon": "◎",
        "effects": {"budget": -410000, "fans": 210, "popularity": 4},
    },
    "stadium_accessibility": {
        "title": "Mejorar el acceso al estadio",
        "description": "Señalizá y acondicioná espacios para recibir mejor a todos.",
        "icon": "⌂",
        "effects": {"budget": -620000, "fans": 70, "popularity": 3},
    },
    "insurance_claim": {
        "title": "Resolver un reclamo de seguros",
        "description": "Un trámite inesperado lleva tiempo y genera gastos administrativos.",
        "icon": "▤",
        "effects": {"budget": -270000, "fans": 0, "popularity": -1},
    },
    "security_costs": {
        "title": "Reforzar la seguridad del predio",
        "description": "Contratá personal adicional para una jornada concurrida.",
        "icon": "!",
        "effects": {"budget": -570000, "fans": 20, "popularity": 1},
    },
    "equipment_theft": {
        "title": "Reponer material deportivo perdido",
        "description": "Faltan pelotas y elementos del depósito antes de la práctica.",
        "icon": "↘",
        "effects": {"budget": -490000, "fans": 0, "popularity": -1},
    },
    "unexpected_donation": {
        "title": "Recibir una donación de un exsocio",
        "description": "Un viejo colaborador ayuda a cubrir gastos del arranque.",
        "icon": "$",
        "effects": {"budget": 890000, "fans": 25, "popularity": 1},
    },
    "equipment_rental": {
        "title": "Alquilar el gimnasio fuera de horario",
        "description": "El espacio se usa para una actividad deportiva de la comunidad.",
        "icon": "⌂",
        "effects": {"budget": 310000, "fans": 75, "popularity": 1},
    },
    "parking_agreement": {
        "title": "Acordar estacionamiento para los partidos",
        "description": "Un predio cercano ofrece lugares y comparte una pequeña recaudación.",
        "icon": "↗",
        "effects": {"budget": 280000, "fans": 80, "popularity": 1},
    },
    "club_anthem": {
        "title": "Grabar una canción para el club",
        "description": "Músicos locales crean un tema para presentar en la cancha.",
        "icon": "♫",
        "effects": {"budget": -240000, "fans": 190, "popularity": 4},
    },
    "club_mascot": {
        "title": "Presentar la mascota del equipo",
        "description": "Una actividad familiar suma color a la previa de los partidos.",
        "icon": "★",
        "effects": {"budget": -330000, "fans": 230, "popularity": 3},
    },
    "grant_application": {
        "title": "Conseguir un subsidio para el club",
        "description": "Un programa deportivo aprueba una ayuda económica puntual.",
        "icon": "$",
        "effects": {"budget": 1380000, "fans": 50, "popularity": 1},
    },
    "supporter_travel": {
        "title": "Organizar el viaje de los hinchas",
        "description": "Coordiná transporte para acompañar al equipo en un amistoso.",
        "icon": "↗",
        "effects": {"budget": -370000, "fans": 160, "popularity": 3},
    },
    "social_media_backlash": {
        "title": "Responder a críticas en redes",
        "description": "Un anuncio confuso genera comentarios negativos y baja el alcance.",
        "icon": "◌",
        "effects": {"budget": -60000, "fans": -90, "popularity": -3},
    },
    "sponsor_activation": {
        "title": "Activar una promoción con un sponsor",
        "description": "Una acción comercial genera un ingreso extra y más exposición.",
        "icon": "✦",
        "effects": {"budget": 760000, "fans": 135, "popularity": 2},
    },
    "coach_workshop": {
        "title": "Capacitar al cuerpo técnico",
        "description": "Un taller mejora la preparación y organización de los entrenamientos.",
        "icon": "⌁",
        "effects": {"budget": -430000, "fans": 0, "popularity": 1},
    },
}


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error: BaseException | None) -> None:
    del _error
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database: Path = DATABASE) -> None:
    db = sqlite3.connect(database)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS clubs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            division TEXT NOT NULL CHECK (division IN ('Primera División', 'Primera Nacional')),
            province TEXT NOT NULL DEFAULT 'Argentina',
            provider_id TEXT UNIQUE,
            logo TEXT,
            shirt_primary TEXT,
            shirt_secondary TEXT,
            shirt_pattern TEXT
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            club_id INTEGER REFERENCES clubs(id) ON DELETE SET NULL,
            provider_id TEXT UNIQUE,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            age INTEGER,
            nationality TEXT NOT NULL DEFAULT 'Argentina',
            overall INTEGER NOT NULL DEFAULT 60,
            base_overall INTEGER,
            market_value INTEGER NOT NULL DEFAULT 1000000,
            wage INTEGER NOT NULL DEFAULT 50000
        );
        CREATE TABLE IF NOT EXISTS career (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            manager_name TEXT NOT NULL,
            club_name TEXT NOT NULL,
            division TEXT NOT NULL,
            province TEXT NOT NULL,
            season_start TEXT NOT NULL,
            phase TEXT NOT NULL DEFAULT 'preseason',
            day INTEGER NOT NULL DEFAULT 1,
            budget INTEGER NOT NULL DEFAULT 0,
            fans INTEGER NOT NULL DEFAULT 1200,
            popularity INTEGER NOT NULL DEFAULT 10,
            shirt_primary TEXT NOT NULL DEFAULT '{DEFAULT_SHIRT_PRIMARY}',
            shirt_secondary TEXT NOT NULL DEFAULT '{DEFAULT_SHIRT_SECONDARY}',
            shirt_pattern TEXT NOT NULL DEFAULT 'solid'
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY,
            day INTEGER NOT NULL UNIQUE,
            decision_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS daily_options (
            day INTEGER NOT NULL,
            slot INTEGER NOT NULL CHECK (slot BETWEEN 1 AND 3),
            decision_key TEXT NOT NULL,
            PRIMARY KEY (day, slot),
            UNIQUE (day, decision_key)
        );
        CREATE TABLE IF NOT EXISTS signings (
            id INTEGER PRIMARY KEY,
            player_id INTEGER NOT NULL REFERENCES players(id),
            signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            fee INTEGER NOT NULL,
            loan_season_number INTEGER
        );
        CREATE TABLE IF NOT EXISTS squad_lineup (
            formation TEXT NOT NULL CHECK (formation IN ('4-4-2', '4-3-3', '4-2-3-1')),
            slot_number INTEGER NOT NULL CHECK (slot_number BETWEEN 1 AND 11),
            player_id INTEGER NOT NULL REFERENCES players(id),
            PRIMARY KEY (formation, slot_number),
            UNIQUE (formation, player_id)
        );
        CREATE TABLE IF NOT EXISTS fixtures (
            id INTEGER PRIMARY KEY,
            season INTEGER NOT NULL,
            division TEXT NOT NULL CHECK (division IN ('Primera División', 'Primera Nacional')),
            matchday INTEGER NOT NULL,
            played_on TEXT NOT NULL,
            home_club_id INTEGER NOT NULL REFERENCES clubs(id),
            away_club_id INTEGER NOT NULL REFERENCES clubs(id),
            UNIQUE (season, division, matchday, home_club_id, away_club_id)
        );
        CREATE TABLE IF NOT EXISTS tournament_matches (
            id INTEGER PRIMARY KEY,
            round_number INTEGER NOT NULL,
            played_on TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_club_id INTEGER REFERENCES clubs(id),
            away_club_id INTEGER REFERENCES clubs(id),
            home_overall INTEGER NOT NULL,
            away_overall INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            match_events TEXT NOT NULL DEFAULT '[]',
            UNIQUE (round_number, home_team, away_team)
        );
        CREATE TABLE IF NOT EXISTS player_match_stats (
            season_number INTEGER NOT NULL,
            competition TEXT NOT NULL DEFAULT 'league',
            match_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL REFERENCES players(id),
            goals INTEGER NOT NULL DEFAULT 0,
            assists INTEGER NOT NULL DEFAULT 0,
            yellow_cards INTEGER NOT NULL DEFAULT 0,
            red_cards INTEGER NOT NULL DEFAULT 0,
            club_id INTEGER REFERENCES clubs(id) ON DELETE SET NULL,
            team_name TEXT,
            division TEXT,
            PRIMARY KEY (season_number, competition, match_id, player_id)
        );
        CREATE TABLE IF NOT EXISTS player_development_runs (
            season_number INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tournament_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_round INTEGER NOT NULL,
            current_season INTEGER NOT NULL DEFAULT 1,
            signing_limit INTEGER NOT NULL DEFAULT 25,
            formation TEXT NOT NULL DEFAULT '4-4-2',
            auto_simulation INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS season_decisions (
            season_number INTEGER NOT NULL,
            after_round INTEGER NOT NULL,
            event_key TEXT NOT NULL,
            choice_key TEXT,
            outcome TEXT,
            PRIMARY KEY (season_number, after_round)
        );
        CREATE TABLE IF NOT EXISTS player_injuries (
            season_number INTEGER NOT NULL,
            player_id INTEGER NOT NULL REFERENCES players(id),
            return_round INTEGER NOT NULL,
            PRIMARY KEY (season_number, player_id)
        );
        CREATE TABLE IF NOT EXISTS tournament_awards (
            award_type TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS promotion_playoff_matches (
            id INTEGER PRIMARY KEY,
            stage TEXT NOT NULL CHECK (stage IN ('quarterfinal', 'semifinal', 'final')),
            match_number INTEGER NOT NULL,
            home_seed INTEGER NOT NULL,
            away_seed INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_club_id INTEGER REFERENCES clubs(id),
            away_club_id INTEGER REFERENCES clubs(id),
            home_overall INTEGER NOT NULL,
            away_overall INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            home_penalties INTEGER,
            away_penalties INTEGER,
            shootout_state TEXT NOT NULL DEFAULT '{}',
            playoff_events TEXT NOT NULL DEFAULT '[]',
            winner_seed INTEGER,
            winner_team TEXT,
            winner_club_id INTEGER,
            winner_overall INTEGER,
            UNIQUE (stage, match_number)
        );
        CREATE TABLE IF NOT EXISTS promotion_playoff_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_stage TEXT NOT NULL CHECK (
                current_stage IN ('quarterfinal', 'semifinal', 'final', 'complete')
            )
        );
        CREATE TABLE IF NOT EXISTS copa_argentina_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            season_number INTEGER NOT NULL,
            current_round INTEGER NOT NULL DEFAULT 1,
            draw_revealed INTEGER NOT NULL DEFAULT 0,
            is_complete INTEGER NOT NULL DEFAULT 0,
            champion_team TEXT,
            prize_paid INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS copa_argentina_matches (
            id INTEGER PRIMARY KEY,
            season_number INTEGER NOT NULL,
            round_number INTEGER NOT NULL,
            match_number INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_club_id INTEGER REFERENCES clubs(id),
            away_club_id INTEGER REFERENCES clubs(id),
            home_overall INTEGER NOT NULL,
            away_overall INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            home_penalties INTEGER,
            away_penalties INTEGER,
            winner_team TEXT,
            winner_club_id INTEGER REFERENCES clubs(id),
            winner_overall INTEGER,
            match_events TEXT NOT NULL DEFAULT '[]',
            revealed INTEGER NOT NULL DEFAULT 0,
            is_bye INTEGER NOT NULL DEFAULT 0,
            UNIQUE (season_number, round_number, match_number)
        );
        CREATE TABLE IF NOT EXISTS data_imports (
            id INTEGER PRIMARY KEY,
            season INTEGER NOT NULL,
            source TEXT NOT NULL,
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            clubs_count INTEGER NOT NULL,
            players_count INTEGER NOT NULL,
            fixtures_count INTEGER NOT NULL
        );
        """
    )
    for table in ("clubs", "players"):
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        if "provider_id" not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN provider_id TEXT")
        db.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_provider_id ON {table}(provider_id)")
    club_cols = {row[1] for row in db.execute("PRAGMA table_info(clubs)").fetchall()}
    if "logo" not in club_cols:
        db.execute("ALTER TABLE clubs ADD COLUMN logo TEXT")
    for column in ("shirt_primary", "shirt_secondary", "shirt_pattern"):
        if column not in club_cols:
            db.execute(f"ALTER TABLE clubs ADD COLUMN {column} TEXT")
    player_cols = {row[1] for row in db.execute("PRAGMA table_info(players)").fetchall()}
    if "base_overall" not in player_cols:
        db.execute("ALTER TABLE players ADD COLUMN base_overall INTEGER")
    db.execute(
        "UPDATE players SET base_overall = overall WHERE base_overall IS NULL"
    )
    career_columns = {
        row[1] for row in db.execute("PRAGMA table_info(career)").fetchall()
    }
    if "season_start" not in career_columns:
        db.execute("ALTER TABLE career ADD COLUMN season_start TEXT")
        if "founded_on" in career_columns:
            db.execute("UPDATE career SET season_start = founded_on")
        db.execute("UPDATE career SET season_start = '2026-01-01' WHERE season_start IS NULL")
    for column, definition in (
        ("crest_primary", f"TEXT NOT NULL DEFAULT '{DEFAULT_CREST_PRIMARY}'"),
        ("crest_secondary", f"TEXT NOT NULL DEFAULT '{DEFAULT_CREST_SECONDARY}'"),
        ("crest_symbol", "TEXT NOT NULL DEFAULT 'star'"),
        ("crest_shape", "TEXT NOT NULL DEFAULT 'shield'"),
        ("shirt_primary", f"TEXT NOT NULL DEFAULT '{DEFAULT_SHIRT_PRIMARY}'"),
        ("shirt_secondary", f"TEXT NOT NULL DEFAULT '{DEFAULT_SHIRT_SECONDARY}'"),
        ("shirt_pattern", "TEXT NOT NULL DEFAULT 'solid'"),
    ):
        if column not in career_columns:
            db.execute(f"ALTER TABLE career ADD COLUMN {column} {definition}")
    tournament_progress_columns = {
        row[1] for row in db.execute("PRAGMA table_info(tournament_progress)").fetchall()
    }
    if "current_season" not in tournament_progress_columns:
        db.execute(
            "ALTER TABLE tournament_progress ADD COLUMN current_season INTEGER NOT NULL DEFAULT 1"
        )
    if "signing_limit" not in tournament_progress_columns:
        db.execute(
            "ALTER TABLE tournament_progress ADD COLUMN signing_limit INTEGER NOT NULL DEFAULT 25"
        )
    if "formation" not in tournament_progress_columns:
        db.execute(
            """ALTER TABLE tournament_progress
               ADD COLUMN formation TEXT NOT NULL DEFAULT '4-4-2'"""
        )
    if "auto_simulation" not in tournament_progress_columns:
        db.execute(
            """ALTER TABLE tournament_progress
               ADD COLUMN auto_simulation INTEGER NOT NULL DEFAULT 0"""
        )
    tournament_match_columns = {
        row[1] for row in db.execute("PRAGMA table_info(tournament_matches)").fetchall()
    }
    if "match_events" not in tournament_match_columns:
        db.execute(
            """ALTER TABLE tournament_matches
               ADD COLUMN match_events TEXT NOT NULL DEFAULT '[]'"""
        )
    playoff_match_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(promotion_playoff_matches)").fetchall()
    }
    if "shootout_state" not in playoff_match_columns:
        db.execute(
            """ALTER TABLE promotion_playoff_matches
               ADD COLUMN shootout_state TEXT NOT NULL DEFAULT '{}'"""
        )
    if "playoff_events" not in playoff_match_columns:
        db.execute(
            """ALTER TABLE promotion_playoff_matches
               ADD COLUMN playoff_events TEXT NOT NULL DEFAULT '[]'"""
        )
    player_match_stats_columns = {
        row[1] for row in db.execute("PRAGMA table_info(player_match_stats)").fetchall()
    }
    if "competition" not in player_match_stats_columns:
        db.execute(
            """ALTER TABLE player_match_stats
               ADD COLUMN competition TEXT NOT NULL DEFAULT 'league'"""
        )
    for column, definition in (
        ("assists", "INTEGER NOT NULL DEFAULT 0"),
        ("club_id", "INTEGER REFERENCES clubs(id) ON DELETE SET NULL"),
        ("team_name", "TEXT"),
        ("division", "TEXT"),
    ):
        if column not in player_match_stats_columns:
            db.execute(
                f"ALTER TABLE player_match_stats ADD COLUMN {column} {definition}"
            )
    signing_columns = {
        row[1] for row in db.execute("PRAGMA table_info(signings)").fetchall()
    }
    if "loan_season_number" not in signing_columns:
        db.execute("ALTER TABLE signings ADD COLUMN loan_season_number INTEGER")
    copa_progress_columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(copa_argentina_progress)").fetchall()
    }
    if "prize_paid" not in copa_progress_columns:
        db.execute(
            """ALTER TABLE copa_argentina_progress
               ADD COLUMN prize_paid INTEGER NOT NULL DEFAULT 0"""
        )
    db.execute(
        """INSERT OR IGNORE INTO tournament_progress
           (id, current_round, current_season, signing_limit)
           VALUES (1, 1, 1, ?)""",
        (MAX_SQUAD_SIZE,),
    )
    db.execute(
        "UPDATE tournament_progress SET signing_limit = ?",
        (MAX_SQUAD_SIZE,),
    )
    squad_limit = db.execute(
        "SELECT signing_limit FROM tournament_progress WHERE id = 1"
    ).fetchone()[0]
    excess_signings = db.execute(
        """SELECT id, fee FROM signings
           ORDER BY signed_at, id
           LIMIT -1 OFFSET ?""",
        (squad_limit,),
    ).fetchall()
    if excess_signings:
        db.executemany(
            "DELETE FROM signings WHERE id = ?",
            [(signing[0],) for signing in excess_signings],
        )
        db.execute(
            "UPDATE career SET budget = budget + ? WHERE id = 1",
            (sum(signing[1] for signing in excess_signings),),
        )
    db.execute("DROP TRIGGER IF EXISTS limit_signings_before_insert")
    db.execute(
        f"""CREATE TRIGGER limit_signings_before_insert
            BEFORE INSERT ON signings
            WHEN (SELECT COUNT(*) FROM signings) >= {MAX_SQUAD_SIZE}
            BEGIN
                SELECT RAISE(ABORT, 'plantel completo');
            END"""
    )
    for club in db.execute(
        """SELECT id, logo, shirt_primary, shirt_secondary
           FROM clubs
           WHERE logo IS NOT NULL"""
    ).fetchall():
        inferred = infer_shirt_colors_from_logo(club[1])
        if inferred is not None:
            db.execute(
                """UPDATE clubs
                   SET shirt_primary = ?,
                       shirt_secondary = ?,
                       shirt_pattern = 'solid'
                   WHERE id = ?""",
                (*inferred, club[0]),
            )
    db.commit()
    db.close()


def get_career() -> sqlite3.Row | None:
    return get_db().execute("SELECT * FROM career WHERE id = 1").fetchone()


def get_daily_options(db: sqlite3.Connection, day: int) -> list[sqlite3.Row]:
    options = db.execute(
        """SELECT slot, decision_key FROM daily_options
           WHERE day = ? ORDER BY slot""",
        (day,),
    ).fetchall()
    if not options:
        recent_keys = {
            row["decision_key"]
            for row in db.execute(
                """SELECT DISTINCT decision_key FROM daily_options
                   WHERE day BETWEEN ? AND ?""",
                (max(1, day - 5), day - 1),
            ).fetchall()
        }
        available = [key for key in DECISIONS if key not in recent_keys]
        if len(available) < 3:
            available = list(DECISIONS)
        selected = random.sample(available, 3)
        db.executemany(
            "INSERT INTO daily_options (day, slot, decision_key) VALUES (?, ?, ?)",
            [(day, slot, key) for slot, key in enumerate(selected, start=1)],
        )
        db.commit()
        options = db.execute(
            """SELECT slot, decision_key FROM daily_options
               WHERE day = ? ORDER BY slot""",
            (day,),
        ).fetchall()
    return options


def money(value: int) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}".replace(",", ".")


def transfer_fee(market_value: int, division: str = "Primera Nacional") -> int:
    increased_value = (market_value * 120 + 99) // 100
    maximum_fee = (
        MAX_FIRST_DIVISION_TRANSFER_FEE
        if division == "Primera División"
        else MAX_TRANSFER_FEE
    )
    return min(maximum_fee, increased_value)


def player_position_group(position: str) -> str | None:
    normalized_position = position.strip().upper()
    return next(
        (
            group
            for group, positions in POSITION_GROUPS.items()
            if normalized_position in positions
        ),
        None,
    )


def loan_fee(market_value: int) -> int:
    return max(50_000, (market_value + 9) // 10)


def continental_qualification(division: str, position: int) -> str | None:
    if division != "Primera División":
        return None
    if position <= 3:
        return "libertadores"
    if position <= 9:
        return "sudamericana"
    return None


def first_division_prize(position: int) -> int:
    if not 1 <= position <= FIRST_DIVISION_TEAM_COUNT - 1:
        return 0
    return FIRST_DIVISION_CHAMPION_PRIZE * (
        FIRST_DIVISION_TEAM_COUNT - 1 - position
    ) // (FIRST_DIVISION_TEAM_COUNT - 2)


def first_national_prize(position: int, team_count: int) -> int:
    if team_count < 2 or not 1 <= position <= team_count:
        return 0
    return FIRST_NATIONAL_CHAMPION_PRIZE * (team_count - position) // (team_count - 1)


def get_season_movements(
    db: sqlite3.Connection, season_number: int
) -> list[sqlite3.Row]:
    awards = db.execute(
        "SELECT award_type, team_name, description FROM tournament_awards"
    ).fetchall()
    exact_award_types = {
        f"promotion_{season_number}",
        f"playoff_promotion_{season_number}",
        f"relegation_{season_number}",
    }
    award_prefixes = (
        f"promotion_{season_number}_club_",
        f"playoff_promotion_{season_number}_club_",
        f"relegation_{season_number}_club_",
    )
    return [
        award
        for award in awards
        if award["description"]
        in ("Ascenso directo a Primera División",
            "Ascenso a Primera División por playoff",
            "Descenso a Primera Nacional")
        and (
            award["award_type"] in exact_award_types
            or award["award_type"].startswith(award_prefixes)
        )
    ]


def ensure_two_division_movements(
    db: sqlite3.Connection, season_number: int
) -> None:
    movements = get_season_movements(db, season_number)
    promoted_names = {
        movement["team_name"]
        for movement in movements
        if movement["description"].startswith("Ascenso")
    }
    relegated_names = {
        movement["team_name"]
        for movement in movements
        if movement["description"].startswith("Descenso")
    }
    for conflicting_name in promoted_names & relegated_names:
        db.execute(
            """DELETE FROM tournament_awards
               WHERE team_name = ?
               AND (award_type = ? OR award_type LIKE ?)
               AND description IN (
                   'Ascenso directo a Primera División',
                   'Ascenso a Primera División por playoff'
               )""",
            (
                conflicting_name,
                f"promotion_{season_number}",
                f"promotion_{season_number}_%",
            ),
        )
    if promoted_names & relegated_names:
        movements = get_season_movements(db, season_number)

    promoted_names = {
        movement["team_name"]
        for movement in movements
        if movement["description"].startswith("Ascenso")
    }
    relegated_names = {
        movement["team_name"]
        for movement in movements
        if movement["description"].startswith("Descenso")
    }
    previous_movements = (
        get_season_movements(db, season_number - 1)
        if season_number > 1
        else []
    )
    previous_promotions = {
        movement["team_name"]
        for movement in previous_movements
        if movement["description"].startswith("Ascenso")
    }
    if len(promoted_names) < 2:
        candidates = db.execute(
            """SELECT c.id, c.name FROM clubs c
               LEFT JOIN players p ON p.club_id = c.id
               WHERE c.division = 'Primera Nacional'
               GROUP BY c.id
               ORDER BY COALESCE(AVG(p.overall), 60) DESC, c.name"""
        ).fetchall()
        for club in candidates:
            if club["name"] in (
                promoted_names | previous_promotions | relegated_names
            ):
                continue
            db.execute(
                """INSERT OR IGNORE INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES (?, ?, 'Ascenso directo a Primera División')""",
                (
                    f"promotion_{season_number}_club_{club['id']}",
                    club["name"],
                ),
            )
            promoted_names.add(club["name"])
            if len(promoted_names) == 2:
                break

def arrange_squad(
    squad: list[sqlite3.Row],
    formation: str,
    saved_slots: dict[int, int] | None = None,
) -> tuple[list[dict[str, object]], list[sqlite3.Row]]:
    remaining = sorted(squad, key=lambda player: (-player["overall"], player["name"]))
    players_by_id = {player["id"]: player for player in remaining}
    assigned: dict[int, sqlite3.Row] = {}
    for slot_number, player_id in (saved_slots or {}).items():
        player = players_by_id.get(player_id)
        if player:
            assigned[slot_number] = player
            remaining.remove(player)

    formation_lines: list[dict[str, object]] = []
    slot_number = 0
    for position, count in SQUAD_FORMATIONS[formation]:
        line_players: list[dict[str, object]] = []
        for _ in range(count):
            slot_number += 1
            player = assigned.get(slot_number)
            if not player:
                player_index = next(
                    (
                        index
                        for index, candidate in enumerate(remaining)
                        if candidate["position"] == position
                    ),
                    0 if remaining else None,
                )
                if player_index is not None:
                    player = remaining.pop(player_index)
            if player:
                line_players.append({**dict(player), "slot_number": slot_number})
        formation_lines.append({"position": position, "players": line_players})
    return formation_lines, remaining


def build_match_dashboard(
    db: sqlite3.Connection,
    career: sqlite3.Row,
    match: sqlite3.Row | dict[str, object] | None,
    user_formation: str,
    round_number: int,
) -> dict[str, object] | None:
    user_squad = db.execute(
        """SELECT p.*, c.name AS origin_club_name, c.logo AS origin_club_logo
           FROM signings s
           JOIN players p ON p.id = s.player_id
           LEFT JOIN clubs c ON c.id = p.club_id
           WHERE p.id NOT IN (
               SELECT player_id FROM player_injuries
               WHERE season_number = ? AND return_round > ?
           )
           ORDER BY p.overall DESC, p.name""",
        (
           current_season_number(db),
           round_number + int(round_complete(db, round_number)),
        ),
    ).fetchall()
    saved_slots = {
        row["slot_number"]: row["player_id"]
        for row in db.execute(
            "SELECT slot_number, player_id FROM squad_lineup WHERE formation = ?",
            (user_formation,),
        ).fetchall()
    }
    user_lines, _ = arrange_squad(user_squad, user_formation, saved_slots)
    if match is None:
        return {
            "bye": True,
            "round_number": round_number,
            "team_name": career["club_name"],
        }

    user_is_home = match["home_club_id"] is None
    opponent_id = match["away_club_id"] if user_is_home else match["home_club_id"]
    opponent = db.execute(
        """SELECT id, name, logo, shirt_primary, shirt_secondary, shirt_pattern
           FROM clubs WHERE id = ?""",
        (opponent_id,),
    ).fetchone()
    if opponent is None:
        return None
    career_shirt = team_shirt_style(
        career["club_name"],
        career["shirt_primary"],
        career["shirt_secondary"],
        career["shirt_pattern"],
    )
    opponent_shirt = team_shirt_style(
        opponent["name"],
        opponent["shirt_primary"],
        opponent["shirt_secondary"],
        opponent["shirt_pattern"],
        opponent["logo"],
    )

    opponent_squad = db.execute(
        """SELECT p.*, c.name AS origin_club_name, c.logo AS origin_club_logo
           FROM players p
           LEFT JOIN clubs c ON c.id = p.club_id
           WHERE p.club_id = ?
           ORDER BY p.overall DESC, p.name
           LIMIT 25""",
        (opponent["id"],),
    ).fetchall()
    opponent_formations = [
        (
            sum(
                int(player["overall"])
                for line in arrange_squad(opponent_squad, formation)[0]
                for player in line["players"]
            ),
            formation,
        )
        for formation in SQUAD_FORMATIONS
    ]
    _, opponent_formation = max(
        opponent_formations,
        key=lambda result: (result[0], -tuple(SQUAD_FORMATIONS).index(result[1])),
    )
    opponent_lines, _ = arrange_squad(opponent_squad, opponent_formation)

    home_team = {
        "name": career["club_name"] if user_is_home else opponent["name"],
        "logo": None if user_is_home else opponent["logo"],
        "formation": user_formation if user_is_home else opponent_formation,
        "lines": user_lines if user_is_home else opponent_lines,
        "is_career": user_is_home,
        **(career_shirt if user_is_home else opponent_shirt),
    }
    away_team = {
        "name": opponent["name"] if user_is_home else career["club_name"],
        "logo": opponent["logo"] if user_is_home else None,
        "formation": opponent_formation if user_is_home else user_formation,
        "lines": opponent_lines if user_is_home else user_lines,
        "is_career": not user_is_home,
        **(opponent_shirt if user_is_home else career_shirt),
    }
    return {
        "round_number": match["round_number"],
        "played_on": match["played_on"],
        "home": home_team,
        "away": away_team,
        "home_score": match["home_score"],
        "away_score": match["away_score"],
        "played": match["home_score"] is not None
        and match["away_score"] is not None,
        "events": json.loads(match["match_events"] or "[]"),
    }
    return None


def current_season_number(db: sqlite3.Connection) -> int:
    progress = db.execute(
        "SELECT current_season FROM tournament_progress WHERE id = 1"
    ).fetchone()
    return int(progress["current_season"]) if progress else 1


def current_squad_limit(db: sqlite3.Connection) -> int:
    return MAX_SQUAD_SIZE


def create_copa_argentina_round(
    db: sqlite3.Connection,
    season_number: int,
    round_number: int,
    teams: list[dict[str, int | str | None]],
    bye_count: int = 0,
) -> None:
    if round_number == 1:
        random.shuffle(teams)
    bye_teams = teams[:bye_count]
    paired_teams = teams[bye_count:]
    scheduled_matches = [
        (team, None, match_number)
        for match_number, team in enumerate(bye_teams, start=1)
    ]
    scheduled_matches.extend(
        (paired_teams[index], paired_teams[index + 1], match_number)
        for match_number, index in enumerate(
            range(0, len(paired_teams), 2),
            start=len(bye_teams) + 1,
        )
    )
    for home, away, match_number in scheduled_matches:
        is_bye = away is None
        db.execute(
            """INSERT INTO copa_argentina_matches
               (season_number, round_number, match_number, home_team, away_team,
                home_club_id, away_club_id, home_overall, away_overall,
                home_score, away_score, winner_team, winner_club_id,
                winner_overall, is_bye)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                season_number,
                round_number,
                match_number,
                home["name"],
                "Pasa libre" if is_bye else away["name"],
                home["club_id"],
                None if is_bye else away["club_id"],
                int(home["overall"]),
                0 if is_bye else int(away["overall"]),
                0 if is_bye else None,
                0 if is_bye else None,
                home["name"] if is_bye else None,
                home["club_id"] if is_bye else None,
                int(home["overall"]) if is_bye else None,
                int(is_bye),
            ),
        )


def ensure_copa_argentina(
    db: sqlite3.Connection, career: sqlite3.Row
) -> None:
    season_number = current_season_number(db)
    progress = db.execute(
        "SELECT season_number FROM copa_argentina_progress WHERE id = 1"
    ).fetchone()
    if progress and int(progress["season_number"]) == season_number:
        return

    clubs = db.execute(
        """SELECT c.id, c.name, COALESCE(AVG(p.overall), 60) AS overall
           FROM clubs c LEFT JOIN players p ON p.club_id = c.id
           WHERE c.division IN ('Primera División', 'Primera Nacional')
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    user_overall = db.execute(
        """SELECT COALESCE(AVG(p.overall), 60)
           FROM signings s JOIN players p ON p.id = s.player_id"""
    ).fetchone()[0]
    participants: list[dict[str, int | str | None]] = [
        {
            "name": club["name"],
            "club_id": int(club["id"]),
            "overall": round(club["overall"]),
        }
        for club in clubs
    ]
    participants.append(
        {
            "name": career["club_name"],
            "club_id": None,
            "overall": round(user_overall),
        }
    )
    if len(participants) < 2:
        raise ValueError("Se necesitan al menos dos equipos para sortear la Copa Argentina.")

    db.execute("DELETE FROM copa_argentina_matches")
    db.execute("DELETE FROM copa_argentina_progress")
    db.execute(
        """INSERT INTO copa_argentina_progress
           (id, season_number, current_round, draw_revealed, is_complete)
           VALUES (1, ?, 1, 0, 0)""",
        (season_number,),
    )
    bracket_size = 1 << (len(participants) - 1).bit_length()
    initial_byes = bracket_size - len(participants)
    create_copa_argentina_round(
        db, season_number, 1, participants, bye_count=initial_byes
    )
    db.commit()


def reveal_next_copa_argentina_match(db: sqlite3.Connection) -> tuple[int, int]:
    progress = db.execute(
        "SELECT season_number, current_round FROM copa_argentina_progress WHERE id = 1"
    ).fetchone()
    if progress is None:
        raise ValueError("El sorteo de la Copa Argentina todavía no está disponible.")
    match = db.execute(
        """SELECT id FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = ? AND revealed = 0
           ORDER BY match_number LIMIT 1""",
        (progress["season_number"], progress["current_round"]),
    ).fetchone()
    if match is None:
        raise ValueError("Ya se revelaron todos los cruces de esta ronda.")
    db.execute(
        "UPDATE copa_argentina_matches SET revealed = 1 WHERE id = ?",
        (match["id"],),
    )
    revealed, total = db.execute(
        """SELECT SUM(revealed), COUNT(*) FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = ?""",
        (progress["season_number"], progress["current_round"]),
    ).fetchone()
    db.execute(
        "UPDATE copa_argentina_progress SET draw_revealed = ? WHERE id = 1",
        (revealed,),
    )
    return int(revealed), int(total)


def copa_argentina_prize(
    round_number: int, final_round: int, champion: bool = False
) -> int:
    if champion:
        return 3_500_000
    rounds_remaining = final_round - round_number
    if rounds_remaining <= 0:
        return 2_000_000
    if rounds_remaining == 1:
        return 1_000_000
    if rounds_remaining == 2:
        return 500_000
    if rounds_remaining == 3:
        return 350_000
    return 250_000


def copa_argentina_final_round(
    db: sqlite3.Connection, season_number: int
) -> int:
    initial_round = db.execute(
        """SELECT COUNT(*) AS matches, SUM(is_bye) AS byes
           FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = 1""",
        (season_number,),
    ).fetchone()
    participants = int(initial_round["matches"]) * 2 - int(initial_round["byes"] or 0)
    if participants < 2:
        raise ValueError("No hay suficientes equipos en la Copa Argentina.")
    return (participants - 1).bit_length()


def copa_argentina_league_matchday(
    db: sqlite3.Connection, season_number: int, cup_round: int, league_rounds: int
) -> int:
    if league_rounds < 1:
        raise ValueError("No hay fechas de liga disponibles para programar la Copa.")
    cup_rounds = copa_argentina_final_round(db, season_number)
    if cup_round < 1 or cup_round > cup_rounds:
        raise ValueError("La ronda de Copa Argentina no es válida.")
    return min(
        league_rounds,
        max(1, cup_round * (league_rounds + 1) // (cup_rounds + 1)),
    )


def pay_copa_argentina_prize(
    db: sqlite3.Connection, amount: int
) -> bool:
    progress = db.execute(
        "SELECT prize_paid FROM copa_argentina_progress WHERE id = 1"
    ).fetchone()
    if progress is None or progress["prize_paid"]:
        return False
    db.execute(
        "UPDATE career SET budget = budget + ? WHERE id = 1", (amount,)
    )
    db.execute(
        "UPDATE copa_argentina_progress SET prize_paid = 1 WHERE id = 1"
    )
    return True


def play_copa_argentina_match(
    db: sqlite3.Connection, career: sqlite3.Row, match_id: int
) -> tuple[int, bool, str, int]:
    progress = db.execute(
        """SELECT season_number, current_round, draw_revealed, is_complete
           FROM copa_argentina_progress WHERE id = 1"""
    ).fetchone()
    if progress is None or int(progress["season_number"]) != current_season_number(db):
        raise ValueError("El sorteo de la Copa Argentina todavía no está disponible.")
    if progress["is_complete"]:
        raise ValueError("La Copa Argentina de esta temporada ya terminó.")
    match = db.execute(
        """SELECT * FROM copa_argentina_matches
           WHERE id = ? AND season_number = ? AND round_number = ?""",
        (match_id, progress["season_number"], progress["current_round"]),
    ).fetchone()
    if match is None:
        raise ValueError("Ese cruce no pertenece a la ronda actual.")
    if not match["revealed"]:
        raise ValueError("Revelá el cruce antes de disputar el partido.")
    if match["is_bye"]:
        raise ValueError("Este equipo pasó libre y no tiene partido que disputar.")
    if match["winner_team"] is not None:
        raise ValueError("Este cruce ya se disputó.")

    home_score, away_score = simulate_goals(
        int(match["home_overall"]), int(match["away_overall"])
    )
    home_penalties = None
    away_penalties = None
    home_wins = home_score > away_score
    if home_score == away_score:
        home_penalties = random.randint(3, 5)
        away_penalties = random.randint(3, 5)
        while home_penalties == away_penalties:
            home_penalties += random.choice((-1, 1))
        home_wins = home_penalties > away_penalties
    winner = "home" if home_wins else "away"
    winner_team = match[f"{winner}_team"]
    winner_club_id = match[f"{winner}_club_id"]
    winner_overall = match[f"{winner}_overall"]
    events = generate_match_events(db, match, home_score, away_score)
    record_player_match_stats(
        db,
        int(progress["season_number"]),
        match,
        events,
        competition="copa_argentina",
    )
    db.execute(
        """UPDATE copa_argentina_matches
           SET home_score = ?, away_score = ?, home_penalties = ?,
               away_penalties = ?, winner_team = ?, winner_club_id = ?,
               winner_overall = ?, match_events = ?
           WHERE id = ?""",
        (
            home_score,
            away_score,
            home_penalties,
            away_penalties,
            winner_team,
            winner_club_id,
            winner_overall,
            json.dumps(events, ensure_ascii=False),
            match["id"],
        ),
    )
    is_career_match = (
        (match["home_club_id"] is None and match["home_team"] == career["club_name"])
        or (
            match["away_club_id"] is None
            and match["away_team"] == career["club_name"]
        )
    )
    prize_awarded = 0
    if is_career_match and winner_team != career["club_name"]:
        final_round = copa_argentina_final_round(
            db, int(progress["season_number"])
        )
        prize = copa_argentina_prize(int(progress["current_round"]), final_round)
        if pay_copa_argentina_prize(db, prize):
            prize_awarded = prize
    return int(progress["current_round"]), is_career_match, winner_team, prize_awarded


def advance_copa_argentina_round(db: sqlite3.Connection) -> tuple[int, bool]:
    progress = db.execute(
        """SELECT season_number, current_round, draw_revealed, is_complete
           FROM copa_argentina_progress WHERE id = 1"""
    ).fetchone()
    if progress is None or progress["is_complete"]:
        raise ValueError("No hay una ronda de Copa Argentina para avanzar.")
    matches = db.execute(
        """SELECT * FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = ? ORDER BY match_number""",
        (progress["season_number"], progress["current_round"]),
    ).fetchall()
    if not matches or int(progress["draw_revealed"]) != len(matches):
        raise ValueError("Revelá todos los cruces antes de avanzar de ronda.")
    if any(match["winner_team"] is None for match in matches):
        raise ValueError("Disputá todos los partidos antes de avanzar de ronda.")

    winners = [
        {
            "name": match["winner_team"],
            "club_id": match["winner_club_id"],
            "overall": int(match["winner_overall"]),
        }
        for match in matches
    ]
    next_round = int(progress["current_round"]) + 1
    if len(winners) == 1:
        champion = winners[0]["name"]
        db.execute(
            """UPDATE copa_argentina_progress
               SET is_complete = 1, champion_team = ? WHERE id = 1""",
            (champion,),
        )
        db.execute(
            """INSERT OR IGNORE INTO tournament_awards
               (award_type, team_name, description)
               VALUES (?, ?, 'Campeón de la Copa Argentina')""",
            (f"copa_argentina_champion_{progress['season_number']}", champion),
        )
        return int(progress["current_round"]), True

    create_copa_argentina_round(
        db,
        int(progress["season_number"]),
        next_round,
        winners,
        bye_count=len(winners) % 2,
    )
    db.execute(
        """UPDATE copa_argentina_progress
           SET current_round = ?, draw_revealed = 0 WHERE id = 1""",
        (next_round,),
    )
    return next_round, False


def simulate_copa_argentina_round_automatically(
    db: sqlite3.Connection, career: sqlite3.Row
) -> None:
    progress = db.execute(
        """SELECT season_number, current_round, is_complete
           FROM copa_argentina_progress WHERE id = 1"""
    ).fetchone()
    if (
        progress is None
        or int(progress["season_number"]) != current_season_number(db)
        or progress["is_complete"]
    ):
        return

    matches = db.execute(
        """SELECT id, is_bye FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = ?
           ORDER BY match_number""",
        (progress["season_number"], progress["current_round"]),
    ).fetchall()
    if not matches:
        raise ValueError("No se encontraron cruces para la ronda actual de Copa Argentina.")

    db.execute(
        """UPDATE copa_argentina_matches SET revealed = 1
           WHERE season_number = ? AND round_number = ?""",
        (progress["season_number"], progress["current_round"]),
    )
    db.execute(
        """UPDATE copa_argentina_progress SET draw_revealed = ?
           WHERE id = 1""",
        (len(matches),),
    )
    for match in matches:
        if match["is_bye"]:
            continue
        current_match = db.execute(
            "SELECT winner_team FROM copa_argentina_matches WHERE id = ?",
            (match["id"],),
        ).fetchone()
        if current_match["winner_team"] is None:
            play_copa_argentina_match(db, career, int(match["id"]))

    round_number, complete = advance_copa_argentina_round(db)
    if not complete:
        return

    champion_match = db.execute(
        """SELECT winner_team, winner_club_id
           FROM copa_argentina_matches
           WHERE season_number = ? AND round_number = ?""",
        (progress["season_number"], round_number),
    ).fetchone()
    if champion_match is None:
        raise ValueError("No se pudo determinar al campeón de la Copa Argentina.")
    if (
        champion_match["winner_club_id"] is None
        and champion_match["winner_team"] == career["club_name"]
    ):
        prize = copa_argentina_prize(round_number, round_number, champion=True)
        pay_copa_argentina_prize(db, prize)


def finish_copa_argentina_automatically(
    db: sqlite3.Connection, career: sqlite3.Row
) -> None:
    while True:
        progress = db.execute(
            """SELECT season_number, current_round, is_complete
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if (
            progress is None
            or int(progress["season_number"]) != current_season_number(db)
            or progress["is_complete"]
        ):
            return
        current_round = int(progress["current_round"])
        simulate_copa_argentina_round_automatically(db, career)
        updated_progress = db.execute(
            """SELECT current_round, is_complete
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if (
            updated_progress is None
            or (
                int(updated_progress["current_round"]) == current_round
                and not updated_progress["is_complete"]
            )
        ):
            raise ValueError("No se pudo completar automáticamente la Copa Argentina.")


def ensure_tournament_schedule(
    db: sqlite3.Connection, career: sqlite3.Row
) -> None:
    if db.execute("SELECT 1 FROM tournament_matches LIMIT 1").fetchone():
        db.execute(
            """INSERT OR IGNORE INTO tournament_progress (id, current_round)
               SELECT 1, COALESCE(
                   (SELECT MIN(round_number) FROM tournament_matches
                    WHERE home_score IS NULL OR away_score IS NULL),
                   (SELECT MAX(round_number) FROM tournament_matches),
                   1
               )"""
        )
        db.commit()
        return

    balance_first_division_clubs(db, career)
    clubs = db.execute(
        """SELECT c.id, c.name, COALESCE(AVG(p.overall), 60) AS overall
           FROM clubs c LEFT JOIN players p ON p.club_id = c.id
           WHERE c.division = ? AND c.name != ?
           GROUP BY c.id ORDER BY c.name""",
        (career["division"], career["club_name"]),
    ).fetchall()
    if not clubs:
        return

    squad_overall = db.execute(
        """SELECT COALESCE(AVG(p.overall), 60)
           FROM signings s JOIN players p ON p.id = s.player_id"""
    ).fetchone()[0]
    teams: list[dict[str, int | str | None]] = [
        {"id": club["id"], "name": club["name"], "overall": round(club["overall"])}
        for club in clubs
    ]
    teams.append(
        {"id": None, "name": career["club_name"], "overall": round(squad_overall)}
    )
    if len(teams) % 2:
        teams.append({"id": None, "name": "", "overall": 0})

    season_number = current_season_number(db)
    season_year = SEASON_START.year + season_number - 1
    official_dates = [
        row["played_on"]
        for row in db.execute(
            """SELECT MIN(played_on) AS played_on FROM fixtures
               WHERE season = 2026 AND division = ?
               GROUP BY matchday ORDER BY matchday""",
            (career["division"],),
        ).fetchall()
    ] if season_number == 1 else []
    schedule: list[tuple[int, str, str, str, int | None, int | None, int, int]] = []
    rotating = teams[:]
    for round_number in range(1, len(rotating)):
        played_on = (
            official_dates[round_number - 1]
            if round_number <= len(official_dates)
            else (
                date.fromisoformat(official_dates[-1])
                + timedelta(days=7 * (round_number - len(official_dates)))
            ).isoformat()
            if official_dates
            else date(season_year, 1, 1).isoformat()
            if round_number == 1
            else (
                date(season_year, 1, 1) + timedelta(days=7 * (round_number - 1))
            ).isoformat()
        )
        for pair_index in range(len(rotating) // 2):
            first = rotating[pair_index]
            second = rotating[-pair_index - 1]
            if not first["name"] or not second["name"]:
                continue
            home, away = (
                (second, first)
                if (round_number + pair_index) % 2
                else (first, second)
            )
            schedule.append(
                (
                    round_number,
                    played_on,
                    str(home["name"]),
                    str(away["name"]),
                    home["id"],
                    away["id"],
                    int(home["overall"]),
                    int(away["overall"]),
                )
            )
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]

    db.executemany(
        """INSERT INTO tournament_matches
           (round_number, played_on, home_team, away_team, home_club_id,
            away_club_id, home_overall, away_overall)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        schedule,
    )
    db.execute(
        "INSERT OR IGNORE INTO tournament_progress (id, current_round) VALUES (1, 1)"
    )
    db.commit()


def balance_first_division_clubs(
    db: sqlite3.Connection, career: sqlite3.Row
) -> None:
    target_club_count = FIRST_DIVISION_TEAM_COUNT - int(
        career["division"] == "Primera División"
    )
    first_division_clubs = db.execute(
        """SELECT c.id, c.name, COALESCE(AVG(p.overall), 60) AS overall
           FROM clubs c LEFT JOIN players p ON p.club_id = c.id
           WHERE c.division = 'Primera División' AND c.name != ?
           GROUP BY c.id ORDER BY overall DESC, c.name""",
        (career["club_name"],),
    ).fetchall()
    if len(first_division_clubs) > target_club_count:
        excess_clubs = first_division_clubs[target_club_count:]
        db.executemany(
            """UPDATE clubs SET division = 'Primera Nacional'
               WHERE id = ?""",
            [(club["id"],) for club in excess_clubs],
        )
    elif len(first_division_clubs) < target_club_count:
        missing_count = target_club_count - len(first_division_clubs)
        national_clubs = db.execute(
            """SELECT c.id, c.name, COALESCE(AVG(p.overall), 60) AS overall
               FROM clubs c LEFT JOIN players p ON p.club_id = c.id
               WHERE c.division = 'Primera Nacional' AND c.name != ?
               GROUP BY c.id ORDER BY overall DESC, c.name LIMIT ?""",
            (career["club_name"], missing_count),
        ).fetchall()
        db.executemany(
            """UPDATE clubs SET division = 'Primera División'
               WHERE id = ?""",
            [(club["id"],) for club in national_clubs],
        )


def simulate_goals(
    home_overall: int,
    away_overall: int,
    rng: random.Random | None = None,
) -> tuple[int, int]:
    return _simulate_goals(
        home_overall,
        away_overall,
        rng.gauss if rng is not None else random.gauss,
    )


def _simulate_goals(
    home_overall: int,
    away_overall: int,
    gauss: Callable[[float, float], float],
) -> tuple[int, int]:
    advantage = (home_overall - away_overall) / 18
    home_goals = round(gauss(1.45 + advantage + 0.2, 1.05))
    away_goals = round(gauss(1.45 - advantage, 1.05))
    return max(0, min(6, home_goals)), max(0, min(6, away_goals))


def record_ai_first_division_relegations(
    db: sqlite3.Connection, season_number: int
) -> None:
    clubs = db.execute(
        """SELECT c.id, c.name, COALESCE(AVG(p.overall), 60) AS overall
           FROM clubs c LEFT JOIN players p ON p.club_id = c.id
           WHERE c.division = 'Primera División'
           GROUP BY c.id ORDER BY c.name"""
    ).fetchall()
    if len(clubs) < 2:
        return

    teams: dict[int, dict[str, int | str]] = {
        club["id"]: {
            "name": club["name"],
            "overall": round(club["overall"]),
            "played": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0,
        }
        for club in clubs
    }
    rotating: list[sqlite3.Row | None] = list(clubs)
    if len(rotating) % 2:
        rotating.append(None)
    rng = random.Random(season_number)
    for round_number in range(len(rotating) - 1):
        for pair_index in range(len(rotating) // 2):
            first = rotating[pair_index]
            second = rotating[-pair_index - 1]
            if first is None or second is None:
                continue
            home, away = (
                (second, first)
                if (round_number + pair_index) % 2
                else (first, second)
            )
            home_score, away_score = _simulate_goals(
                round(home["overall"]), round(away["overall"]), rng.gauss
            )
            home_stats = teams[home["id"]]
            away_stats = teams[away["id"]]
            home_stats["played"] = int(home_stats["played"]) + 1
            away_stats["played"] = int(away_stats["played"]) + 1
            home_stats["goals_for"] = int(home_stats["goals_for"]) + home_score
            home_stats["goals_against"] = (
                int(home_stats["goals_against"]) + away_score
            )
            away_stats["goals_for"] = int(away_stats["goals_for"]) + away_score
            away_stats["goals_against"] = (
                int(away_stats["goals_against"]) + home_score
            )
            if home_score > away_score:
                home_stats["points"] = int(home_stats["points"]) + 3
            elif away_score > home_score:
                away_stats["points"] = int(away_stats["points"]) + 3
            else:
                home_stats["points"] = int(home_stats["points"]) + 1
                away_stats["points"] = int(away_stats["points"]) + 1
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]

    relegated = sorted(
        teams.items(),
        key=lambda item: (
            int(item[1]["points"]),
            int(item[1]["goals_for"]) - int(item[1]["goals_against"]),
            int(item[1]["goals_for"]),
            int(item[1]["overall"]),
            str(item[1]["name"]),
        ),
    )[:2]
    db.execute(
        """DELETE FROM tournament_awards
           WHERE award_type LIKE ? AND description = 'Descenso a Primera Nacional'""",
        (f"relegation_{season_number}_club_%",),
    )
    db.executemany(
        """INSERT OR IGNORE INTO tournament_awards
           (award_type, team_name, description)
           VALUES (?, ?, 'Descenso a Primera Nacional')""",
        [
            (
                f"relegation_{season_number}_club_{club_id}",
                str(team["name"]),
            )
            for club_id, team in relegated
        ],
    )


def career_lost_round(db: sqlite3.Connection, round_number: int) -> bool:
    match = db.execute(
        """SELECT home_club_id, away_club_id, home_score, away_score
           FROM tournament_matches
           WHERE round_number = ?
             AND (home_club_id IS NULL OR away_club_id IS NULL)
             AND home_score IS NOT NULL AND away_score IS NOT NULL""",
        (round_number,),
    ).fetchone()
    if match is None:
        return False
    return (
        match["home_club_id"] is None
        and match["home_score"] < match["away_score"]
    ) or (
        match["away_club_id"] is None
        and match["away_score"] < match["home_score"]
    )


def available_season_decisions(
    db: sqlite3.Connection, career: sqlite3.Row, after_round: int, total_rounds: int
) -> list[str]:
    available = [
        "fatigue",
        "stadium",
        "training",
        "player_bonus",
        "travel",
        "media",
        "academy",
        "facilities",
    ]
    standings = calculate_tournament_standings(db, career)
    career_standing = next(team for team in standings if team["is_career"])
    upcoming_match = db.execute(
        """SELECT home_team, away_team, home_club_id, away_club_id
           FROM tournament_matches
           WHERE round_number = ?
             AND (home_club_id IS NULL OR away_club_id IS NULL)""",
        (after_round + 1,),
    ).fetchone()
    if upcoming_match:
        opponent_name = (
            upcoming_match["away_team"]
            if upcoming_match["home_club_id"] is None
            else upcoming_match["home_team"]
        )
        opponent = next(
            (team for team in standings if team["name"] == opponent_name), None
        )
        if opponent and (
            abs(int(career_standing["points"]) - int(opponent["points"])) <= 3
            or abs(int(career_standing["position"]) - int(opponent["position"])) <= 2
        ):
            available.append("rivalry")

    next_home_match = db.execute(
        """SELECT 1 FROM tournament_matches
           WHERE round_number > ? AND home_club_id IS NULL LIMIT 1""",
        (after_round,),
    ).fetchone()
    if next_home_match:
        available.extend(("rain", "ticketing"))

    if career_lost_round(db, after_round):
        available.append("referee")
    if career_lost_round(db, after_round) and career_lost_round(db, after_round - 1):
        available.append("supporters")

    if after_round >= (total_rounds + 1) // 2 and db.execute(
        """SELECT 1 FROM signings s JOIN players p ON p.id = s.player_id
           WHERE p.position = 'MED' LIMIT 1"""
    ).fetchone():
        available.append("transfer_rumor")
    return available


def get_pending_season_decision(
    db: sqlite3.Connection,
    season_number: int,
    round_number: int,
    career: sqlite3.Row | None = None,
) -> sqlite3.Row | None:
    total_rounds = db.execute(
        "SELECT MAX(round_number) FROM tournament_matches"
    ).fetchone()[0]
    if round_number % 2 or not total_rounds or round_number >= total_rounds:
        return None
    unplayed = db.execute(
        """SELECT COUNT(*) FROM tournament_matches
           WHERE round_number = ? AND (home_score IS NULL OR away_score IS NULL)""",
        (round_number,),
    ).fetchone()[0]
    if unplayed:
        return None

    decision = db.execute(
        """SELECT * FROM season_decisions
           WHERE season_number = ? AND after_round = ?""",
        (season_number, round_number),
    ).fetchone()
    if decision is None:
        if career is None:
            career = db.execute("SELECT * FROM career WHERE id = 1").fetchone()
        if career is None:
            raise RuntimeError("No se encontró la carrera para generar un evento.")
        available_events = available_season_decisions(
            db, career, round_number, total_rounds
        )
        recent_events = {
            row["event_key"]
            for row in db.execute(
                """SELECT event_key FROM season_decisions
                   WHERE season_number = ? AND after_round < ?
                   ORDER BY after_round DESC LIMIT 3""",
                (season_number, round_number),
            ).fetchall()
        }
        varied_events = [
            event_key for event_key in available_events
            if event_key not in recent_events
        ]
        if varied_events:
            available_events = varied_events
        event_key = random.choice(available_events)
        db.execute(
            """INSERT INTO season_decisions
               (season_number, after_round, event_key)
               VALUES (?, ?, ?)""",
            (season_number, round_number, event_key),
        )
        decision = db.execute(
            """SELECT * FROM season_decisions
               WHERE season_number = ? AND after_round = ?""",
            (season_number, round_number),
        ).fetchone()
    return decision if decision["choice_key"] is None else None


def round_complete(db: sqlite3.Connection, round_number: int) -> bool:
    matches = db.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN home_score IS NOT NULL AND away_score IS NOT NULL
                           THEN 1 ELSE 0 END) AS completed
           FROM tournament_matches WHERE round_number = ?""",
        (round_number,),
    ).fetchone()
    return bool(matches["total"]) and matches["total"] == matches["completed"]


def apply_season_decision(
    db: sqlite3.Connection,
    career: sqlite3.Row,
    season_number: int,
    after_round: int,
    choice_key: str,
) -> str:
    decision = db.execute(
        """SELECT event_key FROM season_decisions
           WHERE season_number = ? AND after_round = ? AND choice_key IS NULL""",
        (season_number, after_round),
    ).fetchone()
    if decision is None:
        raise ValueError("No hay una decisión pendiente para esta fecha.")

    event_key = decision["event_key"]
    event = SEASON_DECISIONS[event_key]
    option = event["options"].get(choice_key)
    if option is None:
        raise ValueError("La opción elegida no corresponde a esta decisión.")

    outcome: str
    option_effects = option.get("effects")
    if option_effects is not None:
        db.execute(
            """UPDATE career SET
               budget = budget + ?,
               fans = MIN(10000000, MAX(0, fans + ?)),
               popularity = MIN(100, MAX(0, popularity + ?))
               WHERE id = 1""",
            (
                option_effects.get("budget", 0),
                option_effects.get("fans", 0),
                option_effects.get("popularity", 0),
            ),
        )
        outcome = option_effects["outcome"]
    elif choice_key == "play_starters":
        outcome = "Mantuviste a los titulares. "
        if random.random() < 0.4:
            player = db.execute(
                """SELECT p.id, p.name FROM signings s
                   JOIN players p ON p.id = s.player_id
                   WHERE p.id NOT IN (
                       SELECT player_id FROM player_injuries
                       WHERE season_number = ? AND return_round > ?
                   )
                   ORDER BY p.overall DESC, p.name LIMIT 1""",
                (season_number, after_round),
            ).fetchone()
            if player:
                db.execute(
                    """INSERT OR REPLACE INTO player_injuries
                       (season_number, player_id, return_round)
                       VALUES (?, ?, ?)""",
                    (season_number, player["id"], after_round + 3),
                )
                outcome += (
                    f"{player['name']} sufrió una lesión y se perderá "
                    "las próximas dos fechas."
                )
            else:
                outcome += "El plantel no sufrió lesiones."
        else:
            outcome += "El plantel no sufrió lesiones."
    elif choice_key == "criticize_referee":
        db.execute(
            "UPDATE career SET fans = MIN(10000000, fans + 150) WHERE id = 1"
        )
        outcome = "La hinchada respaldó tu reclamo; aumenta el riesgo de fallos adversos."
    elif choice_key == "diplomatic":
        db.execute("UPDATE career SET fans = MAX(0, fans - 50) WHERE id = 1")
        outcome = "Mantuviste la calma institucional; bajó levemente el apoyo popular."
    elif choice_key == "untouchable":
        player = db.execute(
            """SELECT p.id, p.name FROM signings s
               JOIN players p ON p.id = s.player_id
               WHERE p.position = 'MED'
               ORDER BY p.overall DESC, p.name LIMIT 1"""
        ).fetchone()
        if player:
            db.execute(
                "UPDATE players SET market_value = CAST(market_value * 1.15 AS INTEGER) WHERE id = ?",
                (player["id"],),
            )
            outcome = f"{player['name']} fue declarado intransferible y aumentó su valor."
        else:
            outcome = "No tenés un mediocampista disponible para declarar intransferible."
    elif choice_key == "hear_offers":
        db.execute("UPDATE career SET budget = budget + 500000 WHERE id = 1")
        outcome = "Escuchaste ofertas y el club recibió $500.000; el equipo puede perder concentración."
    elif choice_key == "repair_pitch":
        db.execute("UPDATE career SET budget = budget - 8000 WHERE id = 1")
        outcome = "Invertiste $8.000 en el drenaje y protegiste la localía."
    elif choice_key == "save_money":
        outcome = "Ahorraste el gasto; el próximo partido de local puede tener menos público y más empates."
    elif choice_key == "upgrade_stadium":
        db.execute(
            "UPDATE career SET budget = budget - 1000000, fans = MIN(10000000, fans + 500) WHERE id = 1"
        )
        outcome = "Mejoraste el estadio: invertiste $1.000.000 y sumaste 500 hinchas."
    elif choice_key == "meet_supporters":
        db.execute(
            "UPDATE career SET fans = MIN(10000000, fans + 250) WHERE id = 1"
        )
        outcome = "La reunión recuperó apoyo; el plantel puede sentir algo de tensión."
    elif choice_key == "hire_security":
        db.execute(
            "UPDATE career SET budget = budget - 300000, fans = MAX(0, fans - 100) WHERE id = 1"
        )
        outcome = "Contrataste seguridad por $300.000 y protegiste la tranquilidad del plantel."
    elif choice_key in {
        "rotate",
        "defensive",
        "offensive",
        "postpone_stadium",
    }:
        outcome = {
            "rotate": "Rotaste el plantel; recupera energía, aunque baja algo el rendimiento inmediato.",
            "defensive": "Elegiste un planteo defensivo para buscar un empate.",
            "offensive": "El equipo saldrá a buscar los tres puntos con más riesgo.",
            "postpone_stadium": "Postergaste la obra para priorizar el presupuesto.",
        }[choice_key]
    else:
        raise ValueError("La opción elegida todavía no tiene un efecto configurado.")

    db.execute(
        """UPDATE season_decisions SET choice_key = ?, outcome = ?
           WHERE season_number = ? AND after_round = ?""",
        (choice_key, outcome, season_number, after_round),
    )
    return outcome


def active_decision_effects(
    db: sqlite3.Connection, season_number: int, round_number: int
) -> list[sqlite3.Row]:
    return db.execute(
        """SELECT event_key, choice_key, after_round
           FROM season_decisions
           WHERE season_number = ? AND choice_key IS NOT NULL
             AND after_round < ?""",
        (season_number, round_number),
    ).fetchall()


def generate_match_events(
    db: sqlite3.Connection,
    match: sqlite3.Row,
    home_score: int,
    away_score: int,
) -> list[dict[str, str | int | None]]:
    teams = (
        ("home", match["home_team"], match["home_club_id"], home_score),
        ("away", match["away_team"], match["away_club_id"], away_score),
    )
    lineups: dict[str, list[sqlite3.Row | dict[str, object]]] = {}
    for side, team_name, club_id, _ in teams:
        if club_id is None:
            player_rows = db.execute(
                """SELECT p.id, p.name FROM signings s
                   JOIN players p ON p.id = s.player_id
                   ORDER BY p.overall DESC, p.name LIMIT 11"""
            ).fetchall()
        else:
            player_rows = db.execute(
                """SELECT id, name FROM players WHERE club_id = ?
                   ORDER BY overall DESC, name LIMIT 11""",
                (club_id,),
            ).fetchall()
        lineups[side] = player_rows or [
            {"id": None, "name": f"Jugador de {team_name}"}
        ]

    events: list[dict[str, str | int | None]] = []
    for side, team_name, _club_id, goals in teams:
        for _ in range(goals):
            player = random.choice(lineups[side])
            assist_candidates = [
                candidate
                for candidate in lineups[side]
                if candidate["id"] is not None
                and candidate["id"] != player["id"]
            ]
            assistant = random.choice(assist_candidates) if assist_candidates else None
            events.append(
                {
                    "minute": random.randint(1, 90),
                    "type": "goal",
                    "side": side,
                    "team": team_name,
                    "player": player["name"],
                    "player_id": player["id"],
                    "assist": assistant["name"] if assistant else None,
                    "assist_player_id": assistant["id"] if assistant else None,
                }
            )

    cards: list[tuple[str, str]] = []
    for side, team_name, _club_id, _goals in teams:
        cards.extend((side, team_name) for _ in range(random.randint(1, 3)))
        if random.random() < 0.08:
            cards.append((side, team_name))
    for side, team_name in cards:
        red_card = random.random() < 0.035
        player = random.choice(lineups[side])
        events.append(
            {
                "minute": random.randint(5, 90),
                "type": "red" if red_card else "yellow",
                "side": side,
                "team": team_name,
                "player": player["name"],
                "player_id": player["id"],
            }
        )

    return sorted(events, key=lambda event: int(event["minute"]))


def record_player_match_stats(
    db: sqlite3.Connection,
    season_number: int,
    match: sqlite3.Row,
    events: list[dict[str, str | int | None]],
    competition: str = "league",
    division: str | None = None,
) -> None:
    event_counts: dict[int, dict[str, int]] = {}
    for event in events:
        player_id = event.get("player_id")
        if not isinstance(player_id, int):
            continue
        counts = event_counts.setdefault(
            player_id,
            {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0},
        )
        if event["type"] == "goal":
            counts["goals"] += 1
            assist_player_id = event.get("assist_player_id")
            if isinstance(assist_player_id, int) and assist_player_id != player_id:
                event_counts.setdefault(
                    assist_player_id,
                    {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0},
                )["assists"] += 1
        elif event["type"] == "yellow":
            counts["yellow_cards"] += 1
        elif event["type"] == "red":
            counts["red_cards"] += 1

    player_ids: set[int] = set()
    player_teams: dict[int, tuple[int | None, str, str | None]] = {}
    career = get_career()
    for club_id in (match["home_club_id"], match["away_club_id"]):
        side = "home" if club_id == match["home_club_id"] else "away"
        team_name = str(match[f"{side}_team"])
        team_division = division
        if club_id is not None:
            club = db.execute(
                "SELECT division FROM clubs WHERE id = ?", (club_id,)
            ).fetchone()
            team_division = (
                str(club["division"])
                if club is not None
                else team_division
            )
        elif team_division is None and career is not None:
            team_division = str(career["division"])
        if club_id is None:
            player_rows = db.execute(
                """SELECT p.id FROM signings s
                   JOIN players p ON p.id = s.player_id
                   ORDER BY p.overall DESC, p.name LIMIT 11"""
            ).fetchall()
        else:
            player_rows = db.execute(
                """SELECT id FROM players WHERE club_id = ?
                   ORDER BY overall DESC, name LIMIT 11""",
                (club_id,),
            ).fetchall()
        for row in player_rows:
            player_id = int(row["id"])
            player_ids.add(player_id)
            player_teams[player_id] = (club_id, team_name, team_division)

    for player_id in player_ids:
        counts = event_counts.get(
            player_id,
            {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0},
        )
        club_id, team_name, team_division = player_teams[player_id]
        db.execute(
            """INSERT OR REPLACE INTO player_match_stats
               (season_number, competition, match_id, player_id, goals, assists,
                yellow_cards, red_cards, club_id, team_name, division)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                season_number,
                competition,
                match["id"],
                player_id,
                counts["goals"],
                counts["assists"],
                counts["yellow_cards"],
                counts["red_cards"],
                club_id,
                team_name,
                team_division,
            ),
        )


def get_league_leaders(
    db: sqlite3.Connection, career: sqlite3.Row, season_number: int
) -> tuple[list[dict[str, int | str]], list[dict[str, int | str]]]:
    rows = db.execute(
        """SELECT p.id, p.name, p.position,
                  COALESCE(
                      MAX(NULLIF(stats.team_name, '')),
                      CASE WHEN EXISTS (
                          SELECT 1 FROM signings squad
                          WHERE squad.player_id = p.id
                      ) THEN ? ELSE club.name END
                  ) AS team_name,
                  SUM(stats.goals) AS goals,
                  SUM(stats.assists) AS assists
           FROM player_match_stats stats
           JOIN players p ON p.id = stats.player_id
           LEFT JOIN clubs club ON club.id = COALESCE(stats.club_id, p.club_id)
           WHERE stats.season_number = ? AND stats.competition = 'league'
             AND COALESCE(
                 NULLIF(stats.division, ''),
                 CASE WHEN EXISTS (
                     SELECT 1 FROM signings squad
                     WHERE squad.player_id = p.id
                 ) THEN ? ELSE club.division END
             ) = ?
           GROUP BY p.id, p.name, p.position, club.name
           HAVING SUM(stats.goals) > 0 OR SUM(stats.assists) > 0""",
        (
            career["club_name"],
            season_number,
            career["division"],
            career["division"],
        ),
    ).fetchall()
    leaders = [dict(row) for row in rows]
    scorers = sorted(
        (row for row in leaders if int(row["goals"]) > 0),
        key=lambda row: (-int(row["goals"]), str(row["name"]).casefold()),
    )[:5]
    assisters = sorted(
        (row for row in leaders if int(row["assists"]) > 0),
        key=lambda row: (-int(row["assists"]), str(row["name"]).casefold()),
    )[:5]
    return scorers, assisters


def get_season_individual_awards(
    db: sqlite3.Connection, career: sqlite3.Row, season_number: int
) -> list[dict[str, str]]:
    players = db.execute(
        """SELECT p.id, p.name, p.position, p.age, p.overall,
                  COALESCE(
                      MAX(NULLIF(stats.team_name, '')),
                      CASE WHEN EXISTS (
                          SELECT 1 FROM signings squad
                          WHERE squad.player_id = p.id
                      ) THEN ? ELSE club.name END
                  ) AS team_name,
                  COUNT(*) AS appearances,
                  SUM(stats.goals) AS goals,
                  SUM(stats.assists) AS assists,
                  SUM(stats.yellow_cards) AS yellow_cards,
                  SUM(stats.red_cards) AS red_cards,
                  SUM(
                      CASE
                          WHEN stats.club_id IS NULL AND match.home_club_id IS NULL
                              THEN match.away_score
                          WHEN stats.club_id IS NULL
                              THEN match.home_score
                          WHEN match.home_club_id = stats.club_id
                              THEN match.away_score
                          ELSE match.home_score
                      END
                  ) AS goals_conceded
           FROM player_match_stats stats
           JOIN players p ON p.id = stats.player_id
           JOIN tournament_matches match ON match.id = stats.match_id
           LEFT JOIN clubs club ON club.id = COALESCE(stats.club_id, p.club_id)
           WHERE stats.season_number = ? AND stats.competition = 'league'
             AND COALESCE(
                 NULLIF(stats.division, ''),
                 CASE WHEN EXISTS (
                     SELECT 1 FROM signings squad
                     WHERE squad.player_id = p.id
                 ) THEN ? ELSE club.division END
             ) = ?
           GROUP BY p.id, p.name, p.position, p.age, p.overall, club.name""",
        (
            career["club_name"],
            season_number,
            career["division"],
            career["division"],
        ),
    ).fetchall()
    candidates = [dict(player) for player in players]
    for player in candidates:
        player["performance"] = (
            int(player["goals"]) * 4
            + int(player["assists"]) * 3
            + int(player["appearances"])
            - int(player["yellow_cards"])
            - int(player["red_cards"]) * 3
        )

    def best_outfield(
        candidates_for_award: list[dict[str, object]],
    ) -> dict[str, object] | None:
        return min(
            candidates_for_award,
            key=lambda player: (
                -int(player["performance"]),
                -int(player["overall"]),
                -int(player["appearances"]),
                str(player["name"]).casefold(),
            ),
            default=None,
        )

    goalkeepers = [
        player
        for player in candidates
        if player_position_group(str(player["position"])) == "ARQ"
    ]
    young_players = [
        player
        for player in candidates
        if player["age"] is not None and int(player["age"]) <= 21
    ]
    young_goalkeepers = [
        player for player in goalkeepers if player["age"] is not None and int(player["age"]) <= 21
    ]
    award_winners = [
        (
            "Mejor jugador del año",
            best_outfield(candidates),
        ),
        (
            "Mejor arquero",
            min(
                goalkeepers,
                key=lambda player: (
                    int(player["goals_conceded"]) / int(player["appearances"]),
                    -int(player["appearances"]),
                    -int(player["overall"]),
                    str(player["name"]).casefold(),
                ),
                default=None,
            ),
        ),
        (
            "Mejor jugador joven · Sub-21",
            best_outfield(young_players),
        ),
        (
            "Mejor arquero joven · Sub-21",
            min(
                young_goalkeepers,
                key=lambda player: (
                    int(player["goals_conceded"]) / int(player["appearances"]),
                    -int(player["appearances"]),
                    -int(player["overall"]),
                    str(player["name"]).casefold(),
                ),
                default=None,
            ),
        ),
    ]
    return [
        {
            "title": title,
            "name": str(player["name"]) if player else "Sin candidato",
            "team_name": str(player["team_name"] or "—") if player else "—",
        }
        for title, player in award_winners
    ]


def apply_season_player_development(
    db: sqlite3.Connection, season_number: int
) -> int:
    applied = db.execute(
        """INSERT OR IGNORE INTO player_development_runs (season_number)
           VALUES (?)""",
        (season_number,),
    )
    if not applied.rowcount:
        return 0

    performances = db.execute(
        """SELECT player_id, COUNT(*) AS appearances, SUM(goals) AS goals,
                  SUM(yellow_cards) AS yellow_cards, SUM(red_cards) AS red_cards
           FROM player_match_stats
           WHERE season_number = ?
           GROUP BY player_id""",
        (season_number,),
    ).fetchall()
    changed = 0
    for performance in performances:
        appearances = int(performance["appearances"])
        goals = int(performance["goals"])
        yellow_cards = int(performance["yellow_cards"])
        red_cards = int(performance["red_cards"])
        score = appearances + goals * 2 - yellow_cards - red_cards * 3
        improvement = 0
        if appearances >= 5 and score >= appearances + 8:
            improvement = 2
        elif appearances >= 5 and score >= appearances + 2:
            improvement = 1
        elif appearances >= 10 and score <= appearances - 8:
            improvement = -1
        if improvement:
            cursor = db.execute(
                """UPDATE players SET overall = MIN(99, MAX(1, overall + ?))
                   WHERE id = ? AND overall != MIN(99, MAX(1, overall + ?))""",
                (improvement, performance["player_id"], improvement),
            )
            changed += cursor.rowcount
    return changed


def simulate_tournament_round(
    db: sqlite3.Connection,
    career: sqlite3.Row,
    season_number: int,
    round_number: int,
) -> None:
    matches = db.execute(
        """SELECT * FROM tournament_matches WHERE round_number = ?
           ORDER BY id""",
        (round_number,),
    ).fetchall()
    if not matches:
        raise ValueError("No se encontró la fecha actual del torneo.")
    if all(
        match["home_score"] is not None and match["away_score"] is not None
        for match in matches
    ):
        return

    effects = active_decision_effects(db, season_number, round_number)
    for match in matches:
        if match["home_score"] is not None and match["away_score"] is not None:
            continue
        home_overall = int(match["home_overall"])
        away_overall = int(match["away_overall"])
        user_is_home = match["home_club_id"] is None
        user_is_away = match["away_club_id"] is None
        force_draw_chance = 0.0
        extra_volatility = False

        if user_is_home or user_is_away:
            performance_modifier = 0
            for effect in effects:
                rounds_after_decision = round_number - int(effect["after_round"])
                event = SEASON_DECISIONS[effect["event_key"]]
                option_effects = event["options"][effect["choice_key"]].get(
                    "effects", {}
                )
                performance_rounds = option_effects.get(
                    "performance_rounds", 0
                )
                if 1 <= rounds_after_decision <= performance_rounds:
                    performance_modifier += option_effects.get(
                        "performance_modifier", 0
                    )
                if effect["event_key"] == "fatigue":
                    if effect["choice_key"] == "rotate" and rounds_after_decision == 1:
                        performance_modifier -= 3
                    elif effect["choice_key"] == "rotate" and rounds_after_decision == 2:
                        performance_modifier += 1
                elif effect["event_key"] == "rivalry":
                    if rounds_after_decision == 1:
                        if effect["choice_key"] == "defensive":
                            force_draw_chance = max(force_draw_chance, 0.65)
                        elif effect["choice_key"] == "offensive":
                            extra_volatility = True
                elif effect["event_key"] == "referee":
                    if (
                        effect["choice_key"] == "criticize_referee"
                        and rounds_after_decision <= 2
                        and random.random() < 0.2
                    ):
                        performance_modifier -= 2
                elif effect["event_key"] == "transfer_rumor":
                    if rounds_after_decision <= 2:
                        performance_modifier -= (
                            1 if effect["choice_key"] == "untouchable" else 3
                        )
                elif effect["event_key"] == "rain" and effect["choice_key"] == "save_money":
                    home_match = db.execute(
                        """SELECT MIN(round_number) FROM tournament_matches
                           WHERE round_number > ? AND home_club_id IS NULL""",
                        (effect["after_round"],),
                    ).fetchone()[0]
                    if user_is_home and round_number == home_match:
                        force_draw_chance = max(force_draw_chance, 0.4)
                        db.execute(
                            "UPDATE career SET budget = budget - 50000 WHERE id = 1"
                        )
                elif effect["event_key"] == "supporters" and rounds_after_decision == 1:
                    if effect["choice_key"] == "meet_supporters":
                        performance_modifier -= 2

            injured_count = db.execute(
                """SELECT COUNT(*) FROM player_injuries
                   WHERE season_number = ? AND return_round > ?""",
                (season_number, round_number),
            ).fetchone()[0]
            performance_modifier -= min(injured_count * 2, 6)
            if user_is_home:
                home_overall = max(1, home_overall + performance_modifier)
            else:
                away_overall = max(1, away_overall + performance_modifier)

        if force_draw_chance and random.random() < force_draw_chance:
            draw_goals = random.randint(0, 2)
            home_score, away_score = draw_goals, draw_goals
        else:
            home_score, away_score = simulate_goals(home_overall, away_overall)
            if extra_volatility and random.random() < 0.5:
                if random.random() < 0.5:
                    home_score = min(6, home_score + 1)
                else:
                    away_score = min(6, away_score + 1)
        if user_is_home or user_is_away:
            for effect in effects:
                if (
                    effect["event_key"] == "rivalry"
                    and effect["choice_key"] == "defensive"
                    and round_number - int(effect["after_round"]) == 1
                ):
                    career_score = home_score if user_is_home else away_score
                    opponent_score = away_score if user_is_home else home_score
                    if career_score <= opponent_score:
                        db.execute(
                            "UPDATE career SET fans = MAX(0, fans - 100) WHERE id = 1"
                        )
        events = generate_match_events(db, match, home_score, away_score)
        record_player_match_stats(
            db, season_number, match, events, division=str(career["division"])
        )
        db.execute(
            """UPDATE tournament_matches
               SET home_score = ?, away_score = ?, match_events = ?
               WHERE id = ?""",
            (home_score, away_score, json.dumps(events, ensure_ascii=False), match["id"]),
        )


def continue_auto_simulation(
    db: sqlite3.Connection, career: sqlite3.Row
) -> str:
    season_number = current_season_number(db)
    total_rounds = db.execute(
        "SELECT MAX(round_number) FROM tournament_matches"
    ).fetchone()[0]
    if not total_rounds:
        raise ValueError("No hay fechas cargadas para simular.")

    while True:
        active_round = db.execute(
            "SELECT current_round FROM tournament_progress WHERE id = 1"
        ).fetchone()[0]
        pending = get_pending_season_decision(db, season_number, active_round)
        if pending:
            return "decision"

        if round_complete(db, active_round):
            if active_round >= total_rounds:
                standings = calculate_tournament_standings(db, career)
                setup_league_outcome(db, career, standings)
                finish_copa_argentina_automatically(db, career)
                db.execute(
                    "UPDATE tournament_progress SET auto_simulation = 0 WHERE id = 1"
                )
                return "complete"
            active_round += 1
            db.execute(
                "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
                (active_round,),
            )

        simulate_tournament_round(db, career, season_number, active_round)
        copa_progress = db.execute(
            """SELECT season_number, current_round, is_complete
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if (
            copa_progress
            and int(copa_progress["season_number"]) == season_number
            and not copa_progress["is_complete"]
            and active_round
            == copa_argentina_league_matchday(
                db,
                season_number,
                int(copa_progress["current_round"]),
                total_rounds,
            )
        ):
            simulate_copa_argentina_round_automatically(db, career)
        if active_round >= total_rounds:
            standings = calculate_tournament_standings(db, career)
            setup_league_outcome(db, career, standings)
            finish_copa_argentina_automatically(db, career)
            db.execute(
                "UPDATE tournament_progress SET auto_simulation = 0 WHERE id = 1"
            )
            return "complete"
        if get_pending_season_decision(db, season_number, active_round):
            return "decision"

        db.execute(
            "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
            (active_round + 1,),
        )


def calculate_tournament_standings(
    db: sqlite3.Connection, career: sqlite3.Row
) -> list[dict[str, int | str | bool | None]]:
    teams: dict[int | str, dict[str, int | str | bool]] = {
        club["id"]: {
            "name": club["name"],
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
            "is_career": False,
            "logo": club["logo"],
        }
        for club in db.execute(
            """SELECT id, name, logo
               FROM clubs
               WHERE division = ? AND name != ?""",
            (career["division"], career["club_name"]),
        ).fetchall()
    }
    teams["career"] = {
        "name": career["club_name"],
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "points": 0,
        "is_career": True,
        "logo": "/escudo-club.svg",
    }
    season_number = current_season_number(db)
    if season_number > 1:
        incoming_division = career["division"]
        for movement in get_season_movements(db, season_number - 1):
            is_incoming = (
                movement["description"].startswith("Ascenso")
                and incoming_division == "Primera División"
            ) or (
                movement["description"].startswith("Descenso")
                and incoming_division == "Primera Nacional"
            )
            if not is_incoming:
                continue
            club = db.execute(
                """SELECT id, name, logo
                   FROM clubs WHERE name = ?""",
                (movement["team_name"],),
            ).fetchone()
            if club is None or club["id"] in teams:
                continue
            teams[club["id"]] = {
                "name": club["name"],
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "points": 0,
                "is_career": False,
                "logo": club["logo"],
            }
    played_matches = db.execute(
        """SELECT home_club_id, away_club_id, home_score, away_score
           FROM tournament_matches WHERE home_score IS NOT NULL AND away_score IS NOT NULL"""
    ).fetchall()
    for match in played_matches:
        home_key = match["home_club_id"] if match["home_club_id"] is not None else "career"
        away_key = match["away_club_id"] if match["away_club_id"] is not None else "career"
        home = teams[home_key]
        away = teams[away_key]
        home["played"] = int(home["played"]) + 1
        away["played"] = int(away["played"]) + 1
        home["goals_for"] = int(home["goals_for"]) + match["home_score"]
        home["goals_against"] = int(home["goals_against"]) + match["away_score"]
        away["goals_for"] = int(away["goals_for"]) + match["away_score"]
        away["goals_against"] = int(away["goals_against"]) + match["home_score"]
        if match["home_score"] > match["away_score"]:
            home["wins"] = int(home["wins"]) + 1
            home["points"] = int(home["points"]) + 3
            away["losses"] = int(away["losses"]) + 1
        elif match["home_score"] < match["away_score"]:
            away["wins"] = int(away["wins"]) + 1
            away["points"] = int(away["points"]) + 3
            home["losses"] = int(home["losses"]) + 1
        else:
            home["draws"] = int(home["draws"]) + 1
            away["draws"] = int(away["draws"]) + 1
            home["points"] = int(home["points"]) + 1
            away["points"] = int(away["points"]) + 1
    ordered_teams = sorted(
        teams.values(),
        key=lambda team: (
            int(team["played"]) == 0,
            -int(team["points"]),
            -(int(team["goals_for"]) - int(team["goals_against"])),
            -int(team["goals_for"]),
            str(team["name"]).casefold(),
        ),
    )
    return [
        {
            **team,
            "position": position,
            "goal_difference": int(team["goals_for"]) - int(team["goals_against"]),
        }
        for position, team in enumerate(ordered_teams, start=1)
    ]


def setup_league_outcome(
    db: sqlite3.Connection,
    career: sqlite3.Row,
    standings: list[dict[str, int | str | bool]],
) -> None:
    participating_teams = [
        team for team in standings if int(team["played"]) > 0
    ]
    if not participating_teams:
        return
    season_number = current_season_number(db)
    champion = participating_teams[0]
    db.execute(
        """INSERT OR IGNORE INTO tournament_awards (award_type, team_name, description)
           VALUES (?, ?, 'Campeón de la liga')""",
        (f"champion_{season_number}", champion["name"]),
    )
    if career["division"] == "Primera Nacional":
        career_position = next(
            (int(team["position"]) for team in participating_teams if team["is_career"]),
            None,
        )
        if career_position is not None:
            prize_award = db.execute(
                """INSERT OR IGNORE INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES (?, ?, 'Premio por puesto en Primera Nacional')""",
                (f"league_prize_{season_number}", career["club_name"]),
            )
            prize = first_national_prize(
                career_position, len(participating_teams)
            )
            if prize_award.rowcount and prize:
                db.execute(
                    "UPDATE career SET budget = budget + ? WHERE id = 1",
                    (prize,),
                )
        champion_club_id = None
        if not champion["is_career"]:
            champion_club_id = db.execute(
                "SELECT id FROM clubs WHERE name = ?",
                (champion["name"],),
            ).fetchone()["id"]
        db.execute(
            """INSERT OR IGNORE INTO tournament_awards (award_type, team_name, description)
               VALUES (?, ?, 'Ascenso directo a Primera División')""",
            (
                f"promotion_{season_number}"
                if champion["is_career"]
                else f"promotion_{season_number}_club_{champion_club_id}",
                champion["name"],
            ),
        )
    elif career["division"] == "Primera División":
        career_position = next(
            (int(team["position"]) for team in standings if team["is_career"]),
            None,
        )
        if (
            career_position is not None
            and career_position <= FIRST_DIVISION_TEAM_COUNT - 1
        ):
            prize_award = db.execute(
                """INSERT OR IGNORE INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES (?, ?, 'Premio por puesto en Primera División')""",
                (f"league_prize_{season_number}", career["club_name"]),
            )
            prize = first_division_prize(career_position)
            if prize_award.rowcount and prize:
                db.execute(
                    "UPDATE career SET budget = budget + ? WHERE id = 1",
                    (prize,),
                )
        relegated_teams = sorted(
            (team for team in participating_teams if int(team["played"]) > 0),
            key=lambda team: int(team["position"]),
            reverse=True,
        )[:2]
        for team in relegated_teams:
            club_id = None
            if not team["is_career"]:
                club = db.execute(
                    "SELECT id FROM clubs WHERE name = ?",
                    (team["name"],),
                ).fetchone()
                if club is None:
                    continue
                club_id = club["id"]
            db.execute(
                """INSERT OR IGNORE INTO tournament_awards
                   (award_type, team_name, description)
                   VALUES (?, ?, 'Descenso a Primera Nacional')""",
                (
                    f"relegation_{season_number}"
                    if team["is_career"]
                    else f"relegation_{season_number}_club_{club_id}",
                    team["name"],
                ),
            )

    if career["division"] == "Primera Nacional":
        record_ai_first_division_relegations(db, season_number)

    if career["division"] != "Primera Nacional":
        if career["division"] == "Primera División":
            ensure_two_division_movements(db, season_number)
        db.commit()
        return
    qualified = [
        team for team in standings
        if 2 <= int(team["position"]) <= 9
    ]
    if len(qualified) != 8:
        db.commit()
        return
    if db.execute("SELECT 1 FROM promotion_playoff_matches LIMIT 1").fetchone():
        db.commit()
        return

    participants = {
        int(team["position"]): {
            "name": str(team["name"]),
            "club_id": None if team["is_career"] else db.execute(
                "SELECT id FROM clubs WHERE name = ?",
                (team["name"],),
            ).fetchone()["id"],
            "overall": round(
                db.execute(
                    """SELECT COALESCE(AVG(p.overall), 60)
                       FROM signings s JOIN players p ON p.id = s.player_id"""
                ).fetchone()[0]
            ) if team["is_career"] else round(
                db.execute(
                    """SELECT COALESCE(AVG(overall), 60) FROM players
                       WHERE club_id = (SELECT id FROM clubs WHERE name = ?)""",
                    (team["name"],),
                ).fetchone()[0]
            ),
        }
        for team in qualified
    }
    if len(participants) != 8:
        db.commit()
        return

    pairings = ((2, 9), (3, 8), (4, 7), (5, 6))
    for match_number, (home_seed, away_seed) in enumerate(pairings, start=1):
        home = participants[home_seed]
        away = participants[away_seed]
        db.execute(
            """INSERT INTO promotion_playoff_matches
               (stage, match_number, home_seed, away_seed, home_team, away_team,
                home_club_id, away_club_id, home_overall, away_overall)
               VALUES ('quarterfinal', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match_number, home_seed, away_seed, home["name"], away["name"],
                home["club_id"], away["club_id"], home["overall"], away["overall"],
            ),
        )
    db.execute(
        """INSERT OR IGNORE INTO promotion_playoff_progress (id, current_stage)
           VALUES (1, 'quarterfinal')"""
    )
    db.commit()


def season_is_complete(db: sqlite3.Connection) -> bool:
    progress = db.execute(
        "SELECT current_round FROM tournament_progress WHERE id = 1"
    ).fetchone()
    if not progress:
        return False
    total_rounds = db.execute(
        "SELECT MAX(round_number) FROM tournament_matches"
    ).fetchone()[0]
    if not total_rounds or progress["current_round"] != total_rounds:
        return False
    unplayed = db.execute(
        """SELECT COUNT(*) FROM tournament_matches
           WHERE home_score IS NULL OR away_score IS NULL"""
    ).fetchone()[0]
    if unplayed:
        return False
    playoff = db.execute(
        "SELECT current_stage FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    return playoff is None or playoff["current_stage"] == "complete"


def start_next_season(db: sqlite3.Connection) -> tuple[int, int]:
    if not season_is_complete(db):
        raise ValueError("Terminá la liga y el playoff antes de iniciar otra temporada.")

    career = db.execute("SELECT * FROM career WHERE id = 1").fetchone()
    previous_season = current_season_number(db)
    if previous_season > 1:
        ensure_two_division_movements(db, previous_season - 1)
    ensure_two_division_movements(db, previous_season)
    apply_season_player_development(db, previous_season)
    next_season = previous_season + 1
    expired_loans = [
        row["player_id"]
        for row in db.execute(
            """SELECT player_id FROM signings
               WHERE loan_season_number IS NOT NULL
                 AND loan_season_number <= ?""",
            (previous_season,),
        ).fetchall()
    ]
    if expired_loans:
        db.executemany(
            "DELETE FROM squad_lineup WHERE player_id = ?",
            [(player_id,) for player_id in expired_loans],
        )
        db.execute(
            """DELETE FROM signings
               WHERE loan_season_number IS NOT NULL
                 AND loan_season_number <= ?""",
            (previous_season,),
        )
    next_squad_limit = MAX_SQUAD_SIZE
    promoted = db.execute(
        """SELECT 1 FROM tournament_awards
           WHERE award_type IN (?, ?) AND team_name = ? LIMIT 1""",
        (
            f"promotion_{previous_season}",
            f"playoff_promotion_{previous_season}",
            career["club_name"],
        ),
    ).fetchone()
    relegated = db.execute(
        """SELECT 1 FROM tournament_awards
           WHERE award_type = ? AND team_name = ? LIMIT 1""",
        (f"relegation_{previous_season}", career["club_name"]),
    ).fetchone()
    if promoted:
        next_division = "Primera División"
    elif relegated:
        next_division = "Primera Nacional"
    else:
        next_division = career["division"]

    seasons_to_apply = [previous_season]
    if previous_season > 1:
        seasons_to_apply.insert(0, previous_season - 1)
    for season in seasons_to_apply:
        for team in get_season_movements(db, season):
            if team["description"].startswith("Ascenso"):
                db.execute(
                    """UPDATE clubs SET division = 'Primera División'
                       WHERE name = ? AND division = 'Primera Nacional'""",
                    (team["team_name"],),
                )
            elif team["description"].startswith("Descenso"):
                db.execute(
                    """UPDATE clubs SET division = 'Primera Nacional'
                       WHERE name = ? AND division = 'Primera División'""",
                    (team["team_name"],),
                )
    next_start = date(SEASON_START.year + next_season - 1, 1, 1).isoformat()

    db.execute("DELETE FROM promotion_playoff_matches")
    db.execute("DELETE FROM promotion_playoff_progress")
    db.execute("DELETE FROM copa_argentina_matches")
    db.execute("DELETE FROM copa_argentina_progress")
    db.execute("DELETE FROM tournament_matches")
    db.execute(
        """UPDATE tournament_progress SET current_round = 1,
           current_season = ?, signing_limit = ?, auto_simulation = 0
           WHERE id = 1""",
        (next_season, next_squad_limit),
    )
    db.execute(
        """UPDATE career SET division = ?, phase = 'market', season_start = ?
           WHERE id = 1""",
        (next_division, next_start),
    )
    db.commit()
    return next_season, next_squad_limit


def simulate_promotion_playoff_stage(
    db: sqlite3.Connection, career: sqlite3.Row
) -> str:
    stage = db.execute(
        "SELECT current_stage FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    if stage is None or stage["current_stage"] == "complete":
        return "complete"
    current_stage = stage["current_stage"]
    matches = db.execute(
        """SELECT * FROM promotion_playoff_matches
           WHERE stage = ? ORDER BY match_number""",
        (current_stage,),
    ).fetchall()
    if not matches:
        raise RuntimeError(f"No hay partidos cargados para la etapa {current_stage}.")
    if any(match["winner_team"] is not None for match in matches):
        raise ValueError(f"La etapa {current_stage} ya fue disputada.")

    for match in matches:
        user_match = (
            match["home_club_id"] is None or match["away_club_id"] is None
        )
        if user_match:
            home_score, away_score = simulate_goals(
                match["home_overall"], match["away_overall"]
            )
            events = generate_match_events(db, match, home_score, away_score)
            record_player_match_stats(
                db,
                current_season_number(db),
                match,
                events,
                competition="playoff",
            )
            winner_values = (None, None, None, None)
            if home_score != away_score:
                home_wins = home_score > away_score
                winner_values = (
                    match["home_seed"] if home_wins else match["away_seed"],
                    match["home_team"] if home_wins else match["away_team"],
                    match["home_club_id"] if home_wins else match["away_club_id"],
                    match["home_overall"] if home_wins else match["away_overall"],
                )
            db.execute(
                """UPDATE promotion_playoff_matches
                   SET home_score = ?, away_score = ?, home_penalties = NULL,
                       away_penalties = NULL, shootout_state = '{"kicks": []}',
                       playoff_events = ?, winner_seed = ?, winner_team = ?,
                       winner_club_id = ?, winner_overall = ?
                   WHERE id = ?""",
                (
                    home_score,
                    away_score,
                    json.dumps(events, ensure_ascii=False),
                    *winner_values,
                    match["id"],
                ),
            )
            continue

        home_score, away_score = simulate_goals(
            match["home_overall"], match["away_overall"]
        )
        home_penalties = None
        away_penalties = None
        home_wins = home_score > away_score
        if home_score == away_score:
            home_penalties = random.randint(3, 5)
            away_penalties = random.randint(3, 5)
            while home_penalties == away_penalties:
                if random.choice((True, False)):
                    home_penalties += 1
                else:
                    away_penalties += 1
            home_wins = home_penalties > away_penalties
        winner_seed = match["home_seed"] if home_wins else match["away_seed"]
        winner_team = match["home_team"] if home_wins else match["away_team"]
        winner_club_id = match["home_club_id"] if home_wins else match["away_club_id"]
        winner_overall = match["home_overall"] if home_wins else match["away_overall"]
        db.execute(
            """UPDATE promotion_playoff_matches SET
               home_score = ?, away_score = ?, home_penalties = ?, away_penalties = ?,
               winner_seed = ?, winner_team = ?, winner_club_id = ?, winner_overall = ?
               WHERE id = ?""",
            (
                home_score, away_score, home_penalties, away_penalties,
                winner_seed, winner_team, winner_club_id, winner_overall, match["id"],
            ),
        )
    return current_stage


def apply_penalty_kick(
    state: dict[str, object],
    side: str,
    shot_direction: str,
    keeper_direction: str,
) -> None:
    kicks = state.setdefault("kicks", [])
    if not isinstance(kicks, list):
        raise ValueError("El estado de los penales no es válido.")
    kicks.append(
        {
            "side": side,
            "direction": shot_direction,
            "saved": shot_direction == keeper_direction,
            "scored": shot_direction != keeper_direction,
        }
    )


def finish_user_playoff_shootout(
    db: sqlite3.Connection,
    match: sqlite3.Row,
    state: dict[str, object],
) -> bool:
    kicks = state.get("kicks")
    if not isinstance(kicks, list):
        raise ValueError("El estado de los penales no es válido.")
    home_score = sum(
        kick["side"] == "home" and kick["scored"] for kick in kicks
    )
    away_score = sum(
        kick["side"] == "away" and kick["scored"] for kick in kicks
    )
    home_kicks = sum(kick["side"] == "home" for kick in kicks)
    away_kicks = sum(kick["side"] == "away" for kick in kicks)
    kicks_played = len(kicks)

    decided = False
    if home_kicks <= 5 and away_kicks <= 5:
        home_remaining = max(0, 5 - home_kicks)
        away_remaining = max(0, 5 - away_kicks)
        decided = home_score > away_score + away_remaining or (
            away_score > home_score + home_remaining
        )
        if home_kicks == away_kicks == 5 and home_score != away_score:
            decided = True
    elif home_kicks == away_kicks and home_score != away_score:
        decided = True

    state["home_score"] = home_score
    state["away_score"] = away_score
    state["complete"] = decided
    if not decided:
        return False

    home_wins = home_score > away_score
    winner_seed = match["home_seed"] if home_wins else match["away_seed"]
    winner_team = match["home_team"] if home_wins else match["away_team"]
    winner_club_id = match["home_club_id"] if home_wins else match["away_club_id"]
    winner_overall = match["home_overall"] if home_wins else match["away_overall"]
    db.execute(
        """UPDATE promotion_playoff_matches SET
           home_penalties = ?, away_penalties = ?, winner_seed = ?,
           winner_team = ?, winner_club_id = ?, winner_overall = ?,
           shootout_state = ?
           WHERE id = ?""",
        (
            home_score,
            away_score,
            winner_seed,
            winner_team,
            winner_club_id,
            winner_overall,
            json.dumps(state, ensure_ascii=False),
            match["id"],
        ),
    )
    return True


def play_user_playoff_penalty(
    db: sqlite3.Connection, match: sqlite3.Row, direction: str
) -> bool:
    if direction not in {"left", "center", "right"}:
        raise ValueError("Elegí una dirección válida para el penal.")
    if match["winner_team"] is not None:
        raise ValueError("La definición por penales ya terminó.")
    if (
        match["home_score"] is None
        or match["home_score"] != match["away_score"]
    ):
        raise ValueError("El partido del playoff todavía no está listo para los penales.")

    user_side = "home" if match["home_club_id"] is None else "away"
    state = json.loads(match["shootout_state"] or "{}")
    if not isinstance(state, dict):
        raise ValueError("El estado de los penales no es válido.")
    kicks = state.setdefault("kicks", [])
    if not isinstance(kicks, list):
        raise ValueError("El estado de los penales no es válido.")
    side_to_shoot = "home" if len(kicks) % 2 == 0 else "away"

    if side_to_shoot == user_side:
        apply_penalty_kick(
            state,
            user_side,
            direction,
            random.choice(("left", "center", "right")),
        )
    else:
        apply_penalty_kick(
            state,
            side_to_shoot,
            random.choice(("left", "center", "right")),
            direction,
        )
    complete = finish_user_playoff_shootout(db, match, state)
    db.execute(
        """UPDATE promotion_playoff_matches SET shootout_state = ?
           WHERE id = ? AND winner_team IS NULL""",
        (json.dumps(state, ensure_ascii=False), match["id"]),
    )
    return complete


def advance_promotion_playoff(db: sqlite3.Connection) -> str:
    progress = db.execute(
        "SELECT current_stage FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    if progress is None:
        raise ValueError("El playoff de ascenso todavía no está disponible.")
    stage = progress["current_stage"]
    if stage == "complete":
        raise ValueError("El playoff de ascenso ya terminó.")
    matches = db.execute(
        """SELECT * FROM promotion_playoff_matches
           WHERE stage = ? ORDER BY match_number""",
        (stage,),
    ).fetchall()
    if not matches or any(match["winner_team"] is None for match in matches):
        raise ValueError("Disputá todos los partidos de esta etapa antes de avanzar.")

    if stage == "final":
        winner = matches[0]
        promotion_award_type = (
            f"playoff_promotion_{current_season_number(db)}"
            if winner["winner_club_id"] is None
            else (
                f"playoff_promotion_{current_season_number(db)}"
                f"_club_{winner['winner_club_id']}"
            )
        )
        award = db.execute(
            """INSERT OR IGNORE INTO tournament_awards
               (award_type, team_name, description)
               VALUES (?, ?, 'Ascenso a Primera División por playoff')""",
            (
                promotion_award_type,
                winner["winner_team"],
            ),
        )
        career_team = db.execute(
            "SELECT club_name FROM career WHERE id = 1"
        ).fetchone()["club_name"]
        if award.rowcount and winner["winner_team"] == career_team:
            db.execute("UPDATE career SET budget = budget + 2500000 WHERE id = 1")
        ensure_two_division_movements(db, current_season_number(db))
        next_stage = "complete"
    else:
        winners = [
            {
                "seed": match["winner_seed"],
                "team": match["winner_team"],
                "club_id": match["winner_club_id"],
                "overall": match["winner_overall"],
            }
            for match in matches
        ]
        winners.sort(key=lambda team: team["seed"])
        if stage == "quarterfinal":
            next_stage = "semifinal"
            pairings = ((winners[0], winners[3]), (winners[1], winners[2]))
        else:
            next_stage = "final"
            pairings = ((winners[0], winners[1]),)
        for match_number, (home, away) in enumerate(pairings, start=1):
            db.execute(
                """INSERT INTO promotion_playoff_matches
                   (stage, match_number, home_seed, away_seed, home_team, away_team,
                    home_club_id, away_club_id, home_overall, away_overall)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    next_stage, match_number, home["seed"], away["seed"],
                    home["team"], away["team"], home["club_id"], away["club_id"],
                    home["overall"], away["overall"],
                ),
            )
    db.execute(
        "UPDATE promotion_playoff_progress SET current_stage = ? WHERE id = 1",
        (next_stage,),
    )
    if next_stage == "complete":
        ensure_two_division_movements(db, current_season_number(db))
    return next_stage


app.jinja_env.filters["money"] = money


def build_club_crest_svg(
    club_name: str,
    primary: str,
    secondary: str,
    symbol: str,
    shape: str = "shield",
) -> str:
    initial = escape(club_name[:1].upper() or "C")
    symbols = {
        "star": (
            '<path d="M50 28l5.8 11.8 13 1.9-9.4 9.2 2.2 13-11.6-6.1-11.6 6.1'
            ' 2.2-13-9.4-9.2 13-1.9z" fill="{secondary}"/>'
        ),
        "stripes": (
            '<g clip-path="url(#shield)"><path d="M23 8h12v86H23zm21 0h12v99H44zm21'
            ' 0h12v86H65z" fill="{secondary}"/></g>'
        ),
        "ball": (
            '<circle cx="50" cy="48" r="20" fill="none" stroke="{secondary}"'
            ' stroke-width="4"/><path d="m50 35 9 7-3 11H44l-3-11zm-9 7-8-3m23 3'
            ' 8-3m-17 14-4 9m11-9 4 9" fill="none" stroke="{secondary}"'
            ' stroke-width="3" stroke-linecap="round"/>'
        ),
        "initial": (
            '<text x="50" y="61" text-anchor="middle" fill="{secondary}"'
            ' font-family="Arial,sans-serif" font-size="38" font-weight="700">{initial}</text>'
        ),
        "crown": (
            '<path d="m25 59 5-24 15 13 5-20 5 20 15-13 5 24zM28 66h44v6H28z"'
            ' fill="{secondary}"/>'
        ),
        "diamond": (
            '<path d="m50 25 25 25-25 25-25-25z" fill="{secondary}"/>'
        ),
        "cross": (
            '<path d="M42 28h16v14h14v16H58v14H42V58H28V42h14z" fill="{secondary}"/>'
        ),
        "chevron": (
            '<path d="m25 34 25 20 25-20v17L50 71 25 51z" fill="{secondary}"/>'
        ),
        "sun": (
            '<g fill="none" stroke="{secondary}" stroke-width="5" stroke-linecap="round">'
            '<circle cx="50" cy="50" r="15"/><path d="M50 24v-8m0 68v-8M24 50h-8m68 0h-8'
            'M32 32l-6-6m48 48-6-6m0-36 6-6m-48 48 6-6"/></g>'
        ),
        "mountain": (
            '<path d="m20 70 19-32 11 17 10-14 20 29z" fill="{secondary}"/>'
            '<path d="m34 47 5-9 7 11-5-3-3 4zm20 2 6-8 7 11-7-4-3 4z"'
            ' fill="{primary}"/>'
        ),
        "lightning": (
            '<path d="M55 23 32 54h15l-4 24 25-34H52z" fill="{secondary}"/>'
        ),
        "anchor": (
            '<g fill="none" stroke="{secondary}" stroke-width="5" stroke-linecap="round"'
            ' stroke-linejoin="round"><circle cx="50" cy="30" r="7"/><path d="M50 37v38'
            'M35 48h30M24 60c4 13 14 20 26 20s22-7 26-20M24 60l-1 13 13-3m40-10 1 13-13-3'
            '"/></g>'
        ),
    }
    shapes = {
        "shield": '<path d="M8 6h84v57c0 23-19 39-42 53C27 102 8 86 8 63z"/>',
        "round": '<circle cx="50" cy="60" r="44"/>',
        "rounded": (
            '<path d="M17 7h66a9 9 0 0 1 9 9v49c0 25-18 40-42 51C26 103 8 90 8'
            ' 65V16a9 9 0 0 1 9-9z"/>'
        ),
        "square": '<rect x="8" y="6" width="84" height="108" rx="8"/>',
    }
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", primary):
        primary = DEFAULT_CREST_PRIMARY
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", secondary):
        secondary = DEFAULT_CREST_SECONDARY
    shape_markup = shapes.get(shape, shapes["shield"])
    symbol_svg = symbols.get(symbol, symbols["star"]).format(
        primary=primary, secondary=secondary, initial=initial
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">'
        f'<defs><clipPath id="shield">{shape_markup}</clipPath></defs>'
        f'<g fill="{primary}" stroke="{secondary}" stroke-width="5">{shape_markup}</g>'
        f"{symbol_svg}"
        f'<path d="M23 78h54" stroke="{secondary}" stroke-width="4"'
        ' stroke-linecap="round"/>'
        "</svg>"
    )


@lru_cache(maxsize=128)
def infer_shirt_colors_from_logo(logo: str | None) -> tuple[str, str] | None:
    if not logo or not logo.startswith("/static/crests/"):
        return None
    crest_directory = (BASE_DIR / "static" / "crests").resolve()
    logo_path = (BASE_DIR / logo.lstrip("/\\")).resolve()
    if logo_path.suffix.lower() != ".svg" or crest_directory not in logo_path.parents:
        return None
    try:
        root = ET.parse(logo_path).getroot()
    except (ET.ParseError, OSError) as error:
        app.logger.warning("No se pudieron leer los colores del escudo %s: %s", logo, error)
        return None

    color_pattern = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?")
    colors: Counter[str] = Counter()
    stop_colors: list[str] = []
    ordered_colors: list[str] = []
    for element in root.iter():
        for attribute, value in element.attrib.items():
            values = color_pattern.findall(value)
            for value_color in values:
                color = value_color.lower()
                if len(color) == 4:
                    color = "#" + "".join(character * 2 for character in color[1:])
                colors[color] += 1
                ordered_colors.append(color)
                if attribute.rsplit("}", 1)[-1] == "stop-color":
                    stop_colors.append(color)
    if not colors:
        return None

    def is_chromatic(color: str) -> bool:
        channels = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
        return max(channels) - min(channels) >= 32

    primary = next(iter(stop_colors), None)
    if primary is None:
        primary = next(
            (color for color in colors if is_chromatic(color)),
            colors.most_common(1)[0][0],
        )
    candidates = [
        color
        for color in colors
        if color != primary and is_chromatic(color)
    ]
    if not candidates:
        candidates = [color for color in colors if color != primary]
    secondary = (
        max(candidates, key=lambda color: (colors[color], -ordered_colors.index(color)))
        if candidates
        else DEFAULT_TEAM_SHIRT_SECONDARY
    )
    return primary, secondary


def team_shirt_style(
    team_name: str,
    primary: str | None = None,
    secondary: str | None = None,
    pattern: str | None = None,
    logo: str | None = None,
) -> dict[str, str]:
    del team_name
    inferred = infer_shirt_colors_from_logo(logo)
    inferred_primary, inferred_secondary = (
        inferred
        if inferred is not None
        else (DEFAULT_TEAM_SHIRT_PRIMARY, DEFAULT_TEAM_SHIRT_SECONDARY)
    )
    return {
        "shirt_primary": (
            primary.lower()
            if primary and re.fullmatch(r"#[0-9A-Fa-f]{6}", primary)
            else inferred_primary
        ),
        "shirt_secondary": (
            secondary.lower()
            if secondary and re.fullmatch(r"#[0-9A-Fa-f]{6}", secondary)
            else inferred_secondary
        ),
        "shirt_pattern": pattern if pattern in SHIRT_PATTERNS else "solid",
    }


def restore_original_player_overalls(db: sqlite3.Connection) -> None:
    db.execute(
        "UPDATE players SET base_overall = overall WHERE base_overall IS NULL"
    )
    db.execute("UPDATE players SET overall = base_overall")
    dataset = json.loads(
        (BASE_DIR / "data_2026.json").read_text(encoding="utf-8")
    )
    for player in dataset["players"]:
        db.execute(
            """UPDATE players SET overall = ?, base_overall = ?
               WHERE provider_id = ?""",
            (
                int(player.get("overall", 60)),
                int(player.get("overall", 60)),
                str(player["provider_id"]),
            ),
        )


def restore_initial_club_divisions(db: sqlite3.Connection) -> None:
    initial_clubs = json.loads(
        (BASE_DIR / "data_2026.json").read_text(encoding="utf-8")
    )["clubs"]
    for club in initial_clubs:
        db.execute(
            """UPDATE clubs SET division = ?
               WHERE provider_id = ? OR (provider_id IS NULL AND name = ?)""",
            (club["division"], str(club["provider_id"]), club["name"]),
        )


@app.get("/escudo-club.svg")
def club_crest():
    career = get_career()
    if not career:
        abort(404)
    svg = build_club_crest_svg(
        career["club_name"],
        career["crest_primary"],
        career["crest_secondary"],
        career["crest_symbol"],
        career["crest_shape"],
    )
    return Response(svg, mimetype="image/svg+xml")


@app.route("/", methods=["GET", "POST"])
def home():
    career = get_career()
    if request.method == "POST":
        if career:
            return redirect(url_for("dashboard"))
        manager = request.form.get("manager_name", "").strip()
        club = request.form.get("club_name", "").strip()
        division = request.form.get("division", "")
        province = request.form.get("province", "").strip()
        crest_primary = request.form.get("crest_primary", DEFAULT_CREST_PRIMARY)
        crest_secondary = request.form.get("crest_secondary", DEFAULT_CREST_SECONDARY)
        crest_symbol = request.form.get("crest_symbol", "star")
        crest_shape = request.form.get("crest_shape", "shield")
        shirt_primary = request.form.get("shirt_primary", DEFAULT_SHIRT_PRIMARY)
        shirt_secondary = request.form.get("shirt_secondary", DEFAULT_SHIRT_SECONDARY)
        shirt_pattern = request.form.get("shirt_pattern", "solid")
        if not manager or not club or division not in ("Primera División", "Primera Nacional"):
            flash("Completá tu nombre, el nombre del club y una categoría válida.", "error")
            return render_template(
                "home.html",
                career=None,
                crest_symbols=CREST_SYMBOLS,
                crest_shapes=CREST_SHAPES,
                default_crest_primary=DEFAULT_CREST_PRIMARY,
                default_crest_secondary=DEFAULT_CREST_SECONDARY,
                default_shirt_primary=shirt_primary,
                default_shirt_secondary=shirt_secondary,
                shirt_patterns=SHIRT_PATTERNS,
                default_shirt_pattern=shirt_pattern,
            )
        if len(manager) > 50 or len(club) > 40 or len(province) > 40:
            flash("Revisá la longitud de los campos: hay un máximo de 40/50 caracteres.", "error")
            return render_template(
                "home.html",
                career=None,
                crest_symbols=CREST_SYMBOLS,
                crest_shapes=CREST_SHAPES,
                default_crest_primary=DEFAULT_CREST_PRIMARY,
                default_crest_secondary=DEFAULT_CREST_SECONDARY,
                default_shirt_primary=shirt_primary,
                default_shirt_secondary=shirt_secondary,
                shirt_patterns=SHIRT_PATTERNS,
                default_shirt_pattern=shirt_pattern,
            )
        if (
            not re.fullmatch(r"#[0-9A-Fa-f]{6}", crest_primary)
            or not re.fullmatch(r"#[0-9A-Fa-f]{6}", crest_secondary)
            or crest_symbol not in CREST_SYMBOLS
            or crest_shape not in CREST_SHAPES
            or not re.fullmatch(r"#[0-9A-Fa-f]{6}", shirt_primary)
            or not re.fullmatch(r"#[0-9A-Fa-f]{6}", shirt_secondary)
            or shirt_pattern not in SHIRT_PATTERNS
        ):
            flash("Elegí colores y diseños válidos para el escudo y la camiseta.", "error")
            return render_template(
                "home.html",
                career=None,
                crest_symbols=CREST_SYMBOLS,
                crest_shapes=CREST_SHAPES,
                default_crest_primary=DEFAULT_CREST_PRIMARY,
                default_crest_secondary=DEFAULT_CREST_SECONDARY,
                default_shirt_primary=shirt_primary,
                default_shirt_secondary=shirt_secondary,
                shirt_patterns=SHIRT_PATTERNS,
                default_shirt_pattern=shirt_pattern,
            )
        db = get_db()
        restore_initial_club_divisions(db)
        restore_original_player_overalls(db)
        db.execute(
            """INSERT INTO career
               (id, manager_name, club_name, division, province, season_start, budget,
                crest_primary, crest_secondary, crest_symbol, crest_shape,
                shirt_primary, shirt_secondary, shirt_pattern)
               VALUES (1, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)""",
            (
                manager,
                club,
                division,
                province or "Argentina",
                SEASON_START.isoformat(),
                crest_primary.lower(),
                crest_secondary.lower(),
                crest_symbol,
                crest_shape,
                shirt_primary.lower(),
                shirt_secondary.lower(),
                shirt_pattern,
            ),
        )
        db.execute(
            """INSERT OR REPLACE INTO tournament_progress
               (id, current_round, current_season, signing_limit, formation, auto_simulation)
               VALUES (1, 1, 1, ?, '4-4-2', 0)""",
            (MAX_SQUAD_SIZE,),
        )
        db.commit()
        return redirect(url_for("dashboard"))
    if career:
        return redirect(url_for("dashboard"))
    return render_template(
        "home.html",
        career=None,
        crest_symbols=CREST_SYMBOLS,
        crest_shapes=CREST_SHAPES,
        default_crest_primary=DEFAULT_CREST_PRIMARY,
        default_crest_secondary=DEFAULT_CREST_SECONDARY,
        default_shirt_primary=DEFAULT_SHIRT_PRIMARY,
        default_shirt_secondary=DEFAULT_SHIRT_SECONDARY,
        shirt_patterns=SHIRT_PATTERNS,
        default_shirt_pattern="solid",
    )


@app.get("/club")
def dashboard():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    decisions = get_db().execute("SELECT * FROM decisions ORDER BY day").fetchall()
    options = (
        get_daily_options(get_db(), career["day"])
        if career["phase"] == "preseason"
        and not get_db().execute(
            "SELECT 1 FROM decisions WHERE day = ?", (career["day"],)
        ).fetchone()
        else []
    )
    next_date = date.fromisoformat(career["season_start"]) + timedelta(days=career["day"] - 1)
    return render_template(
        "dashboard.html",
        career=career,
        decisions=decisions,
        options=options,
        next_date=next_date,
        choices=DECISIONS,
    )


@app.post("/club/decision")
def make_decision():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "preseason":
        return redirect(url_for("market"))
    db = get_db()
    if db.execute("SELECT 1 FROM decisions WHERE day = ?", (career["day"],)).fetchone():
        flash("Ya tomaste una decisión para este día.", "error")
        return redirect(url_for("dashboard"))
    key = request.form.get("decision", "")
    offered_keys = {option["decision_key"] for option in get_daily_options(db, career["day"])}
    if key not in offered_keys:
        abort(400, "Elegí una de las tres decisiones disponibles para hoy.")
    decision = DECISIONS[key]
    effects = decision["effects"]
    db.execute(
        "INSERT INTO decisions (day, decision_key) VALUES (?, ?)",
        (career["day"], key),
    )
    db.execute(
        """UPDATE career SET budget = budget + ?,
           fans = MAX(0, fans + ?), popularity = MIN(100, MAX(0, popularity + ?)),
           day = CASE WHEN day >= 20 THEN 20 ELSE day + 1 END,
           phase = CASE WHEN day >= 20 THEN 'market' ELSE phase END
           WHERE id = 1""",
        (effects["budget"], effects["fans"], effects["popularity"]),
    )
    db.commit()
    updated = get_career()
    if updated and updated["phase"] == "market":
        try:
            from live_football_api import ensure_football_data_loaded
            ensure_football_data_loaded(db, database_path=DATABASE)
        except Exception as error:
            app.logger.warning("Auto-sync error on market unlock: %s", error)
        flash("¡Pretemporada completa! El mercado de pases ya está abierto.", "success")
        return redirect(url_for("market"))
    flash(f"Decisión aplicada: {decision['title']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/mercado", methods=["GET", "POST"])
def market():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] == "preseason":
        flash("Completá los 20 días de pretemporada para abrir el mercado.", "error")
        return redirect(url_for("dashboard"))
    if career["phase"] == "season":
        return redirect(url_for("fixtures"))
    db = get_db()
    squad_limit = current_squad_limit(db)
    season_number = current_season_number(db)
    selected_formation = (
        request.form.get("formation", "4-4-2")
        if request.method == "POST"
        else request.args.get("formation", "4-4-2")
    )
    if selected_formation not in SQUAD_FORMATIONS:
        abort(400, "Elegí una formación disponible.")
    if request.method == "POST":
        if request.form.get("action") == "start_tournament":
            db.execute("BEGIN IMMEDIATE")
            current_career = get_career()
            if not current_career or current_career["phase"] != "market":
                db.rollback()
                flash("El mercado de pases ya no está disponible.", "error")
                return redirect(url_for("market"))
            db.execute(
                "UPDATE career SET phase = 'season' WHERE id = 1 AND phase = 'market'"
            )
            db.execute(
                "UPDATE tournament_progress SET formation = ? WHERE id = 1",
                (selected_formation,),
            )
            db.commit()
            updated_career = get_career()
            ensure_tournament_schedule(db, updated_career)
            ensure_copa_argentina(db, updated_career)
            flash(
                "¡Temporada iniciada! Ya podés jugar la liga y descubrir el sorteo de la Copa Argentina.",
                "success",
            )
            return redirect(url_for("copa_argentina"))
        if request.form.get("action") == "auto_build_and_start":
            db.execute("BEGIN IMMEDIATE")
            current_career = get_career()
            if not current_career or current_career["phase"] != "market":
                db.rollback()
                flash("El mercado de pases ya no está disponible.", "error")
                return redirect(url_for("market"))

            signed_players = db.execute(
                """SELECT p.id AS player_id, p.position FROM signings s
                   JOIN players p ON p.id = s.player_id"""
            ).fetchall()
            signed_player_ids = {row["player_id"] for row in signed_players}
            budget = int(current_career["budget"])
            squad_size = len(signed_player_ids)
            role_counts = {group: 0 for group, _ in AUTO_SQUAD_TARGETS}
            for player in signed_players:
                group = player_position_group(player["position"])
                if group:
                    role_counts[group] += 1
            role_deficits = {
                group: max(0, target - role_counts[group])
                for group, target in AUTO_SQUAD_TARGETS
            }
            available_players = [
                dict(player)
                for player in db.execute(
                    """SELECT p.* FROM players p
                   JOIN clubs c ON c.id = p.club_id
                   WHERE c.division = ?
                     AND p.id NOT IN (SELECT player_id FROM signings)""",
                    (current_career["division"],),
                ).fetchall()
            ]
            available_by_group: dict[str, list[dict[str, object]]] = {
                group: [] for group, _ in AUTO_SQUAD_TARGETS
            }
            for player in available_players:
                group = player_position_group(str(player["position"]))
                if group:
                    player["group"] = group
                    player["fee"] = transfer_fee(
                        int(player["market_value"]), current_career["division"]
                    )
                    available_by_group[group].append(player)
            for players_in_group in available_by_group.values():
                random.shuffle(players_in_group)

            slots_to_fill = [
                group
                for index in range(max(role_deficits.values(), default=0))
                for group, _ in AUTO_SQUAD_TARGETS
                if role_deficits[group] > index
            ]
            signings_added = {group: 0 for group, _ in AUTO_SQUAD_TARGETS}
            for slot_index, group in enumerate(slots_to_fill):
                if squad_size >= MAX_SQUAD_SIZE:
                    break
                later_slots = slots_to_fill[slot_index + 1 :]
                reserve = sum(
                    min(
                        int(player["fee"])
                        for player in available_by_group[future_group]
                    )
                    for future_group in later_slots
                    if available_by_group[future_group]
                )
                affordable_players = [
                    player
                    for player in available_by_group[group]
                    if int(player["fee"]) <= budget
                ]
                if not affordable_players:
                    continue
                feasible_players = [
                    player
                    for player in affordable_players
                    if budget - int(player["fee"]) >= reserve
                ]
                choices = feasible_players or [
                    player
                    for player in affordable_players
                    if int(player["fee"])
                    == min(int(candidate["fee"]) for candidate in affordable_players)
                ]
                player = random.choice(choices)
                db.execute(
                    "INSERT INTO signings (player_id, fee) VALUES (?, ?)",
                    (player["id"], player["fee"]),
                )
                budget -= int(player["fee"])
                squad_size += 1
                signings_added[group] += 1
                available_by_group[group].remove(player)

            signed_players = [
                dict(player)
                for player in db.execute(
                    """SELECT p.id AS player_id, p.position FROM signings s
                       JOIN players p ON p.id = s.player_id"""
                ).fetchall()
            ]
            starters_by_group: dict[str, list[dict[str, object]]] = {
                group: [] for group, _ in AUTO_SQUAD_TARGETS
            }
            for player in signed_players:
                group = player_position_group(str(player["position"]))
                if group:
                    starters_by_group[group].append(player)
            for players_in_group in starters_by_group.values():
                random.shuffle(players_in_group)
            remaining_starters = signed_players.copy()
            starter_ids: list[int] = []
            slot_count = sum(count for _, count in SQUAD_FORMATIONS[selected_formation])
            for position, count in SQUAD_FORMATIONS[selected_formation]:
                group = player_position_group(position)
                for _ in range(count):
                    options = [
                        candidate
                        for candidate in (starters_by_group[group] if group else [])
                        if candidate in remaining_starters
                    ]
                    player = random.choice(options) if options else (
                        random.choice(remaining_starters) if remaining_starters else None
                    )
                    if player is None:
                        continue
                    if group and player in starters_by_group[group]:
                        starters_by_group[group].remove(player)
                    remaining_starters.remove(player)
                    starter_ids.append(int(player["player_id"]))
            db.execute(
                "DELETE FROM squad_lineup WHERE formation = ?",
                (selected_formation,),
            )
            db.executemany(
                """INSERT INTO squad_lineup (formation, slot_number, player_id)
                   VALUES (?, ?, ?)""",
                [
                    (selected_formation, slot_number, player_id)
                    for slot_number, player_id in enumerate(starter_ids, start=1)
                ],
            )
            db.execute("UPDATE career SET budget = ? WHERE id = 1", (budget,))
            db.execute(
                "UPDATE tournament_progress SET formation = ? WHERE id = 1",
                (selected_formation,),
            )
            db.commit()
            signings_summary = ", ".join(
                f"{signings_added[group]} {group}"
                for group, _ in AUTO_SQUAD_TARGETS
                if signings_added[group]
            ) or "ningún jugador"
            missing_roles = [
                f"{group} {role_deficits[group] - signings_added[group]}"
                for group, _ in AUTO_SQUAD_TARGETS
                if role_deficits[group] > signings_added[group]
            ]
            roster_message = (
                f" Quedaron {squad_size} jugadores en el plantel y "
                f"{len(starter_ids)} titulares en {selected_formation}."
            )
            if missing_roles:
                roster_message += (
                    " No alcanzó el presupuesto o no había disponibilidad para: "
                    + ", ".join(missing_roles)
                    + "."
                )
            flash(
                f"Equipo armado al azar: {signings_summary}. Se gastaron "
                f"{money(int(current_career['budget']) - budget)}."
                f"{roster_message} Podés cambiar la alineación antes de comenzar la temporada.",
                "success",
            )
            return redirect(url_for("market", formation=selected_formation))
        try:
            player_id = int(request.form.get("player_id", ""))
        except ValueError:
            abort(400, "Jugador no válido.")
        db.execute("BEGIN IMMEDIATE")
        squad_size = db.execute("SELECT COUNT(*) FROM signings").fetchone()[0]
        if request.form.get("action") == "sell_player":
            try:
                player_id = int(request.form.get("player_id", ""))
            except ValueError:
                abort(400, "Jugador no válido.")
            signing = db.execute(
                """SELECT p.name, s.loan_season_number FROM signings s
                   JOIN players p ON p.id = s.player_id
                   WHERE p.id = ?""",
                (player_id,),
            ).fetchone()
            if not signing:
                db.rollback()
                flash("Ese jugador no pertenece a tu plantel.", "error")
                return redirect(url_for("market"))
            if signing["loan_season_number"] is not None:
                db.rollback()
                flash("Un jugador cedido vuelve a su club al terminar la temporada.", "error")
                return redirect(url_for("market"))
            db.execute("DELETE FROM squad_lineup WHERE player_id = ?", (player_id,))
            db.execute("DELETE FROM signings WHERE player_id = ?", (player_id,))
            db.execute(
                "UPDATE career SET budget = budget + ? WHERE id = 1",
                (PLAYER_SALE_REVENUE,),
            )
            db.commit()
            flash(
                f"{signing['name']} fue vendido. Recibiste $500.000 para tu presupuesto.",
                "success",
            )
            return redirect(url_for("market"))
        if request.form.get("action") == "request_loan":
            if squad_size >= squad_limit:
                db.rollback()
                flash("El plantel está completo. Liberá un lugar antes de pedir un préstamo.", "error")
                return redirect(url_for("market"))
            if career["division"] != "Primera Nacional":
                db.rollback()
                flash(
                    "Los préstamos desde Primera División están disponibles para clubes de Primera Nacional.",
                    "error",
                )
                return redirect(url_for("market"))
            player = db.execute(
                """SELECT p.*, c.name AS club_name FROM players p
                   JOIN clubs c ON c.id = p.club_id
                   WHERE p.id = ? AND c.division = 'Primera División'""",
                (player_id,),
            ).fetchone()
            if player is None:
                db.rollback()
                abort(404, "Ese jugador no está disponible para préstamo.")
            if db.execute(
                "SELECT 1 FROM signings WHERE player_id = ?", (player_id,)
            ).fetchone():
                db.rollback()
                flash("Ese jugador ya forma parte de tu plantel.", "error")
                return redirect(url_for("market"))
            fee = loan_fee(int(player["market_value"]))
            if int(career["budget"]) < fee:
                db.rollback()
                flash(
                    f"El préstamo de {player['name']} cuesta ${fee:,}; "
                    "el presupuesto no alcanza.",
                    "error",
                )
                return redirect(url_for("market"))
            db.execute(
                """INSERT INTO signings (player_id, fee, loan_season_number)
                   VALUES (?, ?, ?)""",
                (player_id, fee, season_number),
            )
            db.execute(
                "UPDATE career SET budget = budget - ? WHERE id = 1", (fee,)
            )
            db.commit()
            flash(
                f"{player['name']} llegó a préstamo desde {player['club_name']} "
                f"por una temporada. Se descontaron ${fee:,}.",
                "success",
            )
            return redirect(url_for("market"))
        if squad_size >= squad_limit:
            db.rollback()
            flash(
                "El plantel alcanzó el límite de incorporaciones. "
                "Vendé jugadores para poder incorporar; el máximo es de 25 jugadores.",
                "error",
            )
            return redirect(url_for("market"))
        player = db.execute(
            """SELECT p.* FROM players p
               WHERE p.id = ? AND p.club_id IS NOT NULL
                 AND p.club_id IN (SELECT id FROM clubs WHERE division = ?)""",
            (player_id, career["division"]),
        ).fetchone()
        if not player:
            db.rollback()
            abort(404, "Ese jugador no está disponible en el mercado.")
        if db.execute("SELECT 1 FROM signings WHERE player_id = ?", (player_id,)).fetchone():
            db.rollback()
            flash("Ese jugador ya fue incorporado.", "error")
            return redirect(url_for("market"))
        fee = transfer_fee(player["market_value"], career["division"])
        if career["budget"] < fee:
            db.rollback()
            flash("El presupuesto no alcanza para esta incorporación.", "error")
            return redirect(url_for("market"))
        db.execute("INSERT INTO signings (player_id, fee) VALUES (?, ?)", (player_id, fee))
        db.execute(
            "UPDATE career SET budget = budget - ? WHERE id = 1",
            (fee,),
        )
        db.commit()
        flash(f"{player['name']} ya es nuevo jugador de {career['club_name']}.", "success")
        return redirect(
            url_for(
                "market",
                name=request.form.get("name", "")[:80],
                team=request.form.get("team", ""),
                position=request.form.get("position", ""),
                overall_max=request.form.get("overall_max", ""),
                page=request.form.get("page", "1"),
                formation=selected_formation,
            )
        )
    try:
        from live_football_api import ensure_football_data_loaded
        ensure_football_data_loaded(db, database_path=DATABASE)
    except Exception as error:
        app.logger.warning("Market auto-sync error: %s", error)

    position_rows = db.execute(
        """SELECT DISTINCT p.position FROM players p
           JOIN clubs c ON c.id = p.club_id
           WHERE c.division = ? ORDER BY p.position""",
        (career["division"],),
    ).fetchall()
    positions = [row["position"] for row in position_rows]
    club_rows = db.execute(
        """SELECT c.id, c.name FROM clubs c
           WHERE c.division = ? ORDER BY c.name""",
        (career["division"],),
    ).fetchall()
    position = request.args.get("position", "").strip()
    team_text = request.args.get("team", "").strip()
    try:
        team_id = int(team_text) if team_text else 0
    except ValueError:
        abort(400, "Elegí un equipo disponible.")
    team_ids = {row["id"] for row in club_rows}
    if team_id and team_id not in team_ids:
        abort(400, "Elegí un equipo disponible.")
    player_name = request.args.get("name", "").strip()[:80]
    if position and position not in positions:
        abort(400, "Elegí una posición disponible.")
    try:
        overall_max_text = request.args.get("overall_max", "").strip()
        overall_max = int(overall_max_text) if overall_max_text else None
    except ValueError:
        abort(400, "El OVR máximo debe ser un número entre 0 y 99.")
    if overall_max is not None and not 0 <= overall_max <= 99:
        abort(400, "El OVR máximo debe ser un número entre 0 y 99.")
    try:
        requested_page = int(request.args.get("page", "1"))
    except ValueError:
        abort(400, "La página solicitada no es válida.")
    if requested_page < 1:
        abort(400, "La página solicitada no es válida.")
    filters = (
        career["division"],
        position,
        position,
        team_id,
        team_id,
        player_name,
        player_name,
    )
    total_players = db.execute(
        """SELECT COUNT(*) FROM players p
           JOIN clubs c ON c.id = p.club_id
           WHERE c.division = ?
             AND p.id NOT IN (SELECT player_id FROM signings)
             AND (? = '' OR p.position = ?)
             AND (? = 0 OR c.id = ?)
             AND (? = '' OR instr(lower(p.name), lower(?)) > 0)
             AND (? IS NULL OR p.overall <= ?)""",
        (*filters, overall_max, overall_max),
    ).fetchone()[0]
    total_pages = max(1, (total_players + MARKET_PAGE_SIZE - 1) // MARKET_PAGE_SIZE)
    current_page = min(requested_page, total_pages)
    players = db.execute(
        """SELECT p.*, c.name AS club_name, c.logo AS club_logo FROM players p
           JOIN clubs c ON c.id = p.club_id
           WHERE c.division = ?
             AND p.id NOT IN (SELECT player_id FROM signings)
             AND (? = '' OR p.position = ?)
             AND (? = 0 OR c.id = ?)
             AND (? = '' OR instr(lower(p.name), lower(?)) > 0)
             AND (? IS NULL OR p.overall <= ?)
           ORDER BY p.overall DESC, p.market_value ASC, p.id
           LIMIT ? OFFSET ?""",
        (
            *filters,
            overall_max,
            overall_max,
            MARKET_PAGE_SIZE,
            (current_page - 1) * MARKET_PAGE_SIZE,
        ),
    ).fetchall()
    players = [
        dict(
            player,
            transfer_fee=transfer_fee(player["market_value"], career["division"]),
        )
        for player in players
    ]
    loan_players = []
    if career["division"] == "Primera Nacional":
        loan_players = [
            dict(player, loan_fee=loan_fee(int(player["market_value"])))
            for player in db.execute(
                """SELECT p.*, c.name AS club_name, c.logo AS club_logo
                   FROM players p JOIN clubs c ON c.id = p.club_id
                   WHERE c.division = 'Primera División'
                     AND p.id NOT IN (SELECT player_id FROM signings)
                   ORDER BY p.overall DESC, p.market_value, p.name"""
            ).fetchall()
        ]
    squad = db.execute(
        """SELECT p.*, s.fee, s.loan_season_number,
                  c.name AS origin_club_name, c.logo AS origin_club_logo
           FROM signings s
           JOIN players p ON p.id = s.player_id
           LEFT JOIN clubs c ON c.id = p.club_id
           ORDER BY s.signed_at DESC"""
    ).fetchall()
    saved_slots = {
        row["slot_number"]: row["player_id"]
        for row in db.execute(
            "SELECT slot_number, player_id FROM squad_lineup WHERE formation = ?",
            (selected_formation,),
        ).fetchall()
    }
    formation_lines, substitute_players = arrange_squad(
        squad, selected_formation, saved_slots
    )
    return render_template(
        "market.html",
        career=career,
        players=players,
        loan_players=loan_players,
        squad=squad,
        positions=positions,
        selected_position=position,
        overall_max=overall_max,
        clubs=club_rows,
        selected_team=team_text,
        player_name=player_name,
        max_squad_size=squad_limit,
        season_number=season_number,
        total_players=total_players,
        current_page=current_page,
        total_pages=total_pages,
        formations=tuple(SQUAD_FORMATIONS),
        selected_formation=selected_formation,
        formation_lines=formation_lines,
        substitute_players=substitute_players,
    )


@app.post("/mercado/alineacion")
def save_squad_lineup():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "market":
        return redirect(url_for("fixtures"))

    formation = request.form.get("formation", "")
    if formation not in SQUAD_FORMATIONS:
        abort(400, "Elegí una formación disponible.")
    slot_count = sum(count for _, count in SQUAD_FORMATIONS[formation])
    try:
        player_ids = [int(value) for value in request.form.getlist("starter_id")]
    except ValueError:
        abort(400, "La alineación contiene jugadores no válidos.")
    if len(player_ids) != slot_count or len(set(player_ids)) != slot_count:
        abort(400, "Elegí un jugador distinto para cada puesto titular.")

    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    current_career = get_career()
    if not current_career or current_career["phase"] != "market":
        db.rollback()
        return redirect(url_for("fixtures"))
    signed_player_ids = {
        row["player_id"]
        for row in db.execute("SELECT player_id FROM signings").fetchall()
    }
    if not set(player_ids).issubset(signed_player_ids):
        db.rollback()
        abort(400, "Solo podés poner como titulares jugadores de tu plantel.")

    db.execute("DELETE FROM squad_lineup WHERE formation = ?", (formation,))
    db.executemany(
        """INSERT INTO squad_lineup (formation, slot_number, player_id)
           VALUES (?, ?, ?)""",
        [
            (formation, slot_number, player_id)
            for slot_number, player_id in enumerate(player_ids, start=1)
        ],
    )
    db.execute(
        "UPDATE tournament_progress SET formation = ? WHERE id = 1",
        (formation,),
    )
    db.commit()
    flash("Alineación guardada. Los jugadores reemplazados quedan en el banco.", "success")
    return redirect(
        url_for(
            "market",
            name=request.form.get("name", "")[:80],
            team=request.form.get("team", ""),
            position=request.form.get("position", ""),
            overall_max=request.form.get("overall_max", ""),
            page=request.form.get("page", "1"),
            formation=formation,
        )
    )


@app.get("/calendario")
def fixtures():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    db = get_db()
    if career["phase"] in ("market", "season"):
        try:
            from live_football_api import ensure_football_data_loaded
            ensure_football_data_loaded(db, database_path=DATABASE)
        except Exception as error:
            app.logger.warning("Fixtures auto-sync error: %s", error)
    season_number = current_season_number(db)
    if career["phase"] == "season" and season_number > 1:
        ensure_two_division_movements(db, season_number - 1)
    if career["phase"] == "season":
        ensure_tournament_schedule(db, career)
        ensure_copa_argentina(db, career)
    matches = []
    if career["phase"] != "season":
        matches = db.execute(
        """SELECT f.matchday, f.played_on,
                  home.name AS home_name, home.logo AS home_logo,
                  away.name AS away_name, away.logo AS away_logo
           FROM fixtures f
           JOIN clubs home ON home.id = f.home_club_id
           JOIN clubs away ON away.id = f.away_club_id
           WHERE f.season = 2026 AND f.division = ?
           ORDER BY f.matchday, f.played_on, f.id""",
        (career["division"],),
        ).fetchall()
    active_round = None
    active_round_matches = []
    career_has_active_match = False
    round_complete = False
    standings: list[dict[str, int | str | bool | None]] = []
    league_scorers: list[dict[str, int | str]] = []
    league_assisters: list[dict[str, int | str]] = []
    tournament_rounds = 0
    continental_competition = None
    match_dashboard = None
    pending_season_decision = None
    auto_simulation = False
    if career["phase"] == "season":
        active_round = db.execute(
            "SELECT current_round FROM tournament_progress WHERE id = 1"
        ).fetchone()[0]
        tournament_rounds = db.execute(
            "SELECT MAX(round_number) FROM tournament_matches"
        ).fetchone()[0] or 0
        active_round_matches = db.execute(
            """SELECT * FROM tournament_matches WHERE round_number = ?
               ORDER BY home_team""",
            (active_round,),
        ).fetchall()
        player_match = next(
            (
                match
                for match in active_round_matches
                if match["home_club_id"] is None or match["away_club_id"] is None
            ),
            None,
        )
        selected_formation = db.execute(
            """SELECT formation, auto_simulation FROM tournament_progress
               WHERE id = 1"""
        ).fetchone()["formation"]
        progress_row = db.execute(
            "SELECT auto_simulation FROM tournament_progress WHERE id = 1"
        ).fetchone()
        auto_simulation = bool(progress_row["auto_simulation"])
        match_dashboard = build_match_dashboard(
            db, career, player_match, selected_formation, active_round
        )
        career_has_active_match = any(
            match["home_club_id"] is None or match["away_club_id"] is None
            for match in active_round_matches
        )
        round_complete = bool(active_round_matches) and all(
            match["home_score"] is not None and match["away_score"] is not None
            for match in active_round_matches
        )
        standings = calculate_tournament_standings(db, career)
        league_scorers, league_assisters = get_league_leaders(
            db, career, season_number
        )
        pending_season_decision = get_pending_season_decision(
            db, season_number, active_round
        )
        if pending_season_decision:
            db.commit()
        if career["division"] == "Primera División":
            relegation_candidates = {
                (team["name"], team["is_career"])
                for team in standings
                if int(team["position"]) >= max(1, len(standings) - 1)
            }
            for team in standings:
                team["is_relegation_candidate"] = (
                    (team["name"], team["is_career"]) in relegation_candidates
                )
        if active_round == tournament_rounds and round_complete:
            setup_league_outcome(db, career, standings)
            career_standing = next(
                (team for team in standings if team["is_career"]), None
            )
            if career_standing:
                continental_competition = continental_qualification(
                    career["division"], int(career_standing["position"])
                )

    season_number = current_season_number(db)
    awards = db.execute(
        """SELECT award_type, team_name, description FROM tournament_awards
           WHERE award_type LIKE ? OR award_type LIKE ? OR award_type IN
             ('champion', 'promotion', 'playoff_promotion')""",
        (f"%_{season_number}", f"%_{season_number}_club_%"),
    ).fetchall()
    playoff_stage = None
    playoff_matches = []
    playoff_stage_complete = False
    playoff_match_dashboard = None
    playoff_penalty_turn = None
    playoff_live_simulation = False
    if career["phase"] == "season":
        progress = db.execute(
            "SELECT current_stage FROM promotion_playoff_progress WHERE id = 1"
        ).fetchone()
        if progress:
            playoff_stage = progress["current_stage"]
            if playoff_stage != "complete":
                playoff_matches = db.execute(
                    """SELECT * FROM promotion_playoff_matches
                       WHERE stage = ? ORDER BY match_number""",
                    (playoff_stage,),
                ).fetchall()
                playoff_stage_complete = bool(playoff_matches) and all(
                    match["winner_team"] is not None for match in playoff_matches
                )
                player_playoff_match = next(
                    (
                        match
                        for match in playoff_matches
                        if match["home_club_id"] is None
                        or match["away_club_id"] is None
                    ),
                    None,
                )
                if player_playoff_match is not None:
                    playoff_match_data = dict(player_playoff_match)
                    playoff_match_data["played_on"] = (
                        f"PLAYOFF · {PLAYOFF_STAGE_LABELS[playoff_stage].upper()}"
                    )
                    playoff_match_data["match_events"] = (
                        player_playoff_match["playoff_events"] or "[]"
                    )
                    playoff_match_data["round_number"] = 0
                    playoff_match_dashboard = build_match_dashboard(
                        db,
                        career,
                        playoff_match_data,
                        selected_formation,
                        0,
                    )
                    if playoff_match_dashboard is not None:
                        shootout_state = json.loads(
                            player_playoff_match["shootout_state"] or "{}"
                        )
                        if not isinstance(shootout_state, dict):
                            raise ValueError(
                                "El estado de los penales del playoff no es válido."
                            )
                        kicks = shootout_state.get("kicks", [])
                        if not isinstance(kicks, list):
                            raise ValueError(
                                "El estado de los penales del playoff no es válido."
                            )
                        playoff_match_dashboard.update(
                            {
                                "winner_team": player_playoff_match["winner_team"],
                                "shootout_state": shootout_state,
                                "penalties_complete": bool(
                                    shootout_state.get("complete")
                                ),
                                "penalty_kicks": kicks,
                                "home_penalties": sum(
                                    kick["side"] == "home" and kick["scored"]
                                    for kick in kicks
                                ),
                                "away_penalties": sum(
                                    kick["side"] == "away" and kick["scored"]
                                    for kick in kicks
                                ),
                                "user_side": (
                                    "home"
                                    if player_playoff_match["home_club_id"] is None
                                    else "away"
                                ),
                            }
                        )
                        if (
                            player_playoff_match["winner_team"] is None
                            and player_playoff_match["home_score"]
                            == player_playoff_match["away_score"]
                        ):
                            playoff_penalty_turn = (
                                "home" if len(kicks) % 2 == 0 else "away"
                            )
                        playoff_live_simulation = (
                            request.args.get("playoff_live") == "1"
                            and player_playoff_match["home_score"] is not None
                        )
    playoff_results_hidden = playoff_live_simulation or bool(
        playoff_match_dashboard
        and playoff_match_dashboard["played"]
        and not playoff_match_dashboard["winner_team"]
    )
    can_start_next_season = (
        career["phase"] == "season" and season_is_complete(db)
    )
    copa_progress = db.execute(
        "SELECT * FROM copa_argentina_progress WHERE id = 1"
    ).fetchone()
    copa_is_pending = (
        career["phase"] == "season"
        and copa_progress is not None
        and int(copa_progress["season_number"]) == season_number
        and not bool(copa_progress["is_complete"])
    )
    copa_current_matches = []
    copa_draw_total = 0
    copa_draw_count = 0
    copa_round_complete = False
    copa_scheduled_matchday = None
    copa_is_matchday = False
    if copa_is_pending:
        copa_current_matches = db.execute(
            """SELECT m.*, home.logo AS home_logo, away.logo AS away_logo
               FROM copa_argentina_matches m
               LEFT JOIN clubs home ON home.id = m.home_club_id
               LEFT JOIN clubs away ON away.id = m.away_club_id
               WHERE m.season_number = ? AND m.round_number = ?
               ORDER BY m.match_number""",
            (season_number, copa_progress["current_round"]),
        ).fetchall()
        copa_draw_total = len(copa_current_matches)
        copa_draw_count = sum(
            bool(match["revealed"]) for match in copa_current_matches
        )
        copa_round_complete = bool(copa_current_matches) and all(
            match["winner_team"] is not None for match in copa_current_matches
        )
        if tournament_rounds:
            copa_scheduled_matchday = copa_argentina_league_matchday(
                db,
                season_number,
                int(copa_progress["current_round"]),
                tournament_rounds,
            )
            copa_is_matchday = active_round == copa_scheduled_matchday
    league_season_complete = (
        career["phase"] == "season"
        and active_round == tournament_rounds
        and round_complete
    )
    season_individual_awards = (
        get_season_individual_awards(db, career, season_number)
        if league_season_complete
        else []
    )
    movement_season = None
    if career["phase"] == "market" and season_number > 1:
        movement_season = season_number - 1
    elif league_season_complete or can_start_next_season:
        movement_season = season_number
    elif career["phase"] == "season" and season_number > 1:
        movement_season = season_number - 1
    season_movements = (
        get_season_movements(db, movement_season)
        if movement_season is not None
        else []
    )
    return render_template(
        "fixtures.html",
        career=career,
        matches=matches,
        active_round=active_round,
        active_round_matches=active_round_matches,
        match_dashboard=match_dashboard,
        pending_season_decision=pending_season_decision,
        pending_decision_event=(
            SEASON_DECISIONS[pending_season_decision["event_key"]]
            if pending_season_decision
            else None
        ),
        auto_simulation=auto_simulation,
        career_has_active_match=career_has_active_match,
        round_complete=round_complete,
        standings=standings,
        league_scorers=league_scorers if career["phase"] == "season" else [],
        league_assisters=league_assisters if career["phase"] == "season" else [],
        league_season_complete=league_season_complete,
        season_individual_awards=season_individual_awards,
        career_prize=(
            first_division_prize(
                next(int(team["position"]) for team in standings if team["is_career"])
            )
            if career["division"] == "Primera División" and standings
            else first_national_prize(
                next(
                    (int(team["position"]) for team in standings if team["is_career"]),
                    0,
                ),
                sum(int(team["played"]) > 0 for team in standings),
            )
            if career["division"] == "Primera Nacional" and standings
            else 0
        ),
        tournament_rounds=tournament_rounds,
        continental_competition=continental_competition,
        awards=awards,
        season_movements=season_movements,
        movement_season=movement_season,
        playoff_stage=playoff_stage,
        playoff_matches=playoff_matches,
        playoff_stage_complete=playoff_stage_complete,
        playoff_match_dashboard=playoff_match_dashboard,
        playoff_penalty_turn=playoff_penalty_turn,
        playoff_live_simulation=playoff_live_simulation,
        playoff_results_hidden=playoff_results_hidden,
        playoff_stage_labels=PLAYOFF_STAGE_LABELS,
        season_number=season_number,
        can_start_next_season=can_start_next_season,
        copa_is_pending=copa_is_pending,
        copa_progress=copa_progress,
        copa_current_matches=copa_current_matches,
        copa_draw_total=copa_draw_total,
        copa_draw_count=copa_draw_count,
        copa_round_complete=copa_round_complete,
        copa_scheduled_matchday=copa_scheduled_matchday,
        copa_is_matchday=copa_is_matchday,
        live_match_simulation=(
            request.args.get("live") == "1"
            and bool(match_dashboard)
            and bool(match_dashboard.get("played"))
        ),
    )


@app.get("/copa-argentina")
def copa_argentina():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    db = get_db()
    season_number = current_season_number(db)
    progress = db.execute(
        "SELECT * FROM copa_argentina_progress WHERE id = 1"
    ).fetchone()
    if career["phase"] == "season":
        ensure_tournament_schedule(db, career)
        ensure_copa_argentina(db, career)
        progress = db.execute(
            "SELECT * FROM copa_argentina_progress WHERE id = 1"
        ).fetchone()
    current_matches = []
    bracket_matches = []
    bracket_rounds = []
    bracket_round_count = 1
    draw_count = 0
    draw_total = 0
    round_complete = False
    career_won_copa = False
    if progress and int(progress["season_number"]) == season_number:
        current_matches = db.execute(
            """SELECT m.*, home.logo AS home_logo, away.logo AS away_logo
               FROM copa_argentina_matches m
               LEFT JOIN clubs home ON home.id = m.home_club_id
               LEFT JOIN clubs away ON away.id = m.away_club_id
               WHERE season_number = ? AND round_number = ?
               ORDER BY m.match_number""",
            (season_number, progress["current_round"]),
        ).fetchall()
        bracket_matches = db.execute(
            """SELECT m.*, home.logo AS home_logo, away.logo AS away_logo
               FROM copa_argentina_matches m
               LEFT JOIN clubs home ON home.id = m.home_club_id
               LEFT JOIN clubs away ON away.id = m.away_club_id
               WHERE m.season_number = ?
               ORDER BY m.round_number, m.match_number""",
            (season_number,),
        ).fetchall()
        rounds: dict[int, list[sqlite3.Row]] = {}
        for match in bracket_matches:
            rounds.setdefault(int(match["round_number"]), []).append(match)
        expected_round_counts: dict[int, int] = {}
        expected_match_count = len(rounds.get(1, []))
        round_number = 1
        while expected_match_count:
            expected_round_counts[round_number] = expected_match_count
            if expected_match_count == 1:
                break
            expected_match_count = (expected_match_count + 1) // 2
            round_number += 1
        final_round = max(expected_round_counts, default=0)
        bracket_round_count = max(final_round - 1, 1)
        round_labels = {
            32: "32AVOS",
            16: "16AVOS",
            8: "OCTAVOS",
            4: "CUARTOS",
            2: "SEMIFINALES",
            1: "FINAL",
        }
        bracket_rounds = []
        for round_number, expected_count in expected_round_counts.items():
            matches = list(rounds.get(round_number, []))
            for match_number in range(len(matches) + 1, expected_count + 1):
                matches.append(
                    {
                        "match_number": match_number,
                        "home_team": "Por sortear",
                        "away_team": "Por sortear",
                        "home_club_id": None,
                        "away_club_id": None,
                        "home_logo": None,
                        "away_logo": None,
                        "home_score": None,
                        "away_score": None,
                        "home_penalties": None,
                        "away_penalties": None,
                        "winner_team": None,
                        "revealed": False,
                        "is_bye": False,
                        "is_placeholder": True,
                    }
                )
            bracket_rounds.append(
                {
                "number": round_number,
                "label": round_labels.get(
                    expected_count, f"RONDA {round_number}"
                ),
                "left_matches": matches[: (len(matches) + 1) // 2],
                "right_matches": matches[(len(matches) + 1) // 2 :],
                "final_match": matches[0] if round_number == final_round else None,
                }
            )
        if progress["is_complete"] and final_round:
            final_match = rounds[final_round][0]
            career_won_copa = (
                final_match["winner_club_id"] is None
                and final_match["winner_team"] == career["club_name"]
            )
        draw_count = sum(bool(match["revealed"]) for match in current_matches)
        draw_total = len(current_matches)
        round_complete = bool(current_matches) and all(
            match["winner_team"] is not None for match in current_matches
        )
    return render_template(
        "copa_argentina.html",
        career=career,
        season_number=season_number,
        progress=progress,
        current_matches=current_matches,
        bracket_matches=bracket_matches,
        bracket_rounds=bracket_rounds,
        bracket_round_count=bracket_round_count,
        career_name=career["club_name"],
        career_won_copa=career_won_copa,
        draw_count=draw_count,
        draw_total=draw_total,
        round_complete=round_complete,
    )


def copa_action_redirect():
    endpoint = (
        "fixtures"
        if request.form.get("return_to") == "fixtures"
        else "copa_argentina"
    )
    return redirect(url_for(endpoint))


@app.post("/copa-argentina/sorteo")
def reveal_copa_argentina_draw():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        flash("El sorteo de Copa Argentina se realiza al comenzar la temporada.", "error")
        return copa_action_redirect()
    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    try:
        revealed, total = reveal_next_copa_argentina_match(db)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return copa_action_redirect()
    db.commit()
    flash(f"Cruce {revealed} de {total} revelado.", "success")
    return copa_action_redirect()


@app.post("/copa-argentina/sorteo-completo")
def reveal_all_copa_argentina_matches():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        flash("Comenzá la temporada para jugar la Copa Argentina.", "error")
        return copa_action_redirect()
    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    try:
        progress = db.execute(
            """SELECT season_number, current_round, draw_revealed, is_complete
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if progress is None:
            raise ValueError("El sorteo de la Copa Argentina todavía no está disponible.")
        if progress["is_complete"]:
            raise ValueError("La Copa Argentina de esta temporada ya terminó.")
        revealed = int(progress["draw_revealed"])
        total = db.execute(
            """SELECT COUNT(*) FROM copa_argentina_matches
               WHERE season_number = ? AND round_number = ?""",
            (progress["season_number"], progress["current_round"]),
        ).fetchone()[0]
        while revealed < total:
            revealed, total = reveal_next_copa_argentina_match(db)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return copa_action_redirect()
    db.commit()
    flash(
        f"Se sortearon los {total} cruces de esta ronda. "
        "Los partidos todavía no se jugaron: resolvelos de a uno mientras avanzás la liga.",
        "success",
    )
    return copa_action_redirect()


@app.post("/copa-argentina/jugar/<int:match_id>")
def play_copa_argentina_match_route(match_id: int):
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        flash("Comenzá la temporada para jugar la Copa Argentina.", "error")
        return copa_action_redirect()
    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    try:
        round_number, career_played, winner_team, prize_awarded = (
            play_copa_argentina_match(db, career, match_id)
        )
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return copa_action_redirect()
    db.commit()
    notice = f"Se resolvió un cruce de la ronda {round_number}: clasifica {winner_team}."
    if career_played and winner_team == career["club_name"]:
        notice += " ¡Tu equipo sigue en carrera!"
    elif career_played:
        notice += " Tu equipo quedó eliminado de la Copa."
    if prize_awarded:
        notice += f" Recibiste ${prize_awarded:,} por tu participación."
    flash(notice, "success")
    return copa_action_redirect()


@app.post("/copa-argentina/simular-ronda")
def simulate_copa_argentina_round_route():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        flash("Comenzá la temporada para jugar la Copa Argentina.", "error")
        return copa_action_redirect()
    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    try:
        progress = db.execute(
            """SELECT season_number, current_round, is_complete
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if (
            progress is None
            or int(progress["season_number"]) != current_season_number(db)
            or progress["is_complete"]
        ):
            raise ValueError("No hay una ronda pendiente de Copa Argentina para simular.")
        round_number = int(progress["current_round"])
        simulate_copa_argentina_round_automatically(db, career)
        updated_progress = db.execute(
            """SELECT current_round, is_complete, champion_team
               FROM copa_argentina_progress WHERE id = 1"""
        ).fetchone()
        if updated_progress is None:
            raise ValueError("No se pudo actualizar el avance de la Copa Argentina.")
        if updated_progress["is_complete"]:
            flash(
                f"Se simuló toda la ronda {round_number}. "
                f"¡{updated_progress['champion_team']} es campeón de la Copa Argentina!",
                "success",
            )
        else:
            flash(
                f"Se simularon todos los partidos de la ronda {round_number}. "
                f"Ya está lista la ronda {updated_progress['current_round']}.",
                "success",
            )
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return copa_action_redirect()
    db.commit()
    return copa_action_redirect()


@app.post("/copa-argentina/avanzar")
def advance_copa_argentina():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return copa_action_redirect()
    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    try:
        round_number, complete = advance_copa_argentina_round(db)
        champion = None
        prize_awarded = 0
        if complete:
            champion_match = db.execute(
                """SELECT winner_team, winner_club_id
                   FROM copa_argentina_matches
                   WHERE season_number = (
                       SELECT season_number FROM copa_argentina_progress WHERE id = 1
                   )
                   AND round_number = ?""",
                (round_number,),
            ).fetchone()
            if champion_match is None or champion_match["winner_team"] is None:
                raise ValueError("No se pudo determinar al campeón de la Copa Argentina.")
            champion = champion_match["winner_team"]
            if (
                champion_match["winner_club_id"] is None
                and champion == career["club_name"]
                and pay_copa_argentina_prize(
                    db, copa_argentina_prize(round_number, round_number, champion=True)
                )
            ):
                prize_awarded = copa_argentina_prize(
                    round_number, round_number, champion=True
                )
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return copa_action_redirect()
    db.commit()
    if complete:
        prize_message = (
            f" Premio de campeón: ${prize_awarded:,}."
            if prize_awarded
            else ""
        )
        flash(f"¡{champion} es campeón de la Copa Argentina!{prize_message}", "success")
    else:
        flash(f"Se sorteó la ronda {round_number} de la Copa Argentina.", "success")
    return copa_action_redirect()


@app.post("/torneo/jugar")
def play_tournament_round():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    active_round = db.execute(
        "SELECT current_round FROM tournament_progress WHERE id = 1"
    ).fetchone()[0]
    round_matches = db.execute(
        """SELECT id, home_club_id, away_club_id, home_score, away_score
           FROM tournament_matches WHERE round_number = ?""",
        (active_round,),
    ).fetchall()
    player_match = next(
        (
            match
            for match in round_matches
            if match["home_club_id"] is None or match["away_club_id"] is None
        ),
        None,
    )
    if not round_matches:
        db.rollback()
        flash("No se encontró la fecha actual del torneo.", "error")
        return redirect(url_for("fixtures"))
    if all(
        match["home_score"] is not None and match["away_score"] is not None
        for match in round_matches
    ):
        db.rollback()
        flash(f"La fecha {active_round} ya fue disputada. Avanzá para continuar.", "error")
        return redirect(url_for("fixtures"))

    pending = get_pending_season_decision(
        db, current_season_number(db), active_round
    )
    if pending:
        db.rollback()
        flash("Tomá la decisión pendiente antes de continuar el torneo.", "error")
        return redirect(url_for("fixtures"))

    simulate_tournament_round(
        db, career, current_season_number(db), active_round
    )
    pending = get_pending_season_decision(
        db, current_season_number(db), active_round
    )
    db.commit()
    if active_round == db.execute(
        "SELECT MAX(round_number) FROM tournament_matches"
    ).fetchone()[0]:
        standings = calculate_tournament_standings(db, career)
        setup_league_outcome(db, career, standings)
    if pending:
        flash(
            f"Fecha {active_round} disputada. Hay una decisión de temporada pendiente.",
            "success",
        )
    else:
        flash(f"Fecha {active_round} disputada. ¡Estos son los resultados!", "success")
    playoff_started = db.execute(
        "SELECT 1 FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    return redirect(
        url_for(
            "fixtures",
            live="1" if player_match else None,
            _anchor="promotion-playoff" if playoff_started else None,
        )
    )


@app.post("/torneo/avanzar")
def advance_tournament_round():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    active_round = db.execute(
        "SELECT current_round FROM tournament_progress WHERE id = 1"
    ).fetchone()[0]
    pending = get_pending_season_decision(
        db, current_season_number(db), active_round
    )
    if pending:
        db.commit()
        db.rollback()
        flash("Tomá la decisión pendiente antes de avanzar de fecha.", "error")
        return redirect(url_for("fixtures"))
    total_rounds = db.execute(
        "SELECT MAX(round_number) FROM tournament_matches"
    ).fetchone()[0]
    unplayed = db.execute(
        """SELECT COUNT(*) FROM tournament_matches
           WHERE round_number = ? AND (home_score IS NULL OR away_score IS NULL)""",
        (active_round,),
    ).fetchone()[0]
    if unplayed:
        db.rollback()
        flash("Disputá todos los partidos de esta fecha antes de avanzar.", "error")
        return redirect(url_for("fixtures"))
    copa_progress = db.execute(
        """SELECT season_number, current_round, is_complete
           FROM copa_argentina_progress WHERE id = 1"""
    ).fetchone()
    total_rounds = int(total_rounds or 0)
    if (
        total_rounds > 0
        and copa_progress
        and int(copa_progress["season_number"]) == current_season_number(db)
        and not copa_progress["is_complete"]
        and active_round
        == copa_argentina_league_matchday(
            db,
            int(copa_progress["season_number"]),
            int(copa_progress["current_round"]),
            total_rounds,
        )
    ):
        db.rollback()
        flash(
            "Terminá y avanzá la ronda de Copa Argentina de esta fecha antes de continuar.",
            "error",
        )
        return redirect(url_for("fixtures"))
    if active_round >= total_rounds:
        db.rollback()
        flash("El torneo ya terminó. ¡Revisá la tabla final!", "success")
        return redirect(url_for("fixtures"))

    db.execute(
        "UPDATE tournament_progress SET current_round = ? WHERE id = 1",
        (active_round + 1,),
    )
    db.commit()
    flash(f"Avanzaste a la fecha {active_round + 1}.", "success")
    return redirect(url_for("fixtures"))


@app.post("/torneo/simular-temporada")
def simulate_full_season():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    active_round = db.execute(
        "SELECT current_round FROM tournament_progress WHERE id = 1"
    ).fetchone()[0]
    pending = get_pending_season_decision(
        db, current_season_number(db), active_round
    )
    if pending:
        db.commit()
        db.rollback()
        flash("Elegí una decisión antes de continuar la simulación.", "error")
        return redirect(url_for("fixtures"))
    db.execute("UPDATE tournament_progress SET auto_simulation = 1 WHERE id = 1")
    try:
        result = continue_auto_simulation(db, career)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return redirect(url_for("fixtures"))
    db.commit()
    if result == "decision":
        flash(
            "La Copa Argentina avanzó junto con las fechas de liga. "
            "La simulación se detuvo ante una decisión: elegí cómo actuar para seguir.",
            "success",
        )
    else:
        flash(
            "Se simularon toda la temporada y la Copa Argentina. Revisá la tabla y los premios.",
            "success",
        )
    playoff_started = db.execute(
        "SELECT 1 FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    return redirect(
        url_for(
            "fixtures",
            _anchor="promotion-playoff" if playoff_started else None,
        )
    )


@app.post("/torneo/decision")
def make_season_decision():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    ensure_tournament_schedule(db, career)
    ensure_copa_argentina(db, career)
    db.execute("BEGIN IMMEDIATE")
    season_number = current_season_number(db)
    active_round = db.execute(
        "SELECT current_round FROM tournament_progress WHERE id = 1"
    ).fetchone()[0]
    pending = get_pending_season_decision(db, season_number, active_round)
    if pending is None:
        db.rollback()
        flash("No hay una decisión pendiente en esta fecha.", "error")
        return redirect(url_for("fixtures"))
    choice_key = request.form.get("choice", "")
    try:
        outcome = apply_season_decision(
            db, career, season_number, active_round, choice_key
        )
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return redirect(url_for("fixtures"))

    auto_simulation = bool(
        db.execute(
            "SELECT auto_simulation FROM tournament_progress WHERE id = 1"
        ).fetchone()["auto_simulation"]
    )
    if auto_simulation:
        try:
            result = continue_auto_simulation(db, career)
        except ValueError as error:
            db.rollback()
            flash(str(error), "error")
            return redirect(url_for("fixtures"))
        db.commit()
        if result == "decision":
            flash(
                f"{outcome} La Copa Argentina también avanzó. "
                "Se simularon las siguientes fechas; ya podés tomar otra decisión.",
                "success",
            )
        else:
            flash(
                f"{outcome} Se completaron la temporada y la Copa Argentina.",
                "success",
            )
    else:
        db.commit()
        flash(outcome, "success")
    playoff_started = db.execute(
        "SELECT 1 FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    return redirect(
        url_for(
            "fixtures",
            _anchor="promotion-playoff" if playoff_started else None,
        )
    )


@app.post("/torneo/playoff/jugar")
def play_promotion_playoff():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    try:
        stage = simulate_promotion_playoff_stage(db, career)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return redirect(url_for("fixtures", _anchor="promotion-playoff"))
    player_match = db.execute(
        """SELECT id FROM promotion_playoff_matches
           WHERE stage = ? AND (home_club_id IS NULL OR away_club_id IS NULL)
             AND home_score IS NOT NULL
           LIMIT 1""",
        (stage,),
    ).fetchone()
    db.commit()
    flash(f"Se disputaron los partidos de {PLAYOFF_STAGE_LABELS[stage]}.", "success")
    return redirect(
        url_for(
            "fixtures",
            playoff_live="1" if player_match else None,
            _anchor="promotion-playoff",
        )
    )


@app.post("/torneo/playoff/penal")
def take_promotion_playoff_penalty():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    action = request.form.get("action", "kick")
    direction = request.form.get("direction", "")
    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    current_stage = db.execute(
        "SELECT current_stage FROM promotion_playoff_progress WHERE id = 1"
    ).fetchone()
    if current_stage is None:
        db.rollback()
        flash("El playoff de ascenso todavía no está disponible.", "error")
        return redirect(url_for("fixtures", _anchor="promotion-playoff"))
    match = db.execute(
        """SELECT * FROM promotion_playoff_matches
           WHERE stage = ? AND (home_club_id IS NULL OR away_club_id IS NULL)
           LIMIT 1""",
        (current_stage["current_stage"],),
    ).fetchone()
    if match is None:
        db.rollback()
        flash("No se encontró el partido de tu equipo en este playoff.", "error")
        return redirect(url_for("fixtures", _anchor="promotion-playoff"))
    try:
        if action == "simulate":
            completed = False
            while not completed:
                completed = play_user_playoff_penalty(
                    db,
                    match,
                    random.choice(("left", "center", "right")),
                )
                if not completed:
                    match = db.execute(
                        "SELECT * FROM promotion_playoff_matches WHERE id = ?",
                        (match["id"],),
                    ).fetchone()
        else:
            completed = play_user_playoff_penalty(db, match, direction)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return redirect(url_for("fixtures", _anchor="promotion-playoff"))
    db.commit()
    if completed:
        updated_match = db.execute(
            """SELECT winner_team, home_penalties, away_penalties
               FROM promotion_playoff_matches WHERE id = ?""",
            (match["id"],),
        ).fetchone()
        flash(
            f"Definición terminada: {updated_match['winner_team']} gana "
            f"{updated_match['home_penalties']}–{updated_match['away_penalties']} "
            "por penales.",
            "success",
        )
    else:
        flash("Penal ejecutado. Elegí la próxima jugada de la definición.", "success")
    return redirect(
        url_for(
            "fixtures",
            penalty_live="1" if action == "simulate" else None,
            _anchor="promotion-playoff",
        )
    )


@app.post("/torneo/playoff/avanzar")
def advance_promotion_playoff_stage():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    if career["phase"] != "season":
        return redirect(url_for("market"))

    db = get_db()
    db.execute("BEGIN IMMEDIATE")
    season_number = current_season_number(db)
    try:
        next_stage = advance_promotion_playoff(db)
    except ValueError as error:
        db.rollback()
        flash(str(error), "error")
        return redirect(url_for("fixtures", _anchor="promotion-playoff"))
    db.commit()
    if next_stage == "complete":
        winner = db.execute(
            """SELECT team_name FROM tournament_awards
               WHERE award_type = ? OR award_type GLOB ?
               ORDER BY award_type LIMIT 1""",
            (
                f"playoff_promotion_{season_number}",
                f"playoff_promotion_{season_number}_club_*",
            ),
        ).fetchone()
        if winner is None:
            app.logger.error(
                "Promotion playoff completed without a promotion award for season %s",
                season_number,
            )
            flash(
                "El playoff terminó, pero no se pudo encontrar el equipo ascendido. "
                "Volvé a cargar el calendario.",
                "error",
            )
            return redirect(url_for("fixtures", _anchor="promotion-playoff"))
        if winner["team_name"] == career["club_name"]:
            if not season_is_complete(db):
                flash(
                    f"¡{career['club_name']} logró el ascenso a Primera División! "
                    "Terminá la Copa Argentina antes de iniciar la próxima temporada.",
                    "success",
                )
                return redirect(url_for("fixtures", _anchor="promotion-playoff"))
            next_season, squad_limit = start_next_season(db)
            updated_career = get_career()
            remaining_signings = db.execute(
                "SELECT COUNT(*) FROM signings"
            ).fetchone()[0]
            flash(
                f"¡{career['club_name']} logró el ascenso a Primera División! "
                f"Empezó la temporada {next_season} en {updated_career['division']}. "
                "El mercado es opcional; "
                f"podés sumar hasta {squad_limit - remaining_signings} jugadores "
                "o comenzar el torneo cuando quieras.",
                "success",
            )
            return redirect(url_for("market"))
        flash(
            f"¡{winner['team_name']} logró el ascenso a Primera División!",
            "success",
        )
    else:
        flash(f"Avanzaste a {PLAYOFF_STAGE_LABELS[next_stage]}.", "success")
    return redirect(url_for("fixtures", _anchor="promotion-playoff"))


@app.post("/temporada/nueva")
def begin_new_season():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    db = get_db()
    try:
        season_number, squad_limit = start_next_season(db)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("fixtures"))
    updated_career = get_career()
    flash(
        f"¡Comenzó la temporada {season_number}! Podés incorporar "
        f"{squad_limit - db.execute('SELECT COUNT(*) FROM signings').fetchone()[0]} jugadores "
        f"más para competir en {updated_career['division']}.",
        "success",
    )
    return redirect(url_for("market"))


@app.post("/reiniciar")
def reset():
    db = get_db()
    restore_initial_club_divisions(db)
    db.execute("DELETE FROM squad_lineup")
    db.execute("DELETE FROM player_injuries")
    db.execute("DELETE FROM promotion_playoff_progress")
    db.execute("DELETE FROM promotion_playoff_matches")
    db.execute("DELETE FROM copa_argentina_progress")
    db.execute("DELETE FROM copa_argentina_matches")
    db.execute("DELETE FROM tournament_awards")
    db.execute("DELETE FROM tournament_progress")
    db.execute("DELETE FROM tournament_matches")
    db.execute("DELETE FROM player_match_stats")
    db.execute("DELETE FROM player_development_runs")
    db.execute("DELETE FROM career")
    db.execute("DELETE FROM decisions")
    db.execute("DELETE FROM daily_options")
    db.execute("DELETE FROM season_decisions")
    db.execute("DELETE FROM signings")
    db.commit()
    flash("Carrera reiniciada. ¡Es hora de crear un nuevo club!", "success")
    return redirect(url_for("home"))


@app.post("/api/sync")
def api_sync():
    career = get_career()
    if not career:
        return redirect(url_for("home"))
    from live_football_api import LiveFootballAPIClient
    client = LiveFootballAPIClient()
    try:
        result = client.sync_to_database(DATABASE)
        flash(
            f"Sincronización completada ({result['source']}): "
            f"{result['clubs']} clubes, {result['players']} jugadores y {result['fixtures']} partidos.",
            "success",
        )
    except Exception as error:
        flash(f"Error al sincronizar con la API: {error}", "error")
    if career["phase"] == "market":
        return redirect(url_for("market"))
    return redirect(url_for("dashboard"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
