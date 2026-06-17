"""Genereer een realistische sample-dataset in het DUO-VO-schema.

BELANGRIJK: de scholen hieronder zijn FICTIEF en de cijfers zijn SYNTHETISCH.
Ze dienen alleen om de pijplijn end-to-end te demonstreren zonder echte scholen
ten onrechte goed of slecht voor te stellen. De kolomnamen komen overeen met
DUO-exports, zodat je deze bestanden 1-op-1 kunt vervangen door echte data.

De data is zo opgezet dat de SES-correctie zichtbaar effect heeft: elke school
heeft een (verborgen) "echte" toegevoegde waarde los van de buurt-SES. Scholen
in kansrijke buurten scoren ruw hoger, maar na correctie komen de scholen met de
hoogste toegevoegde waarde bovendrijven.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

# (gemeente, provincie) -- een spreiding over Nederland.
PLAATSEN = [
    ("Amsterdam", "Noord-Holland"),
    ("Rotterdam", "Zuid-Holland"),
    ("Den Haag", "Zuid-Holland"),
    ("Utrecht", "Utrecht"),
    ("Eindhoven", "Noord-Brabant"),
    ("Groningen", "Groningen"),
    ("Tilburg", "Noord-Brabant"),
    ("Almere", "Flevoland"),
    ("Nijmegen", "Gelderland"),
    ("Enschede", "Overijssel"),
    ("Haarlem", "Noord-Holland"),
    ("Arnhem", "Gelderland"),
    ("Zwolle", "Overijssel"),
    ("Leeuwarden", "Friesland"),
    ("Maastricht", "Limburg"),
    ("Middelburg", "Zeeland"),
    ("Assen", "Drenthe"),
    ("Lelystad", "Flevoland"),
]

# Bouwstenen voor fictieve schoolnamen.
SOORT = ["Lyceum", "College", "Gymnasium", "Scholengemeenschap", "Mavo/Havo/Vwo"]
NAAM = [
    "De Horizon", "Stedelijk", "Het Nieuwe", "Rijnvliet", "De Meander",
    "Noorderlicht", "Het Vrije", "Parklaan", "De Brug", "Lindehof",
    "Het Baken", "Oostvaarders", "De Dijk", "Vondel", "Erasmus-fictief",
    "Het Anker", "De Waal", "Spinoza-fictief", "De Vlieger", "Het Kompas",
]

ONDERWIJSTYPEN = ["VMBO-GT", "HAVO", "VWO"]


def genereer() -> dict[str, pd.DataFrame]:
    aantal_scholen = 60
    examen_rijen = []
    doorstroom_rijen = []
    context_rijen = []

    for i in range(aantal_scholen):
        brin = f"{RNG.integers(10, 30):02d}{chr(RNG.integers(65, 91))}{chr(RNG.integers(65, 91))}"
        vestiging = f"{RNG.integers(0, 5):02d}"
        gemeente, provincie = PLAATSEN[i % len(PLAATSEN)]
        naam = f"{NAAM[i % len(NAAM)]} {SOORT[i % len(SOORT)]}"
        # Maak namen uniek.
        naam = f"{naam} ({gemeente})"

        # Buurt-SES: hogere score = kansrijker. Schaal ~ [80, 120], gem 100.
        ses_score = float(np.clip(RNG.normal(100, 10), 75, 125))

        # Verborgen "echte" toegevoegde waarde van de school (los van SES).
        school_effect = RNG.normal(0, 1.0)

        # Onderliggende kwaliteit = SES-component + toegevoegde waarde + ruis.
        ses_component = (ses_score - 100) / 10.0  # ~ standaard-normaal
        kwaliteit = 0.6 * ses_component + school_effect

        # --- Examenresultaten per onderwijstype ---
        for ot in ONDERWIJSTYPEN:
            if RNG.random() < 0.15:
                continue  # niet elke school biedt elk type aan
            kandidaten = int(np.clip(RNG.normal(90, 35), 15, 220))
            # Gemiddeld CE-cijfer rond 6.5, beïnvloed door kwaliteit.
            gem_ce = float(np.clip(6.5 + 0.30 * kwaliteit + RNG.normal(0, 0.10), 5.2, 8.2))
            # Slaagkans afhankelijk van kwaliteit.
            slaagkans = float(np.clip(0.90 + 0.04 * kwaliteit + RNG.normal(0, 0.01), 0.78, 1.0))
            geslaagden = int(round(kandidaten * slaagkans))
            examen_rijen.append(
                {
                    "BRIN_NUMMER": brin,
                    "VESTIGINGSNUMMER": vestiging,
                    "INSTELLINGSNAAM": naam,
                    "GEMEENTE": gemeente,
                    "PROVINCIE": provincie,
                    "ONDERWIJSTYPE": ot,
                    "EXAMENKANDIDATEN": kandidaten,
                    "GESLAAGDEN": geslaagden,
                    # DUO gebruikt vaak komma als decimaalteken.
                    "GEM_CE_CIJFER": f"{gem_ce:.2f}".replace(".", ","),
                }
            )

        # --- Doorstroomindicatoren (Scholen op de Kaart / Inspectie) ---
        onderbouw = float(np.clip(95 + 1.5 * kwaliteit + RNG.normal(0, 1.0), 82, 100))
        bovenbouw = float(np.clip(90 + 2.5 * kwaliteit + RNG.normal(0, 1.5), 75, 100))
        doorstroom_rijen.append(
            {
                "BRIN_NUMMER": brin,
                "VESTIGINGSNUMMER": vestiging,
                "ONDERBOUWSNELHEID": f"{onderbouw:.1f}".replace(".", ","),
                "BOVENBOUWSUCCES": f"{bovenbouw:.1f}".replace(".", ","),
            }
        )

        # --- Contextdata (CBS / Onderwijs in Cijfers) ---
        context_rijen.append(
            {
                "BRIN_NUMMER": brin,
                "VESTIGINGSNUMMER": vestiging,
                "SES_SCORE": f"{ses_score:.1f}".replace(".", ","),
            }
        )

    return {
        "examenresultaten_vo.csv": pd.DataFrame(examen_rijen),
        "doorstroom_vo.csv": pd.DataFrame(doorstroom_rijen),
        "context_ses.csv": pd.DataFrame(context_rijen),
    }


def main() -> None:
    doel = Path(__file__).resolve().parent.parent / "data" / "raw"
    doel.mkdir(parents=True, exist_ok=True)
    for bestand, df in genereer().items():
        pad = doel / bestand
        # Schrijf als DUO: puntkomma-gescheiden.
        df.to_csv(pad, sep=";", index=False, encoding="utf-8")
        print(f"Geschreven: {pad}  ({len(df)} rijen)")


if __name__ == "__main__":
    main()
