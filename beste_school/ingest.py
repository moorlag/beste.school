"""Inlezen van de brondata.

Het systeem koppelt alle bronnen op de unieke schoolsleutel in het Nederlandse
onderwijs: BRIN-nummer + vestigingsnummer.

Echte databronnen (open data, gratis):

  examenresultaten / geslaagden VO
    DUO Open Onderwijsdata -> Voortgezet onderwijs -> Leerlingen / Examens
    https://duo.nl/open_onderwijsdata/voortgezet-onderwijs/
    Levert per vestiging en onderwijstype: examenkandidaten, geslaagden.

  gemiddeld eindexamencijfer (CE)
    DUO Examenmonitor VO (gemiddeld cijfer centraal examen per vestiging/vak).

  onderbouwsnelheid & bovenbouwsucces
    Scholen op de Kaart (Vensters VO) / Onderwijsinspectie kwaliteitsindicatoren.
    https://scholenopdekaart.nl

  context (SES / achterstandsscore van de buurt)
    CBS / Onderwijs in Cijfers -- onderwijsachterstandsindicator (CBS-score)
    https://www.onderwijsincijfers.nl

DUO-bestanden zijn doorgaans CSV met puntkomma-scheiding en cp1252-codering,
met HOOFDLETTER-kolomnamen. `lees_duo_csv` vangt dat af. Voor deze
proof-of-concept staan voorbereide bestanden in `data/raw/` (zie
`scripts/generate_sample_data.py`); ze gebruiken exact dezelfde kolomnamen,
zodat je ze 1-op-1 door echte DUO-exports kunt vervangen.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Documentatie van de echte bronnen (zie ook de docstring hierboven).
DUO_BRONNEN = {
    "examenresultaten": "https://duo.nl/open_onderwijsdata/voortgezet-onderwijs/",
    "examenmonitor": "https://duo.nl/open_onderwijsdata/voortgezet-onderwijs/",
    "doorstroom": "https://scholenopdekaart.nl",
    "context_ses": "https://www.onderwijsincijfers.nl",
}

SLEUTEL = ["brin_nummer", "vestigingsnummer"]


def lees_duo_csv(pad: str | Path) -> pd.DataFrame:
    """Lees een DUO-achtig CSV-bestand robuust in.

    Probeert puntkomma- en komma-scheiding, en cp1252- en utf-8-codering.
    Normaliseert kolomnamen naar lowercase met underscores.
    """
    pad = Path(pad)
    laatste_fout: Exception | None = None
    for sep in (";", ","):
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(pad, sep=sep, encoding=enc, dtype=str)
                if df.shape[1] > 1:
                    df.columns = (
                        df.columns.str.strip()
                        .str.lower()
                        .str.replace(r"[^0-9a-z]+", "_", regex=True)
                        .str.strip("_")
                    )
                    return df
            except Exception as exc:  # noqa: BLE001 - we proberen meerdere varianten
                laatste_fout = exc
    raise ValueError(f"Kon {pad} niet inlezen als CSV") from laatste_fout


def laad_bronnen(map_pad: str | Path) -> dict[str, pd.DataFrame]:
    """Laad alle verwachte bronbestanden uit een map."""
    map_pad = Path(map_pad)
    bestanden = {
        "examen": "examenresultaten_vo.csv",
        "doorstroom": "doorstroom_vo.csv",
        "context": "context_ses.csv",
    }
    out: dict[str, pd.DataFrame] = {}
    for naam, bestand in bestanden.items():
        pad = map_pad / bestand
        if not pad.exists():
            raise FileNotFoundError(
                f"Bronbestand ontbreekt: {pad}\n"
                f"Genereer de sample met `python scripts/generate_sample_data.py` "
                f"of plaats hier de echte DUO-export."
            )
        out[naam] = lees_duo_csv(pad)
    return out
