"""Score-engine: van indicatoren naar een eerlijke ranglijst.

Methode
-------
1. Normaliseer elke indicator naar een z-score (gemiddelde 0, standaarddeviatie 1)
   binnen de populatie scholen. Indicatoren met richting "laag" worden omgekeerd,
   zodat een hogere z-score altijd "beter" betekent.
2. Tel de z-scores gewogen op tot een samengestelde score, en herschaal naar 0-100.
3. (Optioneel) Corrigeer voor de leerlingpopulatie via een lineaire regressie van
   de samengestelde score op een SES-context-variabele. Het residu is de
   "toegevoegde waarde": presteert de school beter dan verwacht gegeven de instroom?

Alle stappen draaien identiek op echte DUO-data en op de sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config


def z_score(reeks: pd.Series) -> pd.Series:
    std = reeks.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(0.0, index=reeks.index)
    return (reeks - reeks.mean()) / std


def _herschaal_0_100(reeks: pd.Series) -> pd.Series:
    laag, hoog = reeks.min(), reeks.max()
    if hoog == laag:
        return pd.Series(50.0, index=reeks.index)
    return 100 * (reeks - laag) / (hoog - laag)


def bereken_scores(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Voeg z-scores, een samengestelde score en (optioneel) toegevoegde waarde toe."""
    df = df.copy()
    gewichten = config.genormaliseerde_gewichten

    # 1. Z-scores per indicator (richting-gecorrigeerd).
    samengesteld = pd.Series(0.0, index=df.index)
    for ind in config.indicatoren:
        if ind.naam not in df.columns:
            raise KeyError(
                f"Indicator '{ind.naam}' staat niet in de data. "
                f"Beschikbaar: {list(df.columns)}"
            )
        z = z_score(df[ind.naam].astype(float))
        if ind.richting == "laag":
            z = -z
        df[f"z_{ind.naam}"] = z
        samengesteld += gewichten[ind.naam] * z

    df["samengestelde_z"] = samengesteld
    df["score"] = _herschaal_0_100(samengesteld)

    # 3. Eerlijke correctie voor de leerlingpopulatie.
    if config.ses_correctie_actief:
        df = _ses_correctie(df, config.ses_context_variabele)

    return df


def _ses_correctie(df: pd.DataFrame, context_variabele: str) -> pd.DataFrame:
    """Regresseer de samengestelde score op SES; het residu = toegevoegde waarde."""
    df = df.copy()
    if context_variabele not in df.columns:
        raise KeyError(
            f"SES-correctie aan, maar context-variabele '{context_variabele}' ontbreekt."
        )

    geldig = df[context_variabele].notna() & df["samengestelde_z"].notna()
    x = df.loc[geldig, context_variabele].astype(float).to_numpy()
    y = df.loc[geldig, "samengestelde_z"].astype(float).to_numpy()

    if len(x) < 3 or np.std(x) == 0:
        # Te weinig spreiding om te corrigeren; val terug op ruwe score.
        df["toegevoegde_waarde"] = np.nan
        df["verwachte_z"] = np.nan
        df["score_gecorrigeerd"] = df["score"]
        return df

    helling, snijpunt = np.polyfit(x, y, 1)
    verwacht = helling * df[context_variabele].astype(float) + snijpunt
    residu = df["samengestelde_z"] - verwacht

    df["verwachte_z"] = verwacht
    df["toegevoegde_waarde"] = residu
    df["score_gecorrigeerd"] = _herschaal_0_100(residu)
    return df


def maak_ranglijst(df: pd.DataFrame, op: str = "score") -> pd.DataFrame:
    """Sorteer aflopend en voeg een rang-kolom toe."""
    gesorteerd = df.sort_values(op, ascending=False).reset_index(drop=True)
    gesorteerd.insert(0, "rang", np.arange(1, len(gesorteerd) + 1))
    return gesorteerd
