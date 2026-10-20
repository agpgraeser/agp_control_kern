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
  Seit 2026-10-20 Blatt **Ablesung** (eine Zeile je Verfahren: Tangente,
  Wendetangente, 3-Punkt) und Spalte `Ablesung_Nr` in Modelle;
  `ablesung_ersetzen()` ersetzt nur das eigene Verfahren samt seinen Modellen,
  `ablesung_finden()` holt die Zeile zurück.
- `pt1tt_tangente.py` – PT1TT-Modell aus einer Sprungantwort nach der
  **Tangentenmethode**, portiert aus `PT1TT_Einspeicher_Tang/src/utils/
  pt1ttMath.ts` (2026-10-20, Spec dort: `SPEC-Portierung-Python.md`).
  Dient **zwei** Apps: PT1TT · Tangente (zwei frei gewählte Tangentenpunkte,
  Einspeichersystem ohne Wendepunkt) und später PT1TT · Wendetangente
  (TP1 = Wendepunkt). Punkte heißen deshalb neutral `tangentenpunkt1/2`.
  Alle drei Methoden im Kern; die Tangenten-Oberfläche zeigt nur Methode 1.
  `eingaben_gueltig(..., punkt="WP")` nennt die Punkte in der Begründung XWP1 …
  (Wendetangente), Voreinstellung "TP".
  `projekt_zeilen()` / `ablesung_zu_eingaben()`: Ablesung und Modelle für die
  Projektdatei (PT1TT nach Spec: `T_T`, `T_1`; `n`, `T_M` leer). Die
  Wendetangente ruft dieselbe Funktion mit `verfahren="Wendetangente"`.
- `pt1tt_3punkt.py` – PT1TT-Modell nach der **3-Punkt-Methode** (t10/t50/t90),
  portiert aus `PT1TT_Berechnung/src/utils/pt1ttMath.ts` (2026-10-20).
  Modellkurve und Fehlerintegral aus `pt1tt_tangente`. Referenzfall vom
  Original-TypeScript gerechnet (Node + esbuild), 11 Tests. Verfahren "3-Punkt".
- `__init__.py` re-exportiert alles Wichtige – die PT1TT-Namen **mit Vorsilbe**
  (`pt1tt_kennwerte`, `pt1tt_auswertung`, …), weil `kennwerte`/`auswertung`
  im Paketnamensraum nicht eindeutig wären.

## Nutzung in den Apps
Editierbar eingebunden (`-e ../agp_control_kern` in requirements.txt):
- **RegelkreisZustandsDemo** – sim_core.py re-exportiert den Kern, enthält nur
  noch die Simulation.
- **SystemDarstellungen** – latex_out importiert `from agp_control_kern import kern`.
- **ReglerparameterBerechnung** – eingebunden, genutzt ab Stufe V3 (Projektdatei).
Die Vite/JS-Apps (PTkPTn-*) nutzen NUR das Dateiformat (kein Python).

## Tests & Regeln
- `venv der Apps: python -m pytest tests` (158 Tests hier; die tiefe Abdeckung
  der Kernfunktionen liegt historisch in RegelkreisZustandsDemo/test_sim_core.py).
- **Änderungen am Kern immer gegen alle App-Suiten prüfen** – die Apps binden
  dieses Paket live ein (-e). Stand 2026-10-20: RegelkreisSimulationen 113,
  ZPK-Identifikation 26, ReglerparameterBerechnung 23, PTn-ZPK 30,
  PTn-Vergleich 20, SystemDarstellungen 15, PT1TT-Tangente 25,
  PT1TT-Wendetangente 30, PT1TT-3Punkt 13.
- Formatversion der Projektdatei nur nach Spec-Änderung (Versionstabelle) erhöhen.

## Verlauf
- **2026-07-17:** Angelegt (Stufe V2). kern.py aus sim_core extrahiert,
  projektdatei.py neu nach Spec V1 (P1–P6). Alle drei Python-Apps umgestellt,
  Suiten grün (54+17+15+13), Server-Smoke-Tests ok.
- **2026-10-20:** `pt1tt_tangente.py` angelegt (Portierung PT1TT · Tangente,
  Schritt 1). Referenzfall der Spec als Testanker: t₁/t₂/TT/TG auf drei
  Nachkommastellen, kS auf vier, Σ Δx²·Δt beider Modelle auf sechs geltende
  Ziffern – 39 Tests, Suite hier 136, alle sechs App-Suiten unverändert grün.
- **2026-10-20:** Projektdatei um Blatt Ablesung + `Ablesung_Nr` erweitert,
  `pt1tt_tangente.projekt_zeilen`. Spec-Nachtrag in
  `RegelkreisSimulationen/Spezifikationen/25v07-V1-Spec-AGP-Projektdatei.tex`.
  Formatversion bleibt 1 (ältere Leser gehen nach Spaltennamen). 145 Tests,
  alle sieben App-Suiten grün.
