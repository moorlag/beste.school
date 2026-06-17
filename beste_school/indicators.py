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


def aggregeer_examen(
    examen: pd.DataFrame, extra_groep: list[str] | None = None
) -> pd.DataFrame:
    """Aggregeer examenresultaten tot één rij per vestiging.

    Een vestiging heeft meestal meerdere onderwijstypen (vmbo-t, havo, vwo) en
    DUO kan binnen een type nog uitsplitsen (bijv. naar geslacht). We tellen
    kandidaten en geslaagden op en berekenen het CE-cijfer gewogen naar het
    aantal kandidaten.

    Met `extra_groep=["onderwijstype"]` blijft de uitsplitsing per onderwijstype
    behouden -- dan krijg je één rij per vestiging *en* onderwijstype.
    """
    examen = _naar_getal(examen, _NUMERIEK_EXAMEN)
    groep_kolommen = SLEUTEL + (extra_groep or [])

    # Identificerende, niet-numerieke velden die we willen bewaren.
    meta_kolommen = [
        k
        for k in ["instellingsnaam", "gemeente", "provincie"]
        if k in examen.columns
    ]

    examen["_ce_x_kandidaten"] = examen["gem_ce_cijfer"] * examen["examenkandidaten"]

    groep = examen.groupby(groep_kolommen, as_index=False).agg(
        examenkandidaten=("examenkandidaten", "sum"),
        geslaagden=("geslaagden", "sum"),
        _ce_x_kandidaten=("_ce_x_kandidaten", "sum"),
    )
    groep["gem_ce_cijfer"] = groep["_ce_x_kandidaten"] / groep["examenkandidaten"]
    groep["slaagpercentage"] = 100 * groep["geslaagden"] / groep["examenkandidaten"]
    groep = groep.drop(columns="_ce_x_kandidaten")

    if meta_kolommen:
        meta = examen.groupby(groep_kolommen, as_index=False)[meta_kolommen].first()
        groep = groep.merge(meta, on=groep_kolommen, how="left")

    return groep


def _context_numeriek(context: pd.DataFrame) -> pd.DataFrame:
    """Maak alle niet-sleutel-kolommen in de contextbron numeriek."""
    kolommen = [k for k in context.columns if k not in SLEUTEL]
    return _naar_getal(context, kolommen)


def bouw_indicatortabel(
    bronnen: dict[str, pd.DataFrame], per_onderwijstype: bool = False
) -> pd.DataFrame:
    """Combineer alle bronnen tot één indicatortabel.

    Met `per_onderwijstype=True` krijg je één rij per vestiging én onderwijstype,
    zodat je binnen vergelijkbare niveaus kunt rangschikken. Doorstroom- en
    contextdata zitten op vestigingsniveau en worden op elke type-rij gekoppeld.
    """
    extra_groep = ["onderwijstype"] if per_onderwijstype else None
    df = aggregeer_examen(bronnen["examen"], extra_groep=extra_groep)

    doorstroom = _naar_getal(bronnen["doorstroom"], _NUMERIEK_DOORSTROOM)
    context = _context_numeriek(bronnen["context"])

    df = df.merge(
        doorstroom[SLEUTEL + _NUMERIEK_DOORSTROOM], on=SLEUTEL, how="left"
    )
    df = df.merge(context, on=SLEUTEL, how="left")

    return df


def filter_drempel(df: pd.DataFrame, drempel_kandidaten: int) -> pd.DataFrame:
    """Verwijder vestigingen met te weinig kandidaten (statistische ruis)."""
    if drempel_kandidaten <= 0:
        return df
    return df[df["examenkandidaten"] >= drempel_kandidaten].reset_index(drop=True)
