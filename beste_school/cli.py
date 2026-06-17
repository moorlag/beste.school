"""Command line interface: draai de hele pijplijn en toon de ranglijst.

Voorbeeld:
    python -m beste_school --data data/raw --config config.yaml --top 15
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import Config, laad_config
from .indicators import bouw_indicatortabel, filter_drempel
from .ingest import laad_bronnen
from .score import bereken_scores, maak_ranglijst

_BASIS_KOLOMMEN = [
    "rang",
    "instellingsnaam",
    "gemeente",
    "provincie",
    "gem_ce_cijfer",
    "slaagpercentage",
    "score",
]
_GECORRIGEERD_KOLOMMEN = [
    "rang",
    "instellingsnaam",
    "gemeente",
    "ses_score",
    "score",
    "score_gecorrigeerd",
    "toegevoegde_waarde",
]


def _toon(df: pd.DataFrame, kolommen: list[str], titel: str, top: int) -> None:
    aanwezig = [k for k in kolommen if k in df.columns]
    print(f"\n{titel}")
    print("=" * len(titel))
    weergave = df[aanwezig].head(top).copy()
    for kol in weergave.select_dtypes(include="number").columns:
        weergave[kol] = weergave[kol].round(2)
    print(weergave.to_string(index=False))


def _toon_totaal(gescoord: pd.DataFrame, config: Config, top: int) -> pd.DataFrame:
    """Eén ranglijst over alle scholen (geaggregeerd over onderwijstypen)."""
    ruw = maak_ranglijst(gescoord, op="score")
    _toon(ruw, _BASIS_KOLOMMEN, f"Top {top} -- ruwe score", top)

    if config.ses_correctie_actief and "score_gecorrigeerd" in gescoord.columns:
        gecorrigeerd = maak_ranglijst(gescoord, op="score_gecorrigeerd")
        _toon(
            gecorrigeerd,
            _GECORRIGEERD_KOLOMMEN,
            f"Top {top} -- gecorrigeerd voor leerlingpopulatie (toegevoegde waarde)",
            top,
        )
        return gecorrigeerd
    return ruw


def _toon_per_onderwijstype(
    gescoord: pd.DataFrame, config: Config, top: int
) -> pd.DataFrame:
    """Aparte ranglijst per onderwijstype; scholen alleen met hun gelijken vergeleken."""
    op = (
        "score_gecorrigeerd"
        if config.ses_correctie_actief and "score_gecorrigeerd" in gescoord.columns
        else "score"
    )
    kolommen = _GECORRIGEERD_KOLOMMEN if op == "score_gecorrigeerd" else _BASIS_KOLOMMEN

    delen = []
    for onderwijstype, deel in gescoord.groupby("onderwijstype", sort=True):
        ranglijst = maak_ranglijst(deel, op=op)
        _toon(ranglijst, kolommen, f"Top {top} -- {onderwijstype}", top)
        delen.append(ranglijst)
    return pd.concat(delen, ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="beste_school",
        description="Rangschik VO-scholen op basis van DUO-/contextdata.",
    )
    parser.add_argument("--data", default="data/raw", help="Map met bronbestanden.")
    parser.add_argument("--config", default="config.yaml", help="Configuratiebestand.")
    parser.add_argument("--top", type=int, default=15, help="Aantal scholen in de top.")
    parser.add_argument(
        "--per-onderwijstype",
        action="store_true",
        help="Rangschik binnen elk onderwijstype (vmbo-t/havo/vwo) apart.",
    )
    parser.add_argument(
        "--output",
        default="output/ranglijst.csv",
        help="Pad voor de volledige ranglijst (CSV).",
    )
    args = parser.parse_args(argv)

    config = laad_config(args.config)
    bronnen = laad_bronnen(args.data)

    indicatoren = bouw_indicatortabel(bronnen, per_onderwijstype=args.per_onderwijstype)
    indicatoren = filter_drempel(indicatoren, config.drempel_kandidaten)

    groep_kolom = "onderwijstype" if args.per_onderwijstype else None
    gescoord = bereken_scores(indicatoren, config, groep_kolom=groep_kolom)

    print(f"\nRijen na drempel ({config.drempel_kandidaten} kandidaten): {len(gescoord)}")

    if args.per_onderwijstype:
        volledig = _toon_per_onderwijstype(gescoord, config, args.top)
    else:
        volledig = _toon_totaal(gescoord, config, args.top)

    uitvoer = Path(args.output)
    uitvoer.parent.mkdir(parents=True, exist_ok=True)
    volledig.to_csv(uitvoer, index=False)
    print(f"\nVolledige ranglijst weggeschreven naar: {uitvoer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
