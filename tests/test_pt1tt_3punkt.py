"""Tests der 3-Punkt-Methode (Portierung aus PT1TT_Berechnung, 2026-10-20).

Referenzfall: die Referenzmessung der Tangente (kuenstliches PT1TT, TT = 3),
abgelesen bei 10/50/90 % auf zwei Nachkommastellen. Die Sollwerte hat das
**Original-TypeScript** der alten App gerechnet (``computeDerived`` aus
``PT1TT_Berechnung/src/utils/pt1ttMath.ts``, mit esbuild gebuendelt und in
Node ausgefuehrt) -- nicht diese Portierung.
"""

from pathlib import Path

import numpy as np
import pytest

from agp_control_kern import pt1tt_3punkt as dp
from agp_control_kern import projektdatei

REF = dict(xa=10.0, xe=20.0, ya=0.0, ye=5.0, t0=2.0,
           t10=5.84, t50=10.55, t90=23.42)

# Ausgabe des Original-TypeScript
ALT_TT = 2.992327044025157
ALT_TG = 8.020865387840672
ALT_SUMME = 0.0007310531768737589
ALT_MODELL_100 = 14.64380231394188
ALT_MODELL_300 = 19.557467863389363

MESSDATEI = (Path(__file__).resolve().parents[2] / "PT1TT_Einspeicher_Tang"
             / "Referenzfall" / "Referenz-PT1TT-Tangente.xlsx")


@pytest.fixture(scope="module")
def messung():
    openpyxl = pytest.importorskip("openpyxl")
    if not MESSDATEI.exists():
        pytest.skip(f"Referenzmessdatei fehlt: {MESSDATEI}")
    ws = openpyxl.load_workbook(MESSDATEI, data_only=True).worksheets[0]
    zeit, x = [], []
    for reihe in ws.iter_rows(min_row=4, max_col=2, values_only=True):
        if reihe[0] is None:
            continue
        zeit.append(float(reihe[0]))
        x.append(float(reihe[1]))
    return np.array(zeit), np.array(x)


def test_kennwerte_wie_die_alte_app():
    kw = dp.kennwerte(**REF)
    assert kw["k_s"] == pytest.approx(2.0)
    assert (kw["x10"], kw["x50"], kw["x90"]) == pytest.approx((11.0, 15.0, 19.0))
    assert kw["TT"] == pytest.approx(ALT_TT, rel=1e-12)
    assert kw["TG"] == pytest.approx(ALT_TG, rel=1e-12)


def test_modell_und_fehlerintegral_wie_die_alte_app(messung):
    zeit, x = messung
    erg = dp.auswertung(zeit=zeit, x_mess=x, **REF)
    m = erg["modelle"][0]
    assert m["kurve"][100] == pytest.approx(ALT_MODELL_100, rel=1e-12)
    assert m["kurve"][300] == pytest.approx(ALT_MODELL_300, rel=1e-12)
    assert m["integral_ende"] == pytest.approx(ALT_SUMME, rel=1e-9)


def test_echtes_pt1tt_wird_naeherungsweise_getroffen():
    """Exakte Zeiten eines PT1TT (TT = 3, T = 8) -> die Methode liefert
    TT und T bis auf ihre Naeherung (Faktoren auf drei Stellen): TG kommt
    hier um 0,2 % zu gross heraus (8,016 statt 8) -- Eigenschaft des
    Verfahrens, nicht der Portierung."""
    t0, tt, tg = 2.0, 3.0, 8.0
    zeiten = {p: t0 + tt - tg * np.log(1 - p) for p in (0.1, 0.5, 0.9)}
    kw = dp.kennwerte(xa=0, xe=1, ya=0, ye=1, t0=t0,
                      t10=zeiten[0.1], t50=zeiten[0.5], t90=zeiten[0.9])
    assert kw["TT"] == pytest.approx(tt, abs=0.01)
    assert kw["TG"] == pytest.approx(tg, rel=0.005)


@pytest.mark.parametrize("aenderung, text", [
    ({"t0": -1}, "t0 muss >= 0"),
    ({"t10": 2.0}, "t10 > t0"),
    ({"t50": 5.0}, "t50 > t10"),
    ({"t90": 10.0}, "t90 > t50"),
    ({"t50": None}, "nicht angegeben: t50"),
])
def test_eingabepruefung(aenderung, text):
    gueltig, grund = dp.eingaben_gueltig(**{**REF, **aenderung})
    assert not gueltig and text in grund


def test_falsche_reihenfolge_gibt_keine_kennwerte():
    kw = dp.kennwerte(**{**REF, "t50": 30.0})
    assert kw["TT"] is None and kw["TG"] is None
    assert kw["k_s"] == pytest.approx(2.0)


def test_ohne_messung_keine_modellkurve():
    assert dp.auswertung(**REF)["modelle"] == []


def test_projektzeilen_und_rundweg(messung):
    zeit, x = messung
    ablesung, modelle = dp.projekt_zeilen(zeit=zeit, x_mess=x, **REF)
    assert (ablesung["t_P1"], ablesung["y_P1"]) == (5.84, pytest.approx(11.0))
    assert (ablesung["t_P3"], ablesung["y_P3"]) == (23.42, pytest.approx(19.0))
    m = modelle[0]
    assert m["Methode"] == "3-Punkt (TG)" and m["n"] == "" and m["T_M"] == ""
    assert m["T_T"] == pytest.approx(ALT_TT) and m["T_1"] == pytest.approx(ALT_TG)
    assert m["Guete"] == pytest.approx(ALT_SUMME, rel=1e-9)

    p = projektdatei.neu("Fall", programm="Test")
    projektdatei.ablesung_ersetzen(p, dp.VERFAHREN, ablesung, modelle)
    q = projektdatei.lesen(projektdatei.schreiben(p))
    eingaben = dp.ablesung_zu_eingaben(projektdatei.ablesung_finden(q, "3-Punkt"))
    assert eingaben == {k: pytest.approx(v) for k, v in REF.items()}
