"""Command line interface: draai de hele pijplijn en toon de ranglijst.

Voorbeeld:
    python -m beste_school --data data/raw --config config.yaml --top 15
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import laad_config
from .indicators import bouw_indicatortabel, filter_drempel
from .ingest import laad_bronnen
from .score import bereken_scores, maak_ranglijst


def _toon(df: pd.DataFrame, kolommen: list[str], titel: str, top: int) -> None:
    aanwezig = [k for k in kolommen if k in df.columns]
    print(f"\n{titel}")
    print("=" * len(titel))
    weergave = df[aanwezig].head(top).copy()
    for kol in weergave.select_dtypes(include="number").columns:
        weergave[kol] = weergave[kol].round(2)
    print(weergave.to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="beste_school",
        description="Rangschik VO-scholen op basis van DUO-/contextdata.",
    )
    parser.add_argument("--data", default="data/raw", help="Map met bronbestanden.")
    parser.add_argument("--config", default="config.yaml", help="Configuratiebestand.")
    parser.add_argument("--top", type=int, default=15, help="Aantal scholen in de top.")
    parser.add_argument(
        "--output",
        default="output/ranglijst.csv",
        help="Pad voor de volledige ranglijst (CSV).",
    )
    args = parser.parse_args(argv)

    config = laad_config(args.config)
    bronnen = laad_bronnen(args.data)

    indicatoren = bouw_indicatortabel(bronnen)
    indicatoren = filter_drempel(indicatoren, config.drempel_kandidaten)
    gescoord = bereken_scores(indicatoren, config)

    print(f"\nScholen na drempel ({config.drempel_kandidaten} kandidaten): {len(gescoord)}")

    basis_kolommen = [
        "rang",
        "instellingsnaam",
        "gemeente",
        "provincie",
        "gem_ce_cijfer",
        "slaagpercentage",
        "score",
    ]

    ruw = maak_ranglijst(gescoord, op="score")
    _toon(ruw, basis_kolommen, f"Top {args.top} -- ruwe score", args.top)

    if config.ses_correctie_actief and "score_gecorrigeerd" in gescoord.columns:
        gecorrigeerd = maak_ranglijst(gescoord, op="score_gecorrigeerd")
        _toon(
            gecorrigeerd,
            ["rang", "instellingsnaam", "gemeente", "ses_score",
             "score", "score_gecorrigeerd", "toegevoegde_waarde"],
            f"Top {args.top} -- gecorrigeerd voor leerlingpopulatie (toegevoegde waarde)",
            args.top,
        )
        volledig = gecorrigeerd
    else:
        volledig = ruw

    uitvoer = Path(args.output)
    uitvoer.parent.mkdir(parents=True, exist_ok=True)
    volledig.to_csv(uitvoer, index=False)
    print(f"\nVolledige ranglijst weggeschreven naar: {uitvoer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
