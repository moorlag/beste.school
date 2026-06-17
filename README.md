# beste.school

Een datapijplijn en score-engine om scholen in het **voortgezet onderwijs (VO)**
te rangschikken — een onderbouwde poging om "de beste school van Nederland" uit
te roepen, met nadruk op **data-analyse en eerlijke vergelijking** in plaats van
op een mooie website.

> **Status:** proof-of-concept. De pijplijn draait end-to-end op een
> meegeleverde, *synthetische* sample-dataset met *fictieve* scholen. De
> ingest-laag is gebouwd op het echte DUO-schema, zodat je de sample 1-op-1 kunt
> vervangen door echte open data (zie [Databronnen](#databronnen)).

## Het idee in één alinea

Er bestaat geen objectieve "beste school". Elke ranglijst is een **normatieve
keuze**: welke indicatoren tellen mee, en hoe zwaar? Dit project maakt die keuze
*expliciet en configureerbaar* (`config.yaml`) en voegt er één ding aan toe dat
de meeste publiekslijstjes missen: een **eerlijke correctie voor de
leerlingpopulatie**. Een school in een kansrijke buurt hoort niet automatisch
bovenaan te staan; de vraag is hoeveel een school *toevoegt* gegeven wie er
binnenkomt.

## Snel starten

```bash
pip install -r requirements.txt
python scripts/generate_sample_data.py   # maakt data/raw/*.csv (sample)
python -m beste_school --top 15          # draait de pijplijn, print de ranglijst
```

Uitvoer: een ruwe top-N, een top-N **gecorrigeerd voor SES** (toegevoegde
waarde), en de volledige ranglijst in `output/ranglijst.csv`.

Tests:

```bash
python -m pytest -q
```

## Hoe het werkt

```
data/raw/*.csv ──► ingest ──► indicators ──► score-engine ──► ranglijst
  (DUO-schema)     inlezen     aggregeren      z-scores +       CLI + CSV
                   & koppelen   per vestiging   weging + SES
```

1. **Ingest** (`beste_school/ingest.py`) — leest DUO-achtige CSV's robuust in
   (puntkomma/komma, cp1252/utf-8, hoofdletter-kolommen). Koppelt alles op de
   unieke schoolsleutel **BRIN-nummer + vestigingsnummer**.
2. **Indicatoren** (`beste_school/indicators.py`) — aggregeert examenresultaten
   per vestiging (kandidaat-gewogen CE-cijfer, slaagpercentage) en koppelt
   doorstroom- en contextdata erbij. Eén rij per school.
3. **Score-engine** (`beste_school/score.py`):
   - **Normaliseren** — elke indicator naar een z-score binnen de populatie.
   - **Wegen** — gewogen som van z-scores → samengestelde score, herschaald 0–100.
   - **SES-correctie** — lineaire regressie van de score op een buurt-SES-variabele;
     het **residu** is de *toegevoegde waarde* (presteert de school boven of onder
     verwachting?). Dit is wat onderwijsonderzoek "value added" noemt.

### Indicatoren (configureerbaar in `config.yaml`)

| Indicator           | Standaard­gewicht | Bron-type                          |
|---------------------|-------------------|------------------------------------|
| Gemiddeld CE-cijfer | 0,40              | DUO Examenmonitor                  |
| Slaagpercentage     | 0,20              | DUO examenresultaten               |
| Onderbouwsnelheid   | 0,20              | Scholen op de Kaart / Inspectie    |
| Bovenbouwsucces     | 0,20              | Scholen op de Kaart / Inspectie    |

Verander de gewichten en de ranglijst verschuift — dat is het punt. Met
`ses_correctie.actief: false` schakel je de correctie uit en krijg je een
klassieke ruwe ranglijst.

## Databronnen

Alles is **open data** en gratis. De sample-bestanden gebruiken exact deze
kolomnamen, dus echte exports passen er zo in.

| Bron | Wat | Waar |
|------|-----|------|
| **DUO Open Onderwijsdata** | Scholen (BRIN), examenkandidaten, geslaagden, examencijfers | <https://duo.nl/open_onderwijsdata/voortgezet-onderwijs/> |
| **Scholen op de Kaart** (Vensters VO) | Onderbouwsnelheid, bovenbouwsucces, tevredenheid | <https://scholenopdekaart.nl> |
| **Onderwijsinspectie** | Kwaliteitsoordelen, inspectierapporten | <https://www.onderwijsinspectie.nl> |
| **CBS / Onderwijs in Cijfers** | Context: onderwijsachterstands-/SES-score per buurt | <https://www.onderwijsincijfers.nl> |

> ⚠️ Deze omgeving heeft geen netwerktoegang tot `duo.nl`. Daarom bevat de POC
> een synthetische sample. Draai het project in een omgeving mét DUO-toegang
> (of download de CSV's handmatig) en plaats ze in `data/raw/` om op echte data
> te draaien.

## Belangrijke beperkingen (eerlijk blijven)

- **"Beste" blijft een keuze.** De ranglijst is zo goed als de gekozen
  gewichten. Lever 'm nooit zonder die gewichten te tonen.
- **Data meet niet alles.** Sfeer, veiligheid, onderwijsvisie en leraarkwaliteit
  zitten niet (of indirect) in de cijfers.
- **SES-correctie is een model, geen waarheid.** Een lineaire correctie op één
  context-variabele is een vereenvoudiging; rijkere modellen gebruiken meerdere
  achtergrondkenmerken.
- **Kleine vestigingen zijn ruisgevoelig.** Vandaar de drempel op
  examenkandidaten (`drempel_kandidaten` in de config).

## Projectstructuur

```
beste_school/      score-engine en pijplijn (ingest, indicators, score, cli)
scripts/           generator voor de synthetische sample-data
tests/             unit-tests voor de berekeningen
data/raw/          bronbestanden (DUO-schema; sample of echte export)
config.yaml        indicatoren, gewichten en SES-instellingen
```
