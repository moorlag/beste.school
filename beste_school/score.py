"""Score-engine: van indicatoren naar een eerlijke ranglijst.

Methode
-------
1. Normaliseer elke indicator naar een z-score (gemiddelde 0, standaarddeviatie 1).
   Indicatoren met richting "laag" worden omgekeerd, zodat een hogere z-score
   altijd "beter" betekent. De normalisatie gebeurt binnen een *peer-groep*: als
   je per onderwijstype rangschikt, worden vwo'ers met vwo'ers vergeleken en
   vmbo'ers met vmbo'ers -- een 7,0 betekent immers niet hetzelfde op vmbo-t als
   op vwo.
2. Tel de z-scores gewogen op tot een samengestelde score, herschaald naar 0-100.
3. (Optioneel) Corrigeer voor de leerlingpopulatie via een *meervoudige* lineaire
   regressie van de samengestelde score op meerdere SES-context-variabelen. Het
   residu is de "toegevoegde waarde": presteert de school beter dan verwacht
   gegeven de instroom?

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


def bereken_scores(
    df: pd.DataFrame, config: Config, groep_kolom: str | None = None
) -> pd.DataFrame:
    """Bereken scores, eventueel binnen peer-groepen (bijv. per onderwijstype).

    Met `groep_kolom` worden z-scores, weging en SES-correctie per groep berekend,
    zodat alleen vergelijkbare scholen tegen elkaar worden afgezet.
    """
    if groep_kolom is None or groep_kolom not in df.columns:
        return _scoor_groep(df, config)

    delen = [
        _scoor_groep(deel, config)
        for _, deel in df.groupby(groep_kolom, sort=False)
    ]
    return pd.concat(delen).sort_index()


def _scoor_groep(df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Bereken scores binnen één (peer-)groep."""
    df = df.copy()
    gewichten = config.genormaliseerde_gewichten

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

    if config.ses_correctie_actief:
        df = _ses_correctie(df, config.ses_context_variabelen)

    return df


def _ses_correctie(df: pd.DataFrame, context_variabelen: list[str]) -> pd.DataFrame:
    """Meervoudige regressie van de score op SES; het residu = toegevoegde waarde.

    Lost kleinste-kwadraten op: samengestelde_z ~ b0 + b1*x1 + ... + bk*xk.
    Het residu (waargenomen - verwacht) is de toegevoegde waarde van de school.
    """
    df = df.copy()
    aanwezig = [v for v in context_variabelen if v in df.columns]
    if not aanwezig:
        raise KeyError(
            "SES-correctie aan, maar geen van de context-variabelen "
            f"{context_variabelen} staat in de data."
        )

    geldig = df["samengestelde_z"].notna()
    for v in aanwezig:
        geldig &= df[v].notna()

    X_vol = df[aanwezig].astype(float)
    n_geldig = int(geldig.sum())

    # Te weinig waarnemingen of geen spreiding -> val terug op de ruwe score.
    genoeg = n_geldig >= len(aanwezig) + 2
    spreiding = all(X_vol.loc[geldig, v].std(ddof=0) > 0 for v in aanwezig)
    if not (genoeg and spreiding):
        df["verwachte_z"] = np.nan
        df["toegevoegde_waarde"] = np.nan
        df["score_gecorrigeerd"] = df["score"]
        return df

    # Ontwerpmatrix met interceptkolom.
    A = np.column_stack([np.ones(n_geldig), X_vol.loc[geldig].to_numpy()])
    y = df.loc[geldig, "samengestelde_z"].to_numpy()
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)

    A_vol = np.column_stack([np.ones(len(df)), X_vol.to_numpy()])
    verwacht = A_vol @ coef
    residu = df["samengestelde_z"].to_numpy() - verwacht

    df["verwachte_z"] = verwacht
    df["toegevoegde_waarde"] = residu
    df["score_gecorrigeerd"] = _herschaal_0_100(pd.Series(residu, index=df.index))
    return df


def maak_ranglijst(df: pd.DataFrame, op: str = "score") -> pd.DataFrame:
    """Sorteer aflopend en voeg een rang-kolom toe."""
    gesorteerd = df.sort_values(op, ascending=False).reset_index(drop=True)
    gesorteerd.insert(0, "rang", np.arange(1, len(gesorteerd) + 1))
    return gesorteerd
