"""Tests voor de score-engine en indicatorberekening."""

from __future__ import annotations

import numpy as np
import pandas as pd

from beste_school.config import Config, Indicator
from beste_school.indicators import aggregeer_examen
from beste_school.score import bereken_scores, maak_ranglijst, z_score


def _config(ses: bool = False, context: list[str] | None = None) -> Config:
    return Config(
        indicatoren=[
            Indicator("gem_ce_cijfer", 1.0, "hoog", "CE"),
            Indicator("slaagpercentage", 1.0, "hoog", "Slaag"),
        ],
        ses_correctie_actief=ses,
        ses_context_variabelen=context or ["ses_score"],
    )


def test_z_score_gemiddelde_nul():
    z = z_score(pd.Series([1.0, 2.0, 3.0, 4.0]))
    assert abs(z.mean()) < 1e-9
    assert abs(z.std(ddof=0) - 1.0) < 1e-9


def test_z_score_constante_reeks():
    z = z_score(pd.Series([5.0, 5.0, 5.0]))
    assert (z == 0).all()


def test_aggregeer_examen_gewogen_gemiddelde():
    examen = pd.DataFrame(
        {
            "brin_nummer": ["00AA", "00AA"],
            "vestigingsnummer": ["00", "00"],
            "instellingsnaam": ["X", "X"],
            "gemeente": ["Stad", "Stad"],
            "provincie": ["P", "P"],
            "onderwijstype": ["HAVO", "VWO"],
            "examenkandidaten": ["100", "50"],
            "geslaagden": ["90", "50"],
            "gem_ce_cijfer": ["6,0", "7,0"],
        }
    )
    out = aggregeer_examen(examen)
    assert len(out) == 1
    rij = out.iloc[0]
    assert rij["examenkandidaten"] == 150
    assert rij["geslaagden"] == 140
    # Gewogen CE: (100*6 + 50*7) / 150 = 6.333...
    assert abs(rij["gem_ce_cijfer"] - (100 * 6 + 50 * 7) / 150) < 1e-9
    # Slaag: 140/150 = 93.33%
    assert abs(rij["slaagpercentage"] - 100 * 140 / 150) < 1e-9


def test_richting_laag_keert_om():
    df = pd.DataFrame(
        {"gem_ce_cijfer": [6.0, 7.0, 8.0], "slaagpercentage": [80.0, 90.0, 100.0]}
    )
    config = Config(
        indicatoren=[Indicator("gem_ce_cijfer", 1.0, "laag", "CE")],
        ses_correctie_actief=False,
        ses_context_variabelen=["ses_score"],
    )
    out = bereken_scores(df, config)
    # Bij richting 'laag' krijgt de laagste waarde de hoogste score.
    assert out.loc[0, "score"] == out["score"].max()


def test_ses_correctie_verschuift_ranglijst():
    # Achtergrond: SES voorspelt de prestatie positief (kansrijke buurt -> hogere
    # cijfers), zodat de regressie een duidelijke helling heeft. Daar bovenop twee
    # scholen met IDENTIEKE ruwe score maar verschillende SES. Na correctie hoort
    # de school in de zwakkere buurt hoger te eindigen (meer toegevoegde waarde).
    df = pd.DataFrame(
        {
            "instellingsnaam": ["A", "B", "C", "D", "E", "Kansrijk", "Kansarm"],
            "gem_ce_cijfer": [6.0, 6.3, 6.6, 6.9, 7.2, 6.6, 6.6],
            "slaagpercentage": [80.0, 85.0, 90.0, 95.0, 99.0, 90.0, 90.0],
            "ses_score": [80.0, 90.0, 100.0, 110.0, 120.0, 120.0, 80.0],
        }
    )
    out = bereken_scores(df, _config(ses=True))
    assert "score_gecorrigeerd" in out.columns
    kansrijk = out[out["instellingsnaam"] == "Kansrijk"].iloc[0]
    kansarm = out[out["instellingsnaam"] == "Kansarm"].iloc[0]
    # Zelfde ruwe score, maar 'Kansarm' presteert boven verwachting.
    assert kansarm["toegevoegde_waarde"] > kansrijk["toegevoegde_waarde"]
    assert kansarm["score_gecorrigeerd"] > kansrijk["score_gecorrigeerd"]


def test_multivariate_ses_correctie():
    # Twee onafhankelijke context-variabelen. Voor de ankerscholen is de prestatie
    # exact een lineaire functie van (ses + opleiding), zodat hun toegevoegde
    # waarde ~0 is. Eén afwijker presteert op topniveau maar heeft de zwakste
    # instroom -> die hoort als enige een duidelijk positieve toegevoegde waarde
    # te krijgen, en wel de hoogste van het veld.
    ankers = [(80, 20), (80, 40), (100, 20), (100, 40),
              (120, 20), (120, 40), (90, 30), (110, 30)]
    namen, ce, slaag, ses, opl = [], [], [], [], []
    for i, (s, o) in enumerate(ankers):
        f = s + o
        namen.append(f"anker_{i}")
        ce.append(6.0 + 0.005 * f)
        slaag.append(80.0 + 0.05 * f)
        ses.append(float(s))
        opl.append(float(o))
    # Afwijker: prestatie als f=160 (top), maar instroom ses=80, opl=20 (f=100).
    namen.append("Afwijker")
    ce.append(6.0 + 0.005 * 160)
    slaag.append(80.0 + 0.05 * 160)
    ses.append(80.0)
    opl.append(20.0)

    df = pd.DataFrame(
        {
            "instellingsnaam": namen,
            "gem_ce_cijfer": ce,
            "slaagpercentage": slaag,
            "ses_score": ses,
            "opleiding_ouders": opl,
        }
    )
    out = bereken_scores(df, _config(ses=True, context=["ses_score", "opleiding_ouders"]))
    afwijker = out[out["instellingsnaam"] == "Afwijker"].iloc[0]
    assert afwijker["toegevoegde_waarde"] == out["toegevoegde_waarde"].max()
    assert afwijker["toegevoegde_waarde"] > 0.5


def test_groeps_normalisatie_per_onderwijstype():
    # Z-scores moeten binnen het onderwijstype berekend worden: een 7,0 op vmbo
    # hoort niet vergeleken te worden met een 7,0 op vwo.
    df = pd.DataFrame(
        {
            "onderwijstype": ["VMBO", "VMBO", "VWO", "VWO"],
            "gem_ce_cijfer": [6.0, 7.0, 6.0, 7.0],
            "slaagpercentage": [80.0, 90.0, 80.0, 90.0],
        }
    )
    out = bereken_scores(df, _config(ses=False), groep_kolom="onderwijstype")
    # Binnen elk type is de hoogste een 7,0 -> z-score +1, ongeacht het type.
    vmbo = out[out["onderwijstype"] == "VMBO"]
    vwo = out[out["onderwijstype"] == "VWO"]
    assert abs(vmbo["z_gem_ce_cijfer"].max() - 1.0) < 1e-9
    assert abs(vwo["z_gem_ce_cijfer"].max() - 1.0) < 1e-9
    # De beste van elk type krijgt binnen zijn groep de topscore.
    assert vmbo["score"].max() == 100.0
    assert vwo["score"].max() == 100.0


def test_maak_ranglijst_sorteert_aflopend():
    df = pd.DataFrame({"score": [10.0, 50.0, 30.0]})
    out = maak_ranglijst(df, op="score")
    assert list(out["rang"]) == [1, 2, 3]
    assert list(out["score"]) == [50.0, 30.0, 10.0]
