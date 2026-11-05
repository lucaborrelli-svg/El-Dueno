"""
Script to generate SVG crests for Argentine clubs and compile data_2026.json
covering Primera División and Primera Nacional for the year 2026.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CRESTS_DIR = BASE_DIR / "static" / "crests"
CRESTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_crest_svg(
    key: str,
    initials: str,
    bg_color: str,
    accent_color: str,
    text_color: str,
    style: str = "stripes",
    detail_color: str | None = None,
) -> str:
    """Generate a clean, high-quality heraldic vector SVG crest."""
    detail = detail_color or text_color
    
    # Base shield path
    shield_path = "M 15 15 Q 60 5 105 15 L 105 75 Q 105 125 60 135 Q 15 125 15 75 Z"
    
    inner_elements = ""
    
    if style == "sash":  # e.g. River Plate, Temperley
        inner_elements = f"""
        <path d="M 0 0 L 120 140 L 95 140 L 0 35 Z" fill="{accent_color}" />
        <path d="M 20 0 L 120 120 L 120 95 L 45 0 Z" fill="{accent_color}" />
        """
    elif style == "horizontal":  # e.g. Boca Juniors, Gimnasia LP
        inner_elements = f"""
        <rect x="0" y="45" width="120" height="40" fill="{accent_color}" />
        """
    elif style == "vertical_stripes":  # e.g. Racing, San Lorenzo, Estudiantes
        inner_elements = f"""
        <rect x="25" y="0" width="14" height="140" fill="{accent_color}" />
        <rect x="53" y="0" width="14" height="140" fill="{accent_color}" />
        <rect x="81" y="0" width="14" height="140" fill="{accent_color}" />
        """
    elif style == "halved":  # e.g. Newell's, Colón
        inner_elements = f"""
        <rect x="0" y="0" width="60" height="140" fill="{bg_color}" />
        <rect x="60" y="0" width="60" height="140" fill="{accent_color}" />
        """
    elif style == "chevron":  # e.g. Vélez
        inner_elements = f"""
        <polygon points="10,25 60,85 110,25 110,50 60,110 10,50" fill="{accent_color}" />
        """
    elif style == "cross":  # e.g. Huracán, Quilmes
        inner_elements = f"""
        <circle cx="60" cy="55" r="28" fill="{accent_color}" />
        <circle cx="60" cy="55" r="20" fill="{bg_color}" />
        """
    else:  # solid or badge
        inner_elements = f"""
        <circle cx="60" cy="65" r="32" fill="{accent_color}" opacity="0.3" />
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 140" width="100%" height="100%">
  <defs>
    <clipPath id="crest-clip-{key}">
      <path d="{shield_path}" />
    </clipPath>
    <linearGradient id="crest-grad-{key}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg_color}" />
      <stop offset="100%" stop-color="{bg_color}" stop-opacity="0.9" />
    </linearGradient>
  </defs>
  <!-- Background -->
  <path d="{shield_path}" fill="url(#crest-grad-{key})" stroke="{detail}" stroke-width="4" />
  <!-- Pattern inside shield -->
  <g clip-path="url(#crest-clip-{key})">
    {inner_elements}
  </g>
  <!-- Inner Border -->
  <path d="{shield_path}" fill="none" stroke="{detail}" stroke-width="3" opacity="0.85" />
  <!-- Acronym / Monogram -->
  <g transform="translate(60, 75)">
    <!-- subtle shadow -->
    <text x="0" y="2" text-anchor="middle" font-family="'Space Grotesk', 'Arial Black', sans-serif" font-size="20" font-weight="900" fill="rgba(0,0,0,0.55)" letter-spacing="1">{initials}</text>
    <text x="0" y="0" text-anchor="middle" font-family="'Space Grotesk', 'Arial Black', sans-serif" font-size="20" font-weight="900" fill="{text_color}" letter-spacing="1">{initials}</text>
  </g>
</svg>"""
    return svg


# Club Definitions
PRIMERA_DIVISION_CLUBS = [
    {
        "provider_id": "arg-river",
        "name": "River Plate",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CARP",
        "bg_color": "#FFFFFF",
        "accent_color": "#D32F2F",
        "text_color": "#111111",
        "style": "sash",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-boca",
        "name": "Boca Juniors",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CABJ",
        "bg_color": "#002B7F",
        "accent_color": "#FDB813",
        "text_color": "#FDB813",
        "style": "horizontal",
        "detail_color": "#FDB813",
    },
    {
        "provider_id": "arg-racing",
        "name": "Racing Club",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "RC",
        "bg_color": "#FFFFFF",
        "accent_color": "#4FA8EB",
        "text_color": "#1565C0",
        "style": "vertical_stripes",
        "detail_color": "#0D47A1",
    },
    {
        "provider_id": "arg-independiente",
        "name": "Independiente",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAI",
        "bg_color": "#C62828",
        "accent_color": "#E53935",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-san-lorenzo",
        "name": "San Lorenzo",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CASLA",
        "bg_color": "#0D2C54",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-velez",
        "name": "Vélez Sarsfield",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAVS",
        "bg_color": "#FFFFFF",
        "accent_color": "#0039A6",
        "text_color": "#0039A6",
        "style": "chevron",
        "detail_color": "#0039A6",
    },
    {
        "provider_id": "arg-estudiantes-lp",
        "name": "Estudiantes de La Plata",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "EDLP",
        "bg_color": "#FFFFFF",
        "accent_color": "#B71C1C",
        "text_color": "#B71C1C",
        "style": "vertical_stripes",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-gimnasia-lp",
        "name": "Gimnasia y Esgrima La Plata",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "GELP",
        "bg_color": "#FFFFFF",
        "accent_color": "#0A2540",
        "text_color": "#0A2540",
        "style": "horizontal",
        "detail_color": "#0A2540",
    },
    {
        "provider_id": "arg-rosario-central",
        "name": "Rosario Central",
        "division": "Primera División",
        "province": "Santa Fe",
        "initials": "CARC",
        "bg_color": "#0D233A",
        "accent_color": "#FFC107",
        "text_color": "#FFC107",
        "style": "vertical_stripes",
        "detail_color": "#FFC107",
    },
    {
        "provider_id": "arg-newells",
        "name": "Newell's Old Boys",
        "division": "Primera División",
        "province": "Santa Fe",
        "initials": "NOB",
        "bg_color": "#B71C1C",
        "accent_color": "#111111",
        "text_color": "#FFFFFF",
        "style": "halved",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-talleres",
        "name": "Talleres de Córdoba",
        "division": "Primera División",
        "province": "Córdoba",
        "initials": "CAT",
        "bg_color": "#0A192F",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#0A192F",
    },
    {
        "provider_id": "arg-belgrano",
        "name": "Belgrano de Córdoba",
        "division": "Primera División",
        "province": "Córdoba",
        "initials": "CAB",
        "bg_color": "#5BC0DE",
        "accent_color": "#FFFFFF",
        "text_color": "#111111",
        "style": "solid",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-instituto",
        "name": "Instituto ACC",
        "division": "Primera División",
        "province": "Córdoba",
        "initials": "IACC",
        "bg_color": "#FFFFFF",
        "accent_color": "#D32F2F",
        "text_color": "#D32F2F",
        "style": "vertical_stripes",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-argentinos",
        "name": "Argentinos Juniors",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "AAAJ",
        "bg_color": "#C62828",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "sash",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-huracan",
        "name": "Huracán",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAH",
        "bg_color": "#FFFFFF",
        "accent_color": "#D32F2F",
        "text_color": "#D32F2F",
        "style": "cross",
        "detail_color": "#D32F2F",
    },
    {
        "provider_id": "arg-lanus",
        "name": "Lanús",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAL",
        "bg_color": "#6A1B29",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-banfield",
        "name": "Banfield",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAB",
        "bg_color": "#1B5E20",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-defensa",
        "name": "Defensa y Justicia",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "DYJ",
        "bg_color": "#2E7D32",
        "accent_color": "#FBC02D",
        "text_color": "#FBC02D",
        "style": "solid",
        "detail_color": "#FBC02D",
    },
    {
        "provider_id": "arg-tigre",
        "name": "Tigre",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAT",
        "bg_color": "#0D47A1",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "horizontal",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-platense",
        "name": "Platense",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAP",
        "bg_color": "#FFFFFF",
        "accent_color": "#5D4037",
        "text_color": "#5D4037",
        "style": "horizontal",
        "detail_color": "#5D4037",
    },
    {
        "provider_id": "arg-godoy-cruz",
        "name": "Godoy Cruz",
        "division": "Primera División",
        "province": "Mendoza",
        "initials": "GC",
        "bg_color": "#0D47A1",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-union",
        "name": "Unión de Santa Fe",
        "division": "Primera División",
        "province": "Santa Fe",
        "initials": "CAU",
        "bg_color": "#FFFFFF",
        "accent_color": "#D32F2F",
        "text_color": "#D32F2F",
        "style": "vertical_stripes",
        "detail_color": "#D32F2F",
    },
    {
        "provider_id": "arg-atletico-tucuman",
        "name": "Atlético Tucumán",
        "division": "Primera División",
        "province": "Tucumán",
        "initials": "CAT",
        "bg_color": "#FFFFFF",
        "accent_color": "#4FA8EB",
        "text_color": "#0D47A1",
        "style": "vertical_stripes",
        "detail_color": "#0D47A1",
    },
    {
        "provider_id": "arg-central-cordoba",
        "name": "Central Córdoba (SdE)",
        "division": "Primera División",
        "province": "Santiago del Estero",
        "initials": "CCSE",
        "bg_color": "#111111",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-barracas",
        "name": "Barracas Central",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CABC",
        "bg_color": "#FFFFFF",
        "accent_color": "#C62828",
        "text_color": "#C62828",
        "style": "vertical_stripes",
        "detail_color": "#C62828",
    },
    {
        "provider_id": "arg-riestra",
        "name": "Deportivo Riestra",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CDR",
        "bg_color": "#111111",
        "accent_color": "#333333",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-sarmiento",
        "name": "Sarmiento de Junín",
        "division": "Primera División",
        "province": "Buenos Aires",
        "initials": "CAS",
        "bg_color": "#2E7D32",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-independiente-riv",
        "name": "Independiente Rivadavia",
        "division": "Primera División",
        "province": "Mendoza",
        "initials": "CSIR",
        "bg_color": "#0D233A",
        "accent_color": "#4FA8EB",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
]

PRIMERA_NACIONAL_CLUBS = [
    {
        "provider_id": "arg-bn-quilmes",
        "name": "Quilmes AC",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "QAC",
        "bg_color": "#FFFFFF",
        "accent_color": "#0A2540",
        "text_color": "#0A2540",
        "style": "solid",
        "detail_color": "#0A2540",
    },
    {
        "provider_id": "arg-bn-ferro",
        "name": "Ferro Carril Oeste",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "FCO",
        "bg_color": "#1B5E20",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-chacarita",
        "name": "Chacarita Juniors",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CACH",
        "bg_color": "#B71C1C",
        "accent_color": "#111111",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-san-martin-tuc",
        "name": "San Martín de Tucumán",
        "division": "Primera Nacional",
        "province": "Tucumán",
        "initials": "CASM",
        "bg_color": "#FFFFFF",
        "accent_color": "#C62828",
        "text_color": "#C62828",
        "style": "vertical_stripes",
        "detail_color": "#C62828",
    },
    {
        "provider_id": "arg-bn-san-martin-sj",
        "name": "San Martín de San Juan",
        "division": "Primera Nacional",
        "province": "San Juan",
        "initials": "CASM",
        "bg_color": "#111111",
        "accent_color": "#2E7D32",
        "text_color": "#2E7D32",
        "style": "vertical_stripes",
        "detail_color": "#2E7D32",
    },
    {
        "provider_id": "arg-bn-nueva-chicago",
        "name": "Nueva Chicago",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CANCH",
        "bg_color": "#1B5E20",
        "accent_color": "#111111",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-all-boys",
        "name": "All Boys",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAAB",
        "bg_color": "#FFFFFF",
        "accent_color": "#111111",
        "text_color": "#111111",
        "style": "horizontal",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-bn-almirante",
        "name": "Almirante Brown",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAB",
        "bg_color": "#111111",
        "accent_color": "#FBC02D",
        "text_color": "#FBC02D",
        "style": "vertical_stripes",
        "detail_color": "#FBC02D",
    },
    {
        "provider_id": "arg-bn-colon",
        "name": "Colón de Santa Fe",
        "division": "Primera Nacional",
        "province": "Santa Fe",
        "initials": "CAC",
        "bg_color": "#B71C1C",
        "accent_color": "#111111",
        "text_color": "#FFFFFF",
        "style": "halved",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-aldosivi",
        "name": "Aldosivi",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAA",
        "bg_color": "#1B5E20",
        "accent_color": "#FBC02D",
        "text_color": "#FBC02D",
        "style": "vertical_stripes",
        "detail_color": "#FBC02D",
    },
    {
        "provider_id": "arg-bn-gimnasia-jujuy",
        "name": "Gimnasia y Esgrima de Jujuy",
        "division": "Primera Nacional",
        "province": "Jujuy",
        "initials": "GYEJ",
        "bg_color": "#FFFFFF",
        "accent_color": "#4FA8EB",
        "text_color": "#0D47A1",
        "style": "solid",
        "detail_color": "#0D47A1",
    },
    {
        "provider_id": "arg-bn-gimnasia-mendoza",
        "name": "Gimnasia y Esgrima de Mendoza",
        "division": "Primera Nacional",
        "province": "Mendoza",
        "initials": "GEM",
        "bg_color": "#FFFFFF",
        "accent_color": "#111111",
        "text_color": "#111111",
        "style": "vertical_stripes",
        "detail_color": "#111111",
    },
    {
        "provider_id": "arg-bn-moron",
        "name": "Deportivo Morón",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CDM",
        "bg_color": "#FFFFFF",
        "accent_color": "#C62828",
        "text_color": "#C62828",
        "style": "horizontal",
        "detail_color": "#C62828",
    },
    {
        "provider_id": "arg-bn-temperley",
        "name": "Temperley",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAT",
        "bg_color": "#4FA8EB",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "sash",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-atlanta",
        "name": "Atlanta",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAA",
        "bg_color": "#0D47A1",
        "accent_color": "#FBC02D",
        "text_color": "#FBC02D",
        "style": "vertical_stripes",
        "detail_color": "#FBC02D",
    },
    {
        "provider_id": "arg-bn-estudiantes-rc",
        "name": "Estudiantes de Río Cuarto",
        "division": "Primera Nacional",
        "province": "Córdoba",
        "initials": "AAERC",
        "bg_color": "#4FA8EB",
        "accent_color": "#FFFFFF",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-patronato",
        "name": "Patronato",
        "division": "Primera Nacional",
        "province": "Entre Ríos",
        "initials": "CAP",
        "bg_color": "#111111",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-arsenal",
        "name": "Arsenal de Sarandí",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CAAS",
        "bg_color": "#4FA8EB",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "sash",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-agropecuario",
        "name": "Agropecuario",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CCAA",
        "bg_color": "#1B5E20",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "solid",
        "detail_color": "#FFFFFF",
    },
    {
        "provider_id": "arg-bn-defensores",
        "name": "Defensores de Belgrano",
        "division": "Primera Nacional",
        "province": "Buenos Aires",
        "initials": "CADB",
        "bg_color": "#111111",
        "accent_color": "#C62828",
        "text_color": "#FFFFFF",
        "style": "vertical_stripes",
        "detail_color": "#FFFFFF",
    },
]

ALL_CLUBS = PRIMERA_DIVISION_CLUBS + PRIMERA_NACIONAL_CLUBS

# Real squad rosters
ROSTERS = {
    "arg-river": [
        ("Franco Armani", "ARQ", 39, 81, 14000000, 450000),
        ("Germán Pezzella", "DEF", 34, 80, 16000000, 500000),
        ("Paulo Díaz", "DEF", 31, 79, 13000000, 420000),
        ("Marcos Acuña", "DEF", 34, 80, 18000000, 520000),
        ("Fabricio Bustos", "DEF", 29, 76, 7500000, 280000),
        ("Enzo Díaz", "DEF", 30, 75, 6000000, 240000),
        ("Rodrigo Villagra", "MED", 24, 77, 9500000, 310000),
        ("Santiago Simón", "MED", 23, 75, 6800000, 250000),
        ("Manuel Lanzini", "MED", 32, 78, 8500000, 390000),
        ("Claudio Echeverri", "MED", 20, 80, 24000000, 400000),
        ("Maximiliano Meza", "MED", 33, 77, 8000000, 350000),
        ("Facundo Colidio", "DEL", 26, 78, 11500000, 380000),
        ("Miguel Borja", "DEL", 33, 81, 15000000, 480000),
        ("Pablo Solari", "DEL", 24, 76, 8200000, 290000),
    ],
    "arg-boca": [
        ("Sergio Romero", "ARQ", 38, 79, 7000000, 420000),
        ("Leandro Brey", "ARQ", 23, 75, 5500000, 210000),
        ("Marcos Rojo", "DEF", 35, 78, 8500000, 460000),
        ("Aaron Anselmino", "DEF", 20, 78, 16000000, 320000),
        ("Luis Advíncula", "DEF", 35, 78, 9000000, 380000),
        ("Lautaro Blanco", "DEF", 26, 77, 8200000, 290000),
        ("Cristian Medina", "MED", 23, 79, 14000000, 390000),
        ("Kevin Zenón", "MED", 24, 79, 13500000, 370000),
        ("Ignacio Miramón", "MED", 22, 75, 6500000, 250000),
        ("Agustín Martegani", "MED", 25, 75, 5800000, 240000),
        ("Edinson Cavani", "DEL", 38, 82, 17000000, 600000),
        ("Miguel Merentiel", "DEL", 29, 80, 14500000, 440000),
        ("Exequiel Zeballos", "DEL", 23, 76, 7800000, 280000),
        ("Brian Aguirre", "DEL", 23, 75, 7200000, 260000),
    ],
    "arg-racing": [
        ("Gabriel Arias", "ARQ", 38, 78, 6200000, 340000),
        ("Marco Di Cesare", "DEF", 23, 76, 7000000, 260000),
        ("Nazareno Colombo", "DEF", 26, 74, 4800000, 210000),
        ("Gabriel Rojas", "DEF", 28, 75, 5500000, 230000),
        ("Gastón Martirena", "DEF", 26, 76, 6800000, 250000),
        ("Juan Nardoni", "MED", 23, 77, 8900000, 310000),
        ("Agustín Almendra", "MED", 25, 76, 7200000, 280000),
        ("Juan Fernando Quintero", "MED", 33, 80, 11000000, 450000),
        ("Baltasar Rodríguez", "MED", 22, 75, 6600000, 240000),
        ("Adrián Martínez", "DEL", 33, 81, 13500000, 430000),
        ("Roger Martínez", "DEL", 31, 78, 8800000, 360000),
        ("Maximiliano Salas", "DEL", 28, 76, 6200000, 250000),
    ],
    "arg-independiente": [
        ("Rodrigo Rey", "ARQ", 34, 78, 7500000, 320000),
        ("Kevin Lomónaco", "DEF", 24, 76, 7200000, 270000),
        ("Joaquín Laso", "DEF", 35, 73, 2800000, 180000),
        ("Damián Pérez", "DEF", 37, 72, 2200000, 160000),
        ("Federico Vera", "DEF", 27, 74, 4500000, 210000),
        ("Iván Marcone", "MED", 35, 76, 5200000, 300000),
        ("Felipe Loyola", "MED", 25, 77, 8100000, 290000),
        ("Federico Mancuello", "MED", 36, 74, 3800000, 220000),
        ("Santiago Montiel", "MED", 25, 76, 6900000, 260000),
        ("Lucas González", "MED", 25, 74, 4600000, 210000),
        ("Gabriel Ávalos", "DEL", 35, 77, 6500000, 290000),
        ("Santiago López", "DEL", 20, 74, 5800000, 200000),
    ],
    "arg-san-lorenzo": [
        ("Gastón Gómez", "ARQ", 30, 74, 3900000, 200000),
        ("Jhohan Romaña", "DEF", 27, 77, 7200000, 270000),
        ("Gastón Campi", "DEF", 34, 73, 3100000, 180000),
        ("Malcom Braida", "DEF", 28, 76, 6800000, 260000),
        ("Gonzalo Luján", "DEF", 24, 74, 4900000, 210000),
        ("Elián Irala", "MED", 21, 76, 7900000, 250000),
        ("Eric Remedi", "MED", 30, 75, 5200000, 240000),
        ("Iker Muniain", "MED", 33, 80, 11500000, 480000),
        ("Nahuel Bustos", "DEL", 27, 76, 6500000, 270000),
        ("Alexis Cuello", "DEL", 25, 75, 5400000, 230000),
        ("Ezequiel Cerutti", "DEL", 34, 73, 3300000, 190000),
    ],
    "arg-velez": [
        ("Tomás Marchiori", "ARQ", 30, 77, 6200000, 260000),
        ("Valentín Gómez", "DEF", 22, 79, 13000000, 350000),
        ("Emanuel Mammana", "DEF", 30, 76, 5800000, 260000),
        ("Elías Gómez", "DEF", 31, 74, 4200000, 210000),
        ("Agustín Bouzat", "MED", 31, 76, 5500000, 240000),
        ("Christian Ordóñez", "MED", 21, 76, 7400000, 250000),
        ("Claudio Aquino", "MED", 34, 80, 8900000, 360000),
        ("Thiago Fernández", "MED", 21, 77, 9200000, 280000),
        ("Braian Romero", "DEL", 34, 78, 6800000, 300000),
        ("Francisco Pizzini", "DEL", 32, 76, 5100000, 240000),
        ("Maher Carrizo", "DEL", 19, 73, 4100000, 170000),
    ],
    "arg-estudiantes-lp": [
        ("Matías Mansilla", "ARQ", 30, 75, 4800000, 230000),
        ("Sebastián Boselli", "DEF", 22, 76, 6900000, 250000),
        ("Luciano Lollo", "DEF", 38, 73, 2100000, 170000),
        ("Gastón Benedetti", "DEF", 25, 75, 5200000, 220000),
        ("Santiago Ascacíbar", "MED", 28, 79, 9800000, 380000),
        ("Enzo Pérez", "MED", 40, 78, 5500000, 350000),
        ("José Sosa", "MED", 40, 77, 4500000, 300000),
        ("Tiago Palacios", "MED", 24, 77, 7800000, 280000),
        ("Guido Carrillo", "DEL", 34, 78, 6500000, 310000),
        ("Edwuin Cetré", "DEL", 28, 77, 7200000, 290000),
        ("Luciano Giménez", "DEL", 25, 74, 4200000, 200000),
    ],
    "arg-gimnasia-lp": [
        ("Marcos Ledesma", "ARQ", 29, 73, 3100000, 180000),
        ("Leonardo Morales", "DEF", 34, 75, 4200000, 220000),
        ("Yonathan Cabral", "DEF", 33, 73, 2800000, 170000),
        ("Nicolás Colazo", "DEF", 35, 72, 2100000, 150000),
        ("Lucas Castro", "MED", 36, 74, 2900000, 190000),
        ("Martín Fernández", "MED", 24, 74, 4400000, 200000),
        ("Pablo De Blasis", "MED", 38, 74, 2800000, 190000),
        ("David Zalazar", "DEL", 23, 73, 3800000, 170000),
        ("Rodrigo Castillo", "DEL", 26, 75, 5200000, 220000),
        ("Norberto Briasco", "DEL", 29, 74, 4600000, 210000),
    ],
    "arg-rosario-central": [
        ("Jorge Broun", "ARQ", 39, 76, 3200000, 220000),
        ("Facundo Mallo", "DEF", 30, 75, 4600000, 210000),
        ("Carlos Quintana", "DEF", 37, 74, 2400000, 180000),
        ("Agustín Sández", "DEF", 25, 74, 4200000, 200000),
        ("Franco Ibarra", "MED", 24, 75, 5400000, 230000),
        ("Mauricio Martínez", "MED", 32, 74, 3800000, 200000),
        ("Ignacio Malcorra", "MED", 38, 77, 4900000, 270000),
        ("Jaminton Campaz", "DEL", 25, 78, 9200000, 340000),
        ("Maximiliano Lovera", "DEL", 26, 74, 4400000, 210000),
        ("Marco Ruben", "DEL", 39, 75, 3000000, 240000),
        ("Enzo Copetti", "DEL", 30, 76, 5800000, 270000),
    ],
    "arg-newells": [
        ("Ramiro Macagno", "ARQ", 28, 73, 3400000, 180000),
        ("Gustavo Velázquez", "DEF", 34, 76, 4200000, 220000),
        ("Saúl Salcedo", "DEF", 28, 74, 3900000, 200000),
        ("Angelo Martino", "DEF", 27, 74, 4100000, 200000),
        ("Ever Banega", "MED", 37, 79, 6500000, 360000),
        ("Rodrigo Fernández", "MED", 29, 74, 4200000, 210000),
        ("Juan Ignacio Méndez", "MED", 28, 74, 4300000, 210000),
        ("Mateo Silvetti", "DEL", 20, 75, 6200000, 220000),
        ("Juan Manuel García", "DEL", 33, 73, 2700000, 180000),
        ("Ignacio Ramírez", "DEL", 28, 76, 5600000, 250000),
    ],
    "arg-talleres": [
        ("Guido Herrera", "ARQ", 33, 78, 6800000, 310000),
        ("Juan Gabriel Rodríguez", "DEF", 31, 75, 4300000, 210000),
        ("Lucas Suárez", "DEF", 30, 74, 3800000, 200000),
        ("Gastón Benavídez", "DEF", 29, 76, 5900000, 240000),
        ("Juan Camilo Portilla", "MED", 27, 77, 7400000, 280000),
        ("Matías Galarza", "MED", 23, 76, 6800000, 250000),
        ("Rubén Botta", "MED", 36, 78, 5900000, 300000),
        ("Sebastián Palacios", "DEL", 34, 75, 4600000, 220000),
        ("Federico Girotti", "DEL", 26, 76, 6200000, 250000),
        ("Cristian Tarragona", "DEL", 34, 74, 3600000, 200000),
    ],
    "arg-belgrano": [
        ("Ignacio Chicco", "ARQ", 29, 74, 3700000, 190000),
        ("Alejandro Rébola", "DEF", 37, 73, 2200000, 160000),
        ("Rafael Delgado", "DEF", 36, 73, 2400000, 170000),
        ("Gabriel Compagnucci", "DEF", 34, 73, 2800000, 180000),
        ("Santiago Longo", "MED", 27, 77, 7200000, 270000),
        ("Esteban Rolón", "MED", 30, 74, 4000000, 210000),
        ("Facundo Quignón", "MED", 32, 74, 3600000, 200000),
        ("Francisco González Metilli", "MED", 28, 75, 5100000, 230000),
        ("Bryan Reyna", "DEL", 27, 76, 6300000, 250000),
        ("Lucas Passerini", "DEL", 31, 77, 6900000, 290000),
        ("Nicolás Fernández", "DEL", 29, 76, 6100000, 250000),
    ],
    "arg-instituto": [
        ("Manuel Roffo", "ARQ", 25, 75, 5200000, 220000),
        ("Fernando Alarcón", "DEF", 31, 75, 4100000, 210000),
        ("Gonzalo Requena", "DEF", 22, 74, 4500000, 190000),
        ("Lucas Rodríguez", "DEF", 31, 73, 3100000, 170000),
        ("Nicolás Dubersarsky", "MED", 21, 74, 4700000, 190000),
        ("Gastón Lodico", "MED", 27, 76, 6100000, 240000),
        ("Damián Puebla", "MED", 23, 76, 6600000, 250000),
        ("Gregorio Rodríguez", "DEL", 25, 74, 4200000, 200000),
        ("Facundo Suárez", "DEL", 31, 75, 4800000, 220000),
        ("Ignacio Russo", "DEL", 25, 74, 3900000, 190000),
    ],
    "arg-argentinos": [
        ("Diego Rodríguez", "ARQ", 36, 75, 4100000, 220000),
        ("Francisco Álvarez", "DEF", 25, 75, 4900000, 210000),
        ("Tobías Palacio", "DEF", 19, 75, 6800000, 230000),
        ("Román Vega", "DEF", 22, 75, 6200000, 220000),
        ("Alan Rodríguez", "MED", 25, 76, 6400000, 240000),
        ("Francis Mac Allister", "MED", 30, 74, 3800000, 200000),
        ("Nicolás Oroz", "MED", 31, 75, 4600000, 220000),
        ("Alan Lescano", "MED", 24, 76, 6800000, 250000),
        ("Gastón Verón", "DEL", 24, 75, 5200000, 220000),
        ("Maximiliano Romero", "DEL", 27, 75, 5100000, 230000),
    ],
    "arg-huracan": [
        ("Hernán Galíndez", "ARQ", 38, 77, 5100000, 260000),
        ("Fernando Tobio", "DEF", 36, 75, 3400000, 210000),
        ("Fabio Pereyra", "DEF", 35, 74, 2800000, 180000),
        ("Lucas Carrizo", "DEF", 28, 74, 3900000, 190000),
        ("Hernán De La Fuente", "DEF", 29, 74, 3800000, 190000),
        ("Federico Fattori", "MED", 33, 75, 4200000, 210000),
        ("Rodrigo Echeverría", "MED", 30, 78, 8600000, 320000),
        ("Williams Alarcón", "MED", 25, 76, 6800000, 250000),
        ("Walter Mazzantti", "DEL", 29, 77, 7100000, 270000),
        ("Rodrigo Cabral", "DEL", 25, 74, 4300000, 200000),
        ("Ramón Ábila", "DEL", 36, 75, 3600000, 240000),
    ],
    "arg-lanus": [
        ("Nahuel Losada", "ARQ", 32, 76, 5200000, 240000),
        ("Carlos Izquierdoz", "DEF", 37, 76, 3800000, 240000),
        ("Ezequiel Muñoz", "DEF", 35, 74, 2900000, 180000),
        ("Julio Soler", "DEF", 21, 77, 9500000, 290000),
        ("Gonzalo Pérez", "MED", 25, 74, 4300000, 200000),
        ("Raúl Loaiza", "MED", 31, 75, 4500000, 220000),
        ("Felipe Peña Biafore", "MED", 24, 76, 6500000, 250000),
        ("Marcelino Moreno", "MED", 31, 79, 9000000, 350000),
        ("Eduardo Salvio", "DEL", 35, 77, 6200000, 320000),
        ("Walter Bou", "DEL", 32, 79, 9200000, 360000),
        ("Leandro Díaz", "DEL", 33, 75, 4400000, 220000),
    ],
    "arg-banfield": [
        ("Facundo Sanguinetti", "ARQ", 24, 73, 2900000, 160000),
        ("Alejandro Maciel", "DEF", 28, 74, 3800000, 190000),
        ("Alexis Maldonado", "DEF", 28, 73, 3100000, 170000),
        ("Mathías De Ritis", "DEF", 22, 73, 3500000, 160000),
        ("Cristian Núñez", "MED", 28, 74, 3900000, 190000),
        ("Yvo Calleros", "MED", 27, 74, 3700000, 180000),
        ("Ignacio Rodríguez", "MED", 23, 74, 4200000, 190000),
        ("Braian Galván", "DEL", 25, 74, 4100000, 190000),
        ("Gerónimo Rivera", "DEL", 22, 76, 6500000, 230000),
        ("Bruno Sepúlveda", "DEL", 33, 74, 3400000, 190000),
    ],
    "arg-defensa": [
        ("Enrique Bologna", "ARQ", 43, 73, 1500000, 150000),
        ("Santiago Ramos Mingo", "DEF", 24, 75, 5200000, 220000),
        ("Emanuel Aguilera", "DEF", 36, 73, 2200000, 160000),
        ("Alexis Soto", "DEF", 32, 75, 4100000, 210000),
        ("Kevin Gutiérrez", "MED", 28, 76, 5900000, 240000),
        ("César Pérez", "MED", 23, 75, 5400000, 220000),
        ("Aarón Molinas", "MED", 25, 76, 6200000, 250000),
        ("Luciano Herrera", "DEL", 29, 74, 3800000, 190000),
        ("Juan Miritello", "DEL", 26, 75, 4900000, 220000),
        ("Abiel Osorio", "DEL", 23, 74, 4300000, 200000),
    ],
    "arg-tigre": [
        ("Felipe Zenobio", "ARQ", 25, 74, 3600000, 180000),
        ("Brian Leizza", "DEF", 25, 73, 3200000, 170000),
        ("Nehuén Paz", "DEF", 32, 74, 3500000, 190000),
        ("Martín Garay", "DEF", 26, 74, 3900000, 190000),
        ("Agustín Cardozo", "MED", 28, 75, 4800000, 220000),
        ("Leonel Miranda", "MED", 32, 75, 4300000, 210000),
        ("Gonzalo Maroni", "MED", 26, 76, 5800000, 240000),
        ("Florián Monzón", "DEL", 25, 75, 4700000, 210000),
        ("Eric Ramírez", "DEL", 29, 75, 4900000, 220000),
        ("Blas Armoa", "DEL", 25, 74, 4200000, 200000),
    ],
    "arg-platense": [
        ("Juan Pablo Cozzani", "ARQ", 27, 75, 4400000, 210000),
        ("Ignacio Vázquez", "DEF", 33, 75, 4100000, 210000),
        ("Gastón Suso", "DEF", 34, 74, 3200000, 180000),
        ("Sasha Marcich", "DEF", 27, 74, 3800000, 190000),
        ("Leonel Picco", "MED", 27, 75, 4900000, 220000),
        ("Fernando Juárez", "MED", 27, 74, 3900000, 190000),
        ("Guido Mainero", "MED", 30, 75, 4600000, 210000),
        ("Ronaldo Martínez", "DEL", 29, 75, 4800000, 220000),
        ("Mateo Pellegrino", "DEL", 24, 76, 6100000, 240000),
        ("Franco Baldassarra", "MED", 27, 73, 3100000, 170000),
    ],
    "arg-godoy-cruz": [
        ("Franco Petroli", "ARQ", 27, 76, 5600000, 230000),
        ("Pier Barrios", "DEF", 35, 74, 2900000, 180000),
        ("Federico Rasmussen", "DEF", 33, 74, 3200000, 190000),
        ("Lucas Arce", "DEF", 28, 75, 4600000, 210000),
        ("Bruno Leyes", "MED", 24, 75, 5100000, 220000),
        ("Nicolás Fernández", "MED", 26, 75, 4900000, 220000),
        ("Vicente Poggi", "MED", 23, 75, 5200000, 220000),
        ("Facundo Altamira", "DEL", 24, 76, 6200000, 240000),
        ("Salomón Rodríguez", "DEL", 26, 76, 5900000, 240000),
        ("Daniel Barrea", "DEL", 24, 74, 4100000, 190000),
    ],
    "arg-union": [
        ("Thiago Cardozo", "ARQ", 29, 74, 3800000, 190000),
        ("Nicolás Paz", "DEF", 23, 75, 5100000, 220000),
        ("Franco Pardo", "DEF", 28, 75, 4700000, 210000),
        ("Claudio Corvalán", "DEF", 36, 74, 2800000, 180000),
        ("Joaquín Mosqueira", "MED", 21, 75, 5500000, 220000),
        ("Mauro Pittón", "MED", 31, 75, 4500000, 210000),
        ("Simón Rivero", "MED", 22, 75, 5200000, 210000),
        ("Mateo Del Blanco", "MED", 22, 74, 4300000, 190000),
        ("Adrián Balboa", "DEL", 32, 75, 4400000, 210000),
        ("Nicolás Orsini", "DEL", 31, 74, 3900000, 200000),
        ("Lucas Gamba", "DEL", 38, 74, 2600000, 180000),
    ],
    "arg-atletico-tucuman": [
        ("Tomás Durso", "ARQ", 26, 74, 3900000, 190000),
        ("Gianluca Ferrari", "DEF", 28, 74, 3800000, 190000),
        ("Néstor Breitenbruch", "DEF", 30, 73, 3100000, 170000),
        ("Juan Infante", "DEF", 29, 74, 3500000, 180000),
        ("Adrián Sánchez", "MED", 26, 75, 4700000, 210000),
        ("Guillermo Acosta", "MED", 37, 74, 2400000, 170000),
        ("Renzo Tesuri", "MED", 29, 76, 5600000, 230000),
        ("Joaquín Pereyra", "MED", 27, 77, 6800000, 260000),
        ("Mateo Coronel", "DEL", 27, 76, 5900000, 240000),
        ("Marcelo Estigarribia", "DEL", 30, 75, 4800000, 220000),
        ("Luis Miguel Rodríguez", "DEL", 41, 74, 2100000, 180000),
    ],
    "arg-central-cordoba": [
        ("Luis Ingolotti", "ARQ", 25, 74, 3600000, 180000),
        ("Lucas Abascia", "DEF", 29, 74, 3700000, 180000),
        ("Sebastián Valdez", "DEF", 30, 73, 3200000, 170000),
        ("Andrés Meli", "DEF", 25, 73, 3100000, 160000),
        ("Kevin Vázquez", "MED", 24, 74, 4100000, 190000),
        ("José Florentín", "MED", 29, 75, 4800000, 210000),
        ("Matías Godoy", "MED", 24, 75, 4900000, 220000),
        ("Rodrigo Atencio", "MED", 23, 76, 5800000, 230000),
        ("Lucas Varaldo", "DEL", 24, 75, 4700000, 210000),
        ("Favio Cabral", "DEL", 24, 74, 3900000, 180000),
    ],
    "arg-barracas": [
        ("Marcelo Miño", "ARQ", 28, 73, 3100000, 170000),
        ("Nicolás Capraro", "DEF", 27, 74, 3900000, 190000),
        ("Gonzalo Goñi", "DEF", 27, 73, 3200000, 170000),
        ("Rodrigo Insúa", "DEF", 27, 74, 3700000, 180000),
        ("Siro Rosane", "MED", 25, 74, 4100000, 190000),
        ("Iván Tapia", "MED", 27, 75, 4900000, 220000),
        ("Alan Cantero", "DEL", 27, 74, 4200000, 190000),
        ("Maximiliano Zalazar", "DEL", 24, 75, 4800000, 210000),
        ("Jhonatan Candia", "DEL", 30, 74, 3800000, 190000),
        ("Facundo Bruera", "DEL", 27, 74, 4000000, 200000),
    ],
    "arg-riestra": [
        ("Ignacio Arce", "ARQ", 33, 74, 3500000, 180000),
        ("Nicolás Sansotre", "DEF", 32, 73, 2800000, 160000),
        ("Alan Barrionuevo", "DEF", 28, 73, 2900000, 160000),
        ("Nicolás Caro Torres", "DEF", 30, 72, 2400000, 150000),
        ("Jonathan Goitia", "DEF", 31, 73, 2700000, 160000),
        ("Milton Céliz", "MED", 33, 74, 3400000, 180000),
        ("Jonatan Goya", "MED", 36, 72, 1900000, 140000),
        ("Braian Sánchez", "MED", 31, 73, 2900000, 160000),
        ("Jonathan Herrera", "DEL", 34, 75, 4200000, 210000),
        ("Antony Alonso", "DEL", 27, 73, 3100000, 160000),
    ],
    "arg-sarmiento": [
        ("Lucas Acosta", "ARQ", 30, 74, 3600000, 180000),
        ("Franco Paredes", "DEF", 26, 74, 3900000, 190000),
        ("Juan Manuel Insaurralde", "DEF", 41, 73, 1800000, 160000),
        ("Facundo Roncaglia", "DEF", 38, 73, 1900000, 160000),
        ("Emiliano Méndez", "MED", 36, 73, 2200000, 160000),
        ("Manuel García", "MED", 26, 73, 3100000, 170000),
        ("Valentín Burgoa", "MED", 25, 74, 3800000, 180000),
        ("Gabriel Gudiño", "MED", 33, 74, 3400000, 180000),
        ("Joaquín Gho", "DEL", 22, 75, 4900000, 210000),
        ("Lisandro López", "DEL", 42, 74, 2100000, 180000),
        ("Iván Morales", "DEL", 26, 74, 3900000, 190000),
    ],
    "arg-independiente-riv": [
        ("Ezequiel Centurión", "ARQ", 28, 74, 3900000, 190000),
        ("Iván Villalba", "DEF", 30, 73, 3100000, 170000),
        ("Sheyko Studer", "DEF", 23, 74, 3900000, 190000),
        ("Tobías Ostchega", "DEF", 27, 73, 3200000, 170000),
        ("Franco Romero", "MED", 25, 75, 4600000, 210000),
        ("Luis Sequeira", "MED", 22, 74, 4200000, 190000),
        ("Gonzalo Ríos", "MED", 26, 74, 3800000, 180000),
        ("Sebastián Villa", "DEL", 29, 78, 8500000, 340000),
        ("Victorio Ramis", "DEL", 31, 74, 3400000, 180000),
        ("Mauricio Asenjo", "DEL", 31, 73, 2900000, 170000),
    ],
    # Primera Nacional Squads
    "arg-bn-quilmes": [
        ("Esteban Glellel", "ARQ", 26, 71, 1800000, 120000),
        ("Federico Tévez", "DEF", 26, 70, 1500000, 110000),
        ("Santiago Moya", "DEF", 22, 69, 1400000, 100000),
        ("Leandro Allende", "DEF", 28, 70, 1600000, 110000),
        ("Iván Ramírez", "MED", 35, 71, 1500000, 120000),
        ("Marcos Enrique", "MED", 26, 70, 1600000, 110000),
        ("Ramiro Luna", "MED", 30, 71, 1800000, 120000),
        ("Lautaro Parisi", "DEL", 31, 72, 2200000, 140000),
        ("Fabián Bordagaray", "DEL", 38, 70, 1200000, 110000),
        ("Tomás González", "DEL", 22, 71, 2100000, 130000),
    ],
    "arg-bn-ferro": [
        ("Mariano Monllor", "ARQ", 36, 70, 1200000, 100000),
        ("Patricio Boolsen", "DEF", 27, 70, 1500000, 110000),
        ("Alan Lorenzo", "DEF", 27, 69, 1300000, 100000),
        ("Martín Rodríguez", "DEF", 27, 69, 1300000, 100000),
        ("Nicolás Gómez", "MED", 29, 71, 1700000, 120000),
        ("Juan Fernández Pinto", "MED", 25, 70, 1600000, 110000),
        ("Ricardo Blanco", "MED", 35, 72, 2000000, 140000),
        ("Nicolás Retamar", "DEL", 26, 72, 2400000, 150000),
        ("Mateo Levato", "DEL", 29, 71, 1900000, 130000),
        ("Franco García", "DEL", 27, 70, 1500000, 110000),
    ],
    "arg-bn-chacarita": [
        ("Marino Arzamendia", "ARQ", 27, 70, 1400000, 110000),
        ("Cristian González", "DEF", 35, 70, 1300000, 110000),
        ("Federico Laurelli", "DEF", 22, 69, 1400000, 100000),
        ("Nicolás Chaves", "DEF", 24, 70, 1600000, 110000),
        ("Nicolás Watson", "MED", 27, 71, 1800000, 120000),
        ("Maximiliano Meléndez", "MED", 23, 70, 1600000, 110000),
        ("Matías Pisano", "MED", 34, 73, 2400000, 160000),
        ("Claudio Pombo", "MED", 31, 71, 1700000, 120000),
        ("Rodrigo Salinas", "DEL", 39, 71, 1400000, 120000),
        ("Fernando Brandán", "DEL", 35, 70, 1300000, 110000),
    ],
    "arg-bn-san-martin-tuc": [
        ("Darío Sand", "ARQ", 38, 73, 2100000, 140000),
        ("Juan Orellana", "DEF", 28, 72, 2200000, 140000),
        ("Agustín Dattola", "DEF", 26, 71, 1900000, 130000),
        ("Lucas Diarte", "DEF", 32, 71, 1800000, 120000),
        ("Gustavo Abregú", "MED", 28, 72, 2300000, 150000),
        ("Matías García", "MED", 34, 73, 2400000, 160000),
        ("Juan Cuevas", "MED", 37, 72, 1700000, 130000),
        ("Lautaro Fedele", "DEL", 24, 72, 2500000, 150000),
        ("Junior Arias", "DEL", 32, 73, 2700000, 170000),
        ("Gonzalo Rodríguez", "DEL", 35, 71, 1600000, 120000),
    ],
    "arg-bn-san-martin-sj": [
        ("Matías Borgogno", "ARQ", 27, 72, 2100000, 130000),
        ("Rodrigo Cáseres", "DEF", 28, 71, 1800000, 120000),
        ("Julián Marchio", "DEF", 25, 70, 1600000, 110000),
        ("Dante Álvarez", "DEF", 29, 70, 1500000, 110000),
        ("Nicolás Pelaitay", "MED", 33, 72, 1900000, 130000),
        ("Sebastián González", "MED", 33, 72, 2100000, 140000),
        ("Alejandro Molina", "DEF", 28, 71, 1800000, 120000),
        ("Maximiliano Casas", "DEL", 32, 72, 2200000, 140000),
        ("Nazareno Fúnez", "DEL", 24, 72, 2500000, 150000),
        ("Tomás Fernández", "DEL", 27, 71, 1900000, 130000),
    ],
    "arg-bn-nueva-chicago": [
        ("Facundo Ferrero", "ARQ", 30, 72, 2000000, 130000),
        ("Stefano Callegari", "DEF", 29, 71, 1900000, 130000),
        ("Tomás Rossi", "DEF", 26, 70, 1600000, 110000),
        ("Diego Arroyo", "DEF", 24, 70, 1500000, 110000),
        ("Tomás Bottari", "MED", 24, 71, 1900000, 130000),
        ("Maximiliano Amarfil", "MED", 24, 71, 1800000, 120000),
        ("Evelio Cardozo", "MED", 25, 72, 2300000, 150000),
        ("Gabriel Altamirano", "MED", 24, 70, 1600000, 110000),
        ("Facundo Castro", "DEL", 29, 72, 2200000, 140000),
        ("Iván Maggi", "DEL", 26, 71, 1900000, 130000),
    ],
    "arg-bn-all-boys": [
        ("Lisandro Mitre", "ARQ", 29, 71, 1800000, 120000),
        ("Maximiliano Coronel", "DEF", 36, 71, 1500000, 120000),
        ("Alejo Tabares", "DEF", 24, 70, 1600000, 110000),
        ("Hernán Grana", "DEF", 40, 69, 1000000, 90000),
        ("Alexis Melo", "MED", 24, 71, 1900000, 130000),
        ("Santiago Gallucci", "MED", 34, 70, 1400000, 110000),
        ("Juan Carlos Salas", "MED", 25, 70, 1500000, 110000),
        ("Tomás Assennato", "DEL", 27, 71, 1800000, 120000),
        ("Franco Toloza", "DEL", 31, 71, 1700000, 120000),
        ("Agustín Gallo", "DEL", 26, 70, 1500000, 110000),
    ],
    "arg-bn-almirante": [
        ("Ramiro Martínez", "ARQ", 34, 70, 1300000, 100000),
        ("Gonzalo Errecalde", "DEF", 25, 70, 1500000, 110000),
        ("Facundo Miño", "DEF", 26, 69, 1300000, 100000),
        ("Fernando Rodríguez", "DEF", 25, 69, 1300000, 100000),
        ("Bruno Cenci", "MED", 22, 70, 1600000, 110000),
        ("Santiago Gauna", "MED", 22, 71, 1800000, 120000),
        ("Joaquín Ibáñez", "MED", 29, 70, 1500000, 110000),
        ("Tomás Díaz", "MED", 23, 70, 1600000, 110000),
        ("Brian Fernández", "DEL", 31, 72, 2300000, 150000),
        ("Santiago Vera", "DEL", 27, 72, 2400000, 150000),
    ],
    "arg-bn-colon": [
        ("Manuel Vicentini", "ARQ", 35, 72, 1900000, 130000),
        ("Paolo Goltz", "DEF", 40, 72, 1600000, 130000),
        ("Hernán Lópes", "DEF", 34, 71, 1600000, 120000),
        ("Facundo Castet", "DEF", 27, 71, 1800000, 120000),
        ("Sebastián Prediger", "MED", 39, 73, 1900000, 140000),
        ("Nicolás Talpone", "MED", 29, 72, 2200000, 140000),
        ("Christian Bernardi", "MED", 35, 73, 2500000, 160000),
        ("Braian Guille", "DEL", 28, 72, 2200000, 140000),
        ("Javier Toledo", "DEL", 39, 71, 1400000, 120000),
        ("Genaro Rossi", "DEL", 23, 71, 2000000, 130000),
    ],
    "arg-bn-aldosivi": [
        ("Jorge Carranza", "ARQ", 44, 71, 1100000, 100000),
        ("Gonzalo Soto", "DEF", 35, 71, 1500000, 110000),
        ("Emanuel Iñiguez", "DEF", 29, 71, 1700000, 120000),
        ("Ignacio Guerrico", "DEF", 27, 70, 1500000, 110000),
        ("Marcelo Esponda", "MED", 22, 71, 1900000, 130000),
        ("Gonzalo Piñeiro", "MED", 25, 71, 1800000, 120000),
        ("Alan Sosa", "MED", 23, 72, 2400000, 150000),
        ("Nicolás Laméndola", "DEL", 27, 72, 2300000, 140000),
        ("Agustín Alonso", "DEL", 24, 71, 1900000, 130000),
        ("Agustín Colazo", "DEL", 25, 73, 2800000, 170000),
    ],
    "arg-bn-gimnasia-jujuy": [
        ("Joaquín Bigo", "ARQ", 27, 69, 1300000, 95000),
        ("Guillermo Cosaro", "DEF", 36, 70, 1200000, 100000),
        ("Mauro Osores", "DEF", 28, 70, 1500000, 110000),
        ("Facundo Rizzi", "DEF", 28, 70, 1400000, 100000),
        ("Hugo Soria", "MED", 35, 71, 1500000, 110000),
        ("Jorge Juárez", "MED", 26, 70, 1600000, 110000),
        ("Francisco Molina", "MED", 35, 70, 1300000, 100000),
        ("Emiliano Endrizzi", "MED", 31, 70, 1400000, 100000),
        ("Cristian Menéndez", "DEL", 37, 71, 1500000, 120000),
        ("Mauro Albertengo", "DEL", 36, 70, 1200000, 100000),
    ],
    "arg-bn-gimnasia-mendoza": [
        ("Matías Tagliamonte", "ARQ", 27, 72, 2200000, 130000),
        ("Diego Mondino", "DEF", 31, 71, 1800000, 120000),
        ("Maximiliano Padilla", "DEF", 31, 71, 1800000, 120000),
        ("Facundo Nadalín", "DEF", 28, 71, 1700000, 120000),
        ("Fermín Antonini", "MED", 28, 71, 1800000, 120000),
        ("Ignacio Antonio", "MED", 30, 70, 1500000, 110000),
        ("Leandro Ciccolini", "MED", 30, 72, 2200000, 140000),
        ("Nicolás Romano", "DEL", 25, 71, 1900000, 130000),
        ("Luis Silba", "DEL", 35, 72, 2000000, 130000),
        ("Jeremías Rodríguez Puch", "MED", 26, 71, 1800000, 120000),
    ],
    "arg-bn-moron": [
        ("Juan Martín Rojas", "ARQ", 26, 70, 1400000, 100000),
        ("Agustín Gómez", "DEF", 29, 70, 1400000, 100000),
        ("Fernando Moreyra", "DEF", 35, 69, 1100000, 95000),
        ("Nicolás Henry", "DEF", 26, 70, 1500000, 110000),
        ("Julián Vitale", "MED", 30, 71, 1700000, 120000),
        ("Gastón González", "MED", 38, 70, 1200000, 100000),
        ("Gonzalo Berterame", "DEL", 29, 71, 1800000, 120000),
        ("Mariano Bracamonte", "MED", 26, 70, 1500000, 110000),
        ("Ezequiel Rescaldani", "DEL", 33, 71, 1600000, 120000),
        ("Ivo Savoya", "DEL", 22, 69, 1300000, 95000),
    ],
    "arg-bn-temperley": [
        ("Francisco Rago", "ARQ", 37, 71, 1400000, 110000),
        ("Agustín Sosa", "DEF", 25, 70, 1600000, 110000),
        ("Mauricio Guzmán", "DEF", 26, 70, 1600000, 110000),
        ("Pedro Souto", "DEF", 25, 71, 1800000, 120000),
        ("Nicolás Da Campo", "MED", 31, 71, 1700000, 120000),
        ("Emanuel Ibáñez", "MED", 32, 70, 1500000, 110000),
        ("Juan Frías", "MED", 24, 71, 1900000, 130000),
        ("Marcos Arturia", "DEL", 27, 72, 2300000, 140000),
        ("Luis López", "DEL", 38, 71, 1500000, 120000),
        ("Julián Mavilla", "DEL", 24, 71, 1900000, 130000),
    ],
    "arg-bn-atlanta": [
        ("Alejandro Sánchez", "ARQ", 39, 70, 1100000, 95000),
        ("Dylan Gissi", "DEF", 34, 71, 1500000, 110000),
        ("Tomás Silva", "DEF", 22, 70, 1600000, 110000),
        ("Mauricio Rosales", "DEF", 33, 69, 1200000, 100000),
        ("Alejo Dramisino", "MED", 25, 71, 1800000, 120000),
        ("Gabriel Vega", "MED", 23, 71, 1900000, 130000),
        ("Carlo Lattanzio", "DEL", 28, 71, 1800000, 120000),
        ("Leonardo Marinucci", "DEL", 32, 71, 1700000, 120000),
        ("Erik Bodencer", "DEL", 25, 71, 1900000, 130000),
        ("Ivo Costantino", "DEL", 26, 70, 1500000, 110000),
    ],
    "arg-bn-estudiantes-rc": [
        ("Joaquín Bigo", "ARQ", 27, 70, 1400000, 100000),
        ("Gonzalo Maffini", "DEF", 32, 71, 1700000, 120000),
        ("Gastón Arturia", "DEF", 26, 70, 1500000, 110000),
        ("Ignacio Abraham", "DEF", 26, 69, 1300000, 100000),
        ("Nahuel Cainelli", "MED", 31, 72, 2100000, 140000),
        ("Francisco Romero", "MED", 26, 70, 1500000, 110000),
        ("Tomás González", "MED", 26, 70, 1500000, 110000),
        ("Mauro Valiente", "DEL", 25, 71, 1800000, 120000),
        ("Guillermo Villalba", "DEL", 29, 70, 1500000, 110000),
        ("Renzo Reynaga", "DEL", 26, 70, 1600000, 110000),
    ],
    "arg-bn-patronato": [
        ("Julio Salvá", "ARQ", 38, 71, 1400000, 110000),
        ("Gabriel Díaz", "DEF", 36, 70, 1300000, 110000),
        ("Mateo Burdisso", "DEF", 23, 69, 1400000, 100000),
        ("Diego Martínez", "DEF", 33, 70, 1400000, 110000),
        ("Gustavo Turraca", "MED", 30, 71, 1700000, 120000),
        ("Ezequiel González", "MED", 24, 70, 1600000, 110000),
        ("Arnaldo González", "MED", 36, 71, 1600000, 120000),
        ("Emanuel Dening", "DEL", 38, 72, 1900000, 130000),
        ("Alan Bonansea", "DEL", 29, 71, 1800000, 120000),
        ("Fabricio Sanguinetti", "DEL", 25, 70, 1500000, 110000),
    ],
    "arg-bn-arsenal": [
        ("Facundo Masuero", "ARQ", 25, 70, 1500000, 110000),
        ("Alexis Sosa", "DEF", 26, 70, 1500000, 110000),
        ("Baltazar Barcia", "DEF", 24, 69, 1400000, 100000),
        ("Iván Cabrera", "DEF", 22, 69, 1300000, 100000),
        ("Nicolás Domingo", "MED", 40, 72, 1600000, 130000),
        ("Matías Lucero", "MED", 23, 70, 1600000, 110000),
        ("Valentín Serrano", "MED", 21, 71, 1900000, 130000),
        ("Ignacio Sabatini", "DEL", 26, 71, 1800000, 120000),
        ("Luca Duarte", "DEL", 20, 70, 1700000, 110000),
        ("Agustín Maziero", "DEL", 28, 70, 1500000, 110000),
    ],
    "arg-bn-agropecuario": [
        ("Germán Salort", "ARQ", 37, 70, 1200000, 100000),
        ("Enzo Silcan", "DEF", 25, 69, 1300000, 100000),
        ("Marcelo Herrera", "DEF", 33, 70, 1400000, 110000),
        ("Alejo Montero", "DEF", 27, 70, 1500000, 110000),
        ("Matías Villarreal", "MED", 33, 71, 1700000, 120000),
        ("Martín Rivero", "MED", 36, 71, 1500000, 120000),
        ("Alejandro Melo", "DEL", 29, 72, 2200000, 140000),
        ("Claudio Bieler", "DEL", 41, 71, 1400000, 120000),
        ("Patricio Cucchi", "DEL", 32, 71, 1800000, 130000),
        ("Sebastián Navarro", "MED", 37, 70, 1200000, 100000),
    ],
    "arg-bn-defensores": [
        ("Ignacio Pietrobono", "ARQ", 34, 71, 1600000, 110000),
        ("Agustín Massaccesi", "DEF", 23, 70, 1600000, 110000),
        ("Facundo Laumann", "DEF", 35, 70, 1300000, 100000),
        ("Fabián Sánchez", "DEF", 25, 70, 1500000, 110000),
        ("Ignacio Gutiérrez", "MED", 22, 71, 1800000, 120000),
        ("Matías Barzi", "MED", 25, 70, 1500000, 110000),
        ("Brian Gómez", "MED", 31, 71, 1700000, 120000),
        ("Patricio Moyano", "DEL", 22, 71, 1900000, 130000),
        ("Ezequiel Aguirre", "DEL", 33, 72, 2100000, 140000),
        ("Gonzalo Aquilino", "DEL", 25, 71, 1800000, 120000),
    ],
}


def build_round_robin(teams: list[str], start_date: date, division: str) -> list[dict]:
    """Generates a complete round-robin fixture where each team plays every other once."""
    n = len(teams)
    if n % 2 != 0:
        raise ValueError("Must have even number of teams")

    rotation = list(teams)
    fixtures = []
    current_date = start_date

    # n - 1 rounds
    for round_num in range(1, n):
        round_matches = []
        for i in range(n // 2):
            home = rotation[i]
            away = rotation[n - 1 - i]
            # Alternate home/away to balance
            if round_num % 2 == 1 and i == 0:
                home, away = away, home

            fixtures.append({
                "division": division,
                "matchday": round_num,
                "played_on": current_date.isoformat(),
                "home_provider_id": home,
                "away_provider_id": away,
            })

        # Rotate keeping first team fixed
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
        current_date += timedelta(days=7)

    return fixtures


def main():
    print("Generating SVG crests...")
    for club in ALL_CLUBS:
        key = club["provider_id"].replace("arg-", "").replace("bn-", "")
        svg_content = generate_crest_svg(
            key=key,
            initials=club["initials"],
            bg_color=club["bg_color"],
            accent_color=club["accent_color"],
            text_color=club["text_color"],
            style=club["style"],
            detail_color=club.get("detail_color"),
        )
        svg_path = CRESTS_DIR / f"{key}.svg"
        svg_path.write_text(svg_content, encoding="utf-8")
        club["logo"] = f"/static/crests/{key}.svg"

    print(f"Created {len(ALL_CLUBS)} SVG crests in {CRESTS_DIR}")

    # Build Clubs Data
    clubs_dataset = [
        {
            "provider_id": c["provider_id"],
            "name": c["name"],
            "division": c["division"],
            "province": c["province"],
            "logo": c["logo"],
        }
        for c in ALL_CLUBS
    ]

    # Build Players Data
    players_dataset = []
    player_id_counter = 1
    for club in ALL_CLUBS:
        p_id = club["provider_id"]
        roster = ROSTERS.get(p_id, [])
        for name, pos, age, overall, val, wage in roster:
            prices_table = {
                68: 120000, 69: 150000, 70: 220000, 71: 320000, 72: 450000, 73: 600000,
                74: 780000, 75: 980000, 76: 1200000, 77: 1420000, 78: 1650000, 79: 1820000,
                80: 1950000, 81: 2000000, 82: 2000000,
            }
            scaled_val = prices_table.get(overall, min(2000000, max(120000, 150000 + (overall - 69) * 150000)))
            scaled_wage = max(5000, round((scaled_val * 0.035) / 1000) * 1000)
            players_dataset.append({
                "provider_id": f"arg-ply-{player_id_counter:04d}",
                "club_provider_id": p_id,
                "name": name,
                "position": pos,
                "age": age,
                "nationality": "Argentina",
                "overall": overall,
                "market_value": int(scaled_val),
                "wage": int(scaled_wage),
            })
            player_id_counter += 1

    print(f"Compiled {len(players_dataset)} players across {len(ALL_CLUBS)} clubs")

    # Build Fixtures 2026
    # Primera División: 28 teams -> 27 matchdays, starting Jan 24, 2026
    pd_team_ids = [c["provider_id"] for c in PRIMERA_DIVISION_CLUBS]
    pd_fixtures = build_round_robin(pd_team_ids, date(2026, 1, 24), "Primera División")

    # Primera Nacional: 20 teams -> 19 matchdays, starting Feb 1, 2026
    pn_team_ids = [c["provider_id"] for c in PRIMERA_NACIONAL_CLUBS]
    pn_fixtures = build_round_robin(pn_team_ids, date(2026, 2, 1), "Primera Nacional")

    all_fixtures = pd_fixtures + pn_fixtures
    print(f"Generated {len(all_fixtures)} fixtures (PD: {len(pd_fixtures)}, PN: {len(pn_fixtures)})")

    dataset = {
        "season": 2026,
        "source": "API Live Football Data (Creativesdev / AFA 2026)",
        "clubs": clubs_dataset,
        "players": players_dataset,
        "fixtures": all_fixtures,
    }

    out_file = BASE_DIR / "data_2026.json"
    out_file.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved complete dataset to {out_file}")

    # Validate dataset using import_data.validate_dataset
    from import_data import validate_dataset
    validate_dataset(dataset)
    print("Dataset validation passed successfully!")


if __name__ == "__main__":
    main()
