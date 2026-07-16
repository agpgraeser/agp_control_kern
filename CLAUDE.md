# agp_control_kern – Projektnotizen

## Projektbeschreibung
**Gemeinsamer Fachkern der AGP·Control-Programmfamilie** (Stufe V2 der
Vereinheitlichung, Spec 25v07 + Antwortkonzept + Projektdatei-Spec V1 in
`RegelkreisZustandsDemo/Spezifikationen/`).

## Module
- `kern.py` – Parser (A,b,c, Polynome, Pole/Nullstellen, Zeitkonstanten-Faktoren)
  und Umwandlungen (zpk→tf, zk→tf, tf→Zustandsraum RNF/BNF/Modalform),
  herausgelöst aus `RegelkreisZustandsDemo/sim_core.py` (2026-07-17).
- `projektdatei.py` – AGP-Projektdatei **Formatversion 1**: EINE wachsende
  .xlsx je Schulungsfall (Blätter Meta/System/Stoerungen/Zeitverlaeufe/Modelle/
  Regler/Kennwerte); Programme schreiben nur eigene Blätter + Historie-Zeile;
  Altformat-Import (RKZ-Systemdateien); Zeitbasis Sekunden.
- `__init__.py` re-exportiert alles Wichtige.

## Nutzung in den Apps
Editierbar eingebunden (`-e ../agp_control_kern` in requirements.txt):
- **RegelkreisZustandsDemo** – sim_core.py re-exportiert den Kern, enthält nur
  noch die Simulation.
- **SystemDarstellungen** – latex_out importiert `from agp_control_kern import kern`.
- **ReglerparameterBerechnung** – eingebunden, genutzt ab Stufe V3 (Projektdatei).
Die Vite/JS-Apps (PTkPTn-*) nutzen NUR das Dateiformat (kein Python).

## Tests & Regeln
- `venv der Apps: python -m pytest tests` (13 Tests hier; die tiefe Abdeckung
  der Kernfunktionen liegt historisch in RegelkreisZustandsDemo/test_sim_core.py).
- **Änderungen am Kern immer gegen alle drei App-Suiten prüfen**
  (RKZ 54, RPB 17, SysDarst 15) – die Apps binden dieses Paket live ein (-e).
- Formatversion der Projektdatei nur nach Spec-Änderung (Versionstabelle) erhöhen.

## Verlauf
- **2026-07-17:** Angelegt (Stufe V2). kern.py aus sim_core extrahiert,
  projektdatei.py neu nach Spec V1 (P1–P6). Alle drei Python-Apps umgestellt,
  Suiten grün (54+17+15+13), Server-Smoke-Tests ok.
