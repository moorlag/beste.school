"""Laden en valideren van de configuratie (config.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Indicator:
    naam: str
    gewicht: float
    richting: str  # "hoog" of "laag"
    label: str

    def __post_init__(self) -> None:
        if self.richting not in ("hoog", "laag"):
            raise ValueError(
                f"Indicator '{self.naam}': richting moet 'hoog' of 'laag' zijn, "
                f"kreeg '{self.richting}'."
            )
        if self.gewicht < 0:
            raise ValueError(f"Indicator '{self.naam}': gewicht mag niet negatief zijn.")


@dataclass
class Config:
    indicatoren: list[Indicator]
    ses_correctie_actief: bool
    ses_context_variabelen: list[str]
    drempel_kandidaten: int = 0
    extra: dict = field(default_factory=dict)

    @property
    def genormaliseerde_gewichten(self) -> dict[str, float]:
        """Gewichten die optellen tot 1, zodat de samengestelde score schaalvast is."""
        totaal = sum(i.gewicht for i in self.indicatoren)
        if totaal == 0:
            raise ValueError("Som van de indicatorgewichten is 0; kan niet normaliseren.")
        return {i.naam: i.gewicht / totaal for i in self.indicatoren}


def laad_config(pad: str | Path) -> Config:
    pad = Path(pad)
    with pad.open(encoding="utf-8") as f:
        ruw = yaml.safe_load(f)

    indicatoren = [
        Indicator(
            naam=naam,
            gewicht=float(spec["gewicht"]),
            richting=spec.get("richting", "hoog"),
            label=spec.get("label", naam),
        )
        for naam, spec in ruw["indicatoren"].items()
    ]

    ses = ruw.get("ses_correctie", {})
    # Ondersteun zowel één variabele (context_variabele) als meerdere
    # (context_variabelen). Meerdere -> multivariate regressie.
    if "context_variabelen" in ses:
        context_variabelen = list(ses["context_variabelen"])
    else:
        context_variabelen = [ses.get("context_variabele", "ses_score")]

    return Config(
        indicatoren=indicatoren,
        ses_correctie_actief=bool(ses.get("actief", False)),
        ses_context_variabelen=context_variabelen,
        drempel_kandidaten=int(ruw.get("drempel_kandidaten", 0)),
    )
