"""Tests des PT1TT-Vergleichs (Portierung aus PT1TT_Vergleich, 2026-10-20).

Sollwerte vom **Original-TypeScript** der alten App (``computeModels`` aus
``PT1TT_Vergleich/src/utils/math.ts``, mit esbuild gebuendelt und in Node
ausgefuehrt); das Fehlerintegral nach der Formel aus ``ResponseChart.tsx``.
Messung: Referenzmessung der Tangente.
"""

from pathlib import Path

import numpy as np
import pytest

from agp_control_kern import projektdatei
from agp_control_kern import pt1tt_vergleich as vg

SIGNAL = dict(xa=10.0, t0=2.0, ya=0.0, dy=5.0)
SYSTEME = [
    {"name": "Tangente", "KS": 2, "TT": 2.486, "TG": 12.885, "aktiv": True},
    {"name": "3-Punkt", "KS": 2, "TT": 2.992, "TG": 8.021, "aktiv": True},
    {"name": "aus", "KS": 1, "TT": 1, "TG": 1, "aktiv": False},
    {"name": "", "KS": 1.5, "TT": 0, "TG": 4, "aktiv": True},
]

# Ausgabe des Original-TypeScript
ALT_OHNE_ENDE = 69.417
ALT_OHNE_W250 = [19.047218787889825, 19.75608219123776, 17.497928766607817]
ALT_MIT_W100 = [13.481491262728731, 14.64396458104457, 16.484985375725405]
ALT_SUMME = [46.254192349495355, 0.0007316675941451816, 270.20429884177065]

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
        if reihe[0] is not None:
            zeit.append(float(reihe[0]))
            x.append(float(reihe[1]))
    return np.array(zeit), np.array(x)


def test_ohne_messung_wie_die_alte_app():
    erg = vg.vergleich(**SIGNAL, systeme=SYSTEME)
    assert len(erg["zeit"]) == 500
    assert erg["zeit"][-1] == pytest.approx(ALT_OHNE_ENDE)
    assert [m["name"] for m in erg["modelle"]] == ["Tangente", "3-Punkt", "System 4"]
    assert [m["index"] for m in erg["modelle"]] == [0, 1, 3]
    werte = [m["kurve"][250] for m in erg["modelle"]]
    assert werte == pytest.approx(ALT_OHNE_W250, rel=1e-12)
    assert "integral_ende" not in erg["modelle"][0]


def test_mit_messung_wie_die_alte_app(messung):
    zeit, x = messung
    erg = vg.vergleich(**SIGNAL, systeme=SYSTEME, zeit=zeit, x_mess=x)
    assert len(erg["zeit"]) == 601
    assert [m["kurve"][100] for m in erg["modelle"]] == pytest.approx(ALT_MIT_W100, rel=1e-12)
    assert [m["integral_ende"] for m in erg["modelle"]] == pytest.approx(ALT_SUMME, rel=1e-9)


@pytest.mark.parametrize("aenderung", [{"xa": None}, {"t0": None}, {"dy": 0}, {"dy": None}])
def test_ungueltiges_signal_gibt_nichts(aenderung):
    erg = vg.vergleich(**{**SIGNAL, **aenderung}, systeme=SYSTEME)
    assert erg["modelle"] == [] and len(erg["zeit"]) == 0


def test_feldfehler_wie_die_alte_app():
    fehler = vg.vergleich(**{**SIGNAL, "dy": 0}, systeme=[
        {"KS": 0, "TT": -1, "TG": 0, "aktiv": True},
        {"KS": 0, "TT": -1, "TG": 0, "aktiv": False}])["fehler"]
    assert fehler["signal"] == {"XA": False, "t0": False, "YA": False, "DY": True}
    assert fehler["systeme"][0] == {"KS": True, "TT": True, "TG": True}
    assert fehler["systeme"][1] == {"KS": False, "TT": False, "TG": False}


def test_systeme_und_signal_aus_projekt():
    p = projektdatei.neu("Fall", programm="Test")
    p["modelle"] = [{"Nr": 1, "Typ": "PTn", "Methode": "ZPK", "k_M": 2, "n": 3, "T_M": 1.5}]
    projektdatei.ablesung_ersetzen(
        p, "Tangente",
        {"y_A": 10, "y_E": 20, "u_A": 0, "u_E": 5, "t_0": 2},
        [{"Typ": "PT1TT", "Methode": "Tangente M1 (TG)", "k_M": 2, "T_T": 2.486, "T_1": 12.885}])
    projektdatei.ablesung_ersetzen(
        p, "3-Punkt", {"y_A": 10, "u_A": 0, "u_E": 5, "t_0": 2},
        [{"Typ": "PT1TT", "Methode": "3-Punkt (TG)", "k_M": 2, "T_T": 2.992, "T_1": 8.021}])
    q = projektdatei.lesen(projektdatei.schreiben(p))
    systeme = vg.systeme_aus_projekt(q)
    assert [s["name"] for s in systeme] == ["Tangente M1 (TG)", "3-Punkt (TG)"]
    assert systeme[1]["TG"] == pytest.approx(8.021)
    assert vg.signal_aus_projekt(q) == {"XA": 10, "t0": 2, "YA": 0, "DY": 5,
                                        "verfahren": "Tangente"}


def test_hoechstens_vier_systeme():
    p = {"modelle": [{"Typ": "PT1TT", "Methode": f"M{i}", "k_M": 1, "T_T": 1, "T_1": 1}
                     for i in range(6)]}
    assert len(vg.systeme_aus_projekt(p)) == 4
