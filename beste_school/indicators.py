"""Van ruwe bronnen naar één tabel met indicatoren per school.

Stappen:
  1. Examenresultaten aggregeren per vestiging (gewogen over onderwijstypen).
  2. Doorstroom- en contextdata erbij koppelen op BRIN + vestigingsnummer.
  3. Resultaat: één rij per school(vestiging) met alle indicatoren.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .ingest import SLEUTEL

# Kolommen die we als getal verwachten in de examenbron.
_NUMERIEK_EXAMEN = ["examenkandidaten", "geslaagden", "gem_ce_cijfer"]
_NUMERIEK_DOORSTROOM = ["onderbouwsnelheid", "bovenbouwsucces"]
_NUMERIEK_CONTEXT = ["ses_score"]


def _naar_getal(df: pd.DataFrame, kolommen: list[str]) -> pd.DataFrame:
    df = df.copy()
    for kol in kolommen:
        if kol in df.columns:
            # DUO gebruikt soms komma's als decimaalteken.
            df[kol] = pd.to_numeric(
                df[kol].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
    return df


def aggregeer_examen(examen: pd.DataFrame) -> pd.DataFrame:
    """Aggregeer examenresultaten naar één rij per vestiging.

    Een vestiging heeft meestal meerdere onderwijstypen (vmbo-t, havo, vwo).
    We tellen kandidaten en geslaagden op en berekenen het gemiddelde CE-cijfer
    gewogen naar het aantal kandidaten.
    """
    examen = _naar_getal(examen, _NUMERIEK_EXAMEN)

    # Identificerende, niet-numerieke velden die we willen bewaren.
    meta_kolommen = [
        k
        for k in ["instellingsnaam", "gemeente", "provincie"]
        if k in examen.columns
    ]

    examen["_ce_x_kandidaten"] = examen["gem_ce_cijfer"] * examen["examenkandidaten"]

    groep = examen.groupby(SLEUTEL, as_index=False).agg(
        examenkandidaten=("examenkandidaten", "sum"),
        geslaagden=("geslaagden", "sum"),
        _ce_x_kandidaten=("_ce_x_kandidaten", "sum"),
    )
    groep["gem_ce_cijfer"] = groep["_ce_x_kandidaten"] / groep["examenkandidaten"]
    groep["slaagpercentage"] = 100 * groep["geslaagden"] / groep["examenkandidaten"]
    groep = groep.drop(columns="_ce_x_kandidaten")

    if meta_kolommen:
        meta = examen.groupby(SLEUTEL, as_index=False)[meta_kolommen].first()
        groep = groep.merge(meta, on=SLEUTEL, how="left")

    return groep


def bouw_indicatortabel(bronnen: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combineer alle bronnen tot één indicatortabel per school."""
    df = aggregeer_examen(bronnen["examen"])

    doorstroom = _naar_getal(bronnen["doorstroom"], _NUMERIEK_DOORSTROOM)
    context = _naar_getal(bronnen["context"], _NUMERIEK_CONTEXT)

    df = df.merge(
        doorstroom[SLEUTEL + _NUMERIEK_DOORSTROOM], on=SLEUTEL, how="left"
    )
    df = df.merge(context[SLEUTEL + _NUMERIEK_CONTEXT], on=SLEUTEL, how="left")

    return df


def filter_drempel(df: pd.DataFrame, drempel_kandidaten: int) -> pd.DataFrame:
    """Verwijder vestigingen met te weinig kandidaten (statistische ruis)."""
    if drempel_kandidaten <= 0:
        return df
    return df[df["examenkandidaten"] >= drempel_kandidaten].reset_index(drop=True)
