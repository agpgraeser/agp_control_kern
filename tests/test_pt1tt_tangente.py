"""Tests der Tangentenmethode fuer PT1TT-Modelle.

Herzstueck ist der **Referenzfall** aus
``PT1TT_Einspeicher_Tang/SPEC-Portierung-Python.md``, Abschnitt 6: eine
kuenstlich erzeugte Messdatei und die Werte, die die **alte React-App**
dazu anzeigt. Geprueft wird gegen diese Werte, nicht gegen die Erzeugung
der Messdatei -- die Tangentenmethode trifft die erzeugenden Kennwerte
nur naeherungsweise (TT = 3 wird als 2,486 abgelesen), und genau das soll
die Portierung uebernehmen.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from agp_control_kern import (
    PT1TT_METHODEN,
    pt1tt_auswertung,
    pt1tt_eingaben_gueltig,
    pt1tt_guetemasse,
    pt1tt_kennwerte,
    pt1tt_modell_sprungantwort,
)

# ── Referenzfall ───────────────────────────────────────────────────────────

#: Eingaben des Referenzfalls (Spec Abschnitt 6)
REF = dict(xa=10.0, xe=20.0, ya=0.0, ye=5.0, t0=2.0,
           x_tp1=11.1750, t_tp1=6.0, x_tp2=15.8314, t_tp2=12.0)

#: Ergebnisse, die die alte App zeigt -- unverkuerzt nachgerechnet
REF_T1 = 4.485955
REF_T2 = 17.371446
REF_TT = 2.485955
REF_TG = 12.885491
REF_TG1 = 11.371446
REF_INTEGRAL_1 = 46.2625002914944
REF_INTEGRAL_2 = 21.711237711650877

MESSDATEI = (Path(__file__).resolve().parents[2] / "PT1TT_Einspeicher_Tang"
             / "Referenzfall" / "Referenz-PT1TT-Tangente.xlsx")


@pytest.fixture(scope="module")
def messung():
    """Zeit, Regelgroesse und Stellgroesse der Referenzmessdatei.

    Struktur C: Zeile 1 Systemname, Zeile 2 Variablennamen, Zeile 3
    Einheiten, danach die Werte.
    """
    openpyxl = pytest.importorskip("openpyxl")
    if not MESSDATEI.exists():
        pytest.skip(f"Referenzmessdatei fehlt: {MESSDATEI}")
    ws = openpyxl.load_workbook(MESSDATEI, data_only=True).worksheets[0]
    zeit, x, y = [], [], []
    for reihe in ws.iter_rows(min_row=4, max_col=3, values_only=True):
        if reihe[0] is None:
            continue
        zeit.append(float(reihe[0]))
        x.append(float(reihe[1]))
        y.append(float(reihe[2]))
    return np.array(zeit), np.array(x), np.array(y)


def test_messdatei_hat_die_erwartete_form(messung):
    zeit, x, _ = messung
    assert zeit.size == 601
    assert zeit[0] == 0.0 and zeit[-1] == pytest.approx(60.0)
    assert x[0] == pytest.approx(10.0)       # vor dem Sprung XA


# ── Kennwerte des Referenzfalls ────────────────────────────────────────────

def test_referenzfall_kennwerte():
    """Abnahmekriterium der Spec: t1, t2, TT, TG auf drei Nachkommastellen,
    kS auf vier."""
    kw = pt1tt_kennwerte(**REF)
    assert kw["d_x"] == pytest.approx(10.0)
    assert kw["d_y"] == pytest.approx(5.0)
    assert round(kw["k_s"], 4) == 2.0000
    assert round(kw["t1"], 3) == round(REF_T1, 3)
    assert round(kw["t2"], 3) == round(REF_T2, 3)
    assert round(kw["TT"], 3) == round(REF_TT, 3)
    assert round(kw["TG"], 3) == round(REF_TG, 3)
    assert round(kw["TG1"], 3) == round(REF_TG1, 3)


def test_referenzfall_kennwerte_unverkuerzt():
    """Dieselben Werte voll aufgeloest -- faengt stilles Wegrunden."""
    kw = pt1tt_kennwerte(**REF)
    assert kw["t1"] == pytest.approx(REF_T1, abs=5e-7)
    assert kw["t2"] == pytest.approx(REF_T2, abs=5e-7)
    assert kw["TT"] == pytest.approx(REF_TT, abs=5e-7)
    assert kw["TG"] == pytest.approx(REF_TG, abs=5e-7)
    assert kw["TG1"] == pytest.approx(REF_TG1, abs=5e-7)


def test_referenzfall_fehlerintegrale(messung):
    """Sigma dx^2*dt beider Modelle auf sechs geltende Ziffern."""
    zeit, x, _ = messung
    erg = pt1tt_auswertung(zeit=zeit, x_mess=x, methode=3, **REF)
    assert [m["zeit_name"] for m in erg["modelle"]] == ["TG", "TG1"]
    assert erg["modelle"][0]["integral_ende"] == pytest.approx(
        REF_INTEGRAL_1, rel=1e-6)
    assert erg["modelle"][1]["integral_ende"] == pytest.approx(
        REF_INTEGRAL_2, rel=1e-6)


def test_methode_1_liefert_nur_das_erste_modell(messung):
    zeit, x, _ = messung
    erg = pt1tt_auswertung(zeit=zeit, x_mess=x, methode=1, **REF)
    assert len(erg["modelle"]) == 1
    assert erg["modelle"][0]["zeit_name"] == "TG"
    assert erg["modelle"][0]["integral_ende"] == pytest.approx(
        REF_INTEGRAL_1, rel=1e-6)


def test_methode_2_liefert_nur_das_zweite_modell(messung):
    zeit, x, _ = messung
    erg = pt1tt_auswertung(zeit=zeit, x_mess=x, methode=2, **REF)
    assert len(erg["modelle"]) == 1
    assert erg["modelle"][0]["zeit_name"] == "TG1"
    assert erg["modelle"][0]["integral_ende"] == pytest.approx(
        REF_INTEGRAL_2, rel=1e-6)


def test_unbekannte_methode_wird_abgelehnt():
    with pytest.raises(ValueError):
        pt1tt_auswertung(methode=4, **REF)
    assert PT1TT_METHODEN == (1, 2, 3)


# ── t0 und die geometrische Pruefung ──────────────────────────────────────

def test_schnittpunkte_sind_unabhaengig_von_t0():
    """t1 und t2 haengen nur an der Tangente -- t0 verschiebt nur TT."""
    ohne = pt1tt_kennwerte(**{**REF, "t0": None})
    mit = pt1tt_kennwerte(**{**REF, "t0": 7.5})
    assert ohne["t1"] == pytest.approx(mit["t1"])
    assert ohne["t2"] == pytest.approx(mit["t2"])
    assert ohne["TT"] is None                 # ohne t0 keine Kennwerte
    assert mit["TT"] == pytest.approx(REF_T1 - 7.5)
    # TG bleibt, TT wandert
    assert mit["TG"] == pytest.approx(REF_TG, abs=5e-7)


def test_negatives_t0_gibt_keine_kennwerte():
    kw = pt1tt_kennwerte(**{**REF, "t0": -1.0})
    assert kw["t1"] is not None               # Tangente steht trotzdem
    assert kw["TT"] is None and kw["TG"] is None and kw["TG1"] is None


@pytest.mark.parametrize("aenderung", [
    {"x_tp2": 10.5},            # Steigung so flach, dass t2 vor TP1 liegt
    {"x_tp1": 19.9},            # TP1 fast am Endwert -> t1 hinter TP1
])
def test_geometrisch_falsche_tangente_gibt_nichts(aenderung):
    kw = pt1tt_kennwerte(**{**REF, **aenderung})
    assert kw["t1"] is None and kw["t2"] is None
    assert kw["TT"] is None


def test_waagerechte_tangente_gibt_nichts():
    kw = pt1tt_kennwerte(**{**REF, "x_tp2": REF["x_tp1"]})
    assert kw["steigung"] == 0
    assert kw["t1"] is None


def test_senkrechte_tangente_gibt_nichts():
    """tTP2 == tTP1 -- Division durch Null wird abgefangen."""
    kw = pt1tt_kennwerte(**{**REF, "t_tp2": REF["t_tp1"]})
    assert kw["steigung"] is None and kw["t1"] is None


# ── Teilweise gefuellte Eingaben ──────────────────────────────────────────

def test_unvollstaendige_eingaben_rechnen_so_weit_es_geht():
    kw = pt1tt_kennwerte(xa=10.0, xe=20.0, ya=0.0, ye=5.0)
    assert kw["d_x"] == 10.0 and kw["k_s"] == 2.0
    assert kw["t1"] is None and kw["TT"] is None


def test_kein_stellsprung_gibt_kein_ks():
    kw = pt1tt_kennwerte(xa=10.0, xe=20.0, ya=3.0, ye=3.0)
    assert kw["d_y"] == 0 and kw["k_s"] is None


@pytest.mark.parametrize("wert", ["", "abc", None, float("nan"),
                                  float("inf")])
def test_unbrauchbare_eingaben_gelten_als_nicht_angegeben(wert):
    kw = pt1tt_kennwerte(**{**REF, "x_tp1": wert})
    assert kw["t1"] is None


def test_text_wird_gelesen_wenn_er_eine_zahl_ist():
    """Die Oberflaeche liefert Strings -- sie muessen durchgehen."""
    kw = pt1tt_kennwerte(**{k: str(v) for k, v in REF.items()})
    assert round(kw["TG"], 3) == round(REF_TG, 3)


# ── Eingabepruefung der Oberflaeche ───────────────────────────────────────

def test_referenzfall_ist_gueltige_eingabe():
    gueltig, grund = pt1tt_eingaben_gueltig(
        REF["xa"], REF["xe"], REF["t0"], REF["x_tp1"], REF["t_tp1"],
        REF["x_tp2"], REF["t_tp2"])
    assert gueltig and grund == ""


@pytest.mark.parametrize("aenderung, text", [
    ({"t0": -0.1}, "t0 muss >= 0"),
    ({"x_tp1": 9.0}, "XTP1 >= XA"),          # TP1 unter XA
    ({"x_tp2": 25.0}, "XTP2 <= XE"),         # TP2 ueber XE
    ({"x_tp2": 11.0}, "XTP1 < XTP2"),        # TP2 unter TP1
    ({"t_tp1": 1.0}, "tTP1 > t0"),           # TP1 vor dem Sprung
    ({"t_tp2": 3.0}, "tTP2 > tTP1"),
    ({"x_tp1": None}, "nicht angegeben"),
])
def test_ungueltige_eingaben_werden_begruendet(aenderung, text):
    werte = {**REF, **aenderung}
    gueltig, grund = pt1tt_eingaben_gueltig(
        werte["xa"], werte["xe"], werte["t0"], werte["x_tp1"],
        werte["t_tp1"], werte["x_tp2"], werte["t_tp2"])
    assert not gueltig
    assert text in grund


def test_tangentenpunkte_duerfen_die_beharrungswerte_beruehren():
    """Neue Grenze (20.10.2026): ``>= XA`` und ``<= XE`` statt echt dazwischen.

    Kennwerte liefert ``XTP1 == XA`` trotzdem nicht -- dann faellt t1 mit
    tTP1 zusammen und die geometrische Pruefung ``t1 < tTP1 < t2`` greift.
    """
    gueltig, grund = pt1tt_eingaben_gueltig(
        REF["xa"], REF["xe"], REF["t0"], REF["xa"], REF["t_tp1"],
        REF["xe"], REF["t_tp2"])
    assert gueltig and grund == ""


def test_tangentenpunkt_vor_dem_sprung_ist_ungueltig():
    """tTP1 > t0: ein Tangentenpunkt vor dem Stellsprung ergibt keinen Sinn.
    Die alte App liess ihn zu."""
    gueltig, grund = pt1tt_eingaben_gueltig(
        REF["xa"], REF["xe"], 7.0, REF["x_tp1"], 6.0,
        REF["x_tp2"], REF["t_tp2"])
    assert not gueltig
    assert "tTP1 > t0" in grund


# ── Modellkurve und Guetemasse einzeln ────────────────────────────────────

def test_modell_haelt_den_anfangswert_bis_totzeit_vorbei():
    t = np.array([0.0, 2.0, 4.0, 4.485955, 5.0, 100.0])
    kurve = pt1tt_modell_sprungantwort(
        t, xa=10.0, k_s=2.0, d_y=5.0, t0=2.0, tt=REF_TT, tg=REF_TG)
    # t <= t0 + TT = 4.485955 -> XA
    np.testing.assert_allclose(kurve[:4], 10.0)
    assert kurve[4] > 10.0
    # Endwert XA + kS*dY; bei t = 100 fehlen noch rund 6e-3 (7,4 Zeitkonstanten)
    assert kurve[-1] == pytest.approx(20.0, abs=1e-2)


def test_modell_trifft_die_eigene_erzeugung_exakt():
    """Mit den erzeugenden Kennwerten (TT = 3, TG = 8) muss die Kurve die
    Messdatei-Formel reproduzieren -- Gegenprobe zur Modellgleichung."""
    t = np.linspace(0, 60, 601)
    kurve = pt1tt_modell_sprungantwort(
        t, xa=10.0, k_s=2.0, d_y=5.0, t0=2.0, tt=3.0, tg=8.0)
    erwartet = np.where(
        t <= 5.0, 10.0, 10.0 + 10.0 * (1.0 - np.exp(-(t - 5.0) / 8.0)))
    np.testing.assert_allclose(kurve, erwartet, rtol=1e-12)


def test_erster_integrationsschritt_zaehlt_nicht():
    """Rechteckregel mit dt = 0 im ersten Punkt -- wie in der alten App."""
    t = np.array([0.0, 1.0, 2.0])
    g = pt1tt_guetemasse(t, x_mess=[3.0, 3.0, 3.0], x_modell=[0.0, 1.0, 1.0])
    np.testing.assert_allclose(g["abweichung"], [3.0, 2.0, 2.0])
    np.testing.assert_allclose(g["abweichung_quadrat"], [9.0, 4.0, 4.0])
    # erster Punkt mit dt = 0 -> 0, dann +4*1, +4*1
    np.testing.assert_allclose(g["integral"], [0.0, 4.0, 8.0])
    assert g["integral_ende"] == 8.0


def test_integral_bei_ungleichen_zeitschritten():
    t = np.array([0.0, 0.5, 2.5])
    g = pt1tt_guetemasse(t, x_mess=[1.0, 1.0, 1.0], x_modell=[0.0, 0.0, 0.0])
    np.testing.assert_allclose(g["integral"], [0.0, 0.5, 2.5])


def test_guetemasse_ohne_punkte():
    g = pt1tt_guetemasse([], [], [])
    assert g["integral_ende"] is None


# ── Auswertung ohne Messung ───────────────────────────────────────────────

def test_auswertung_ohne_messdaten_gibt_nur_kennwerte():
    erg = pt1tt_auswertung(methode=1, **REF)
    assert erg["modelle"] == []
    assert round(erg["TG"], 3) == round(REF_TG, 3)


def test_auswertung_ohne_kennwerte_gibt_keine_modelle(messung):
    zeit, x, _ = messung
    erg = pt1tt_auswertung(zeit=zeit, x_mess=x, methode=3,
                           **{**REF, "t_tp2": REF["t_tp1"]})
    assert erg["modelle"] == []


def test_messung_und_zeit_muessen_gleich_lang_sein():
    erg = pt1tt_auswertung(zeit=[0.0, 1.0, 2.0], x_mess=[0.0, 1.0],
                           methode=1, **REF)
    assert erg["modelle"] == []


def test_modellkurve_der_auswertung_ist_die_des_einzelaufrufs(messung):
    zeit, x, _ = messung
    erg = pt1tt_auswertung(zeit=zeit, x_mess=x, methode=1, **REF)
    einzeln = pt1tt_modell_sprungantwort(
        zeit, xa=REF["xa"], k_s=2.0, d_y=5.0, t0=REF["t0"],
        tt=erg["TT"], tg=erg["TG"])
    np.testing.assert_allclose(erg["modelle"][0]["kurve"], einzeln, rtol=1e-12)


def test_grosse_ausgleichszeit_ueberlaeuft_nicht():
    """Sehr kleines TG: exp(-grosse Zahl) darf keine Warnung werfen."""
    t = np.array([0.0, 1.0, 1000.0])
    kurve = pt1tt_modell_sprungantwort(
        t, xa=0.0, k_s=1.0, d_y=1.0, t0=0.0, tt=0.0, tg=1e-6)
    assert all(math.isfinite(w) for w in kurve)


# ── Projektdatei: Blätter Ablesung und Modelle (2026-10-20) ────────────────

from agp_control_kern import (  # noqa: E402
    pt1tt_ablesung_zu_eingaben,
    pt1tt_projekt_zeilen,
    projektdatei,
)


def test_projekt_zeilen_referenzfall_mit_messung(messung):
    zeit, x, _ = messung
    ablesung, modelle = pt1tt_projekt_zeilen(zeit=zeit, x_mess=x, methode=1, **REF)
    assert ablesung["y_A"] == 10.0 and ablesung["u_E"] == 5.0
    assert ablesung["t_P1"] == 6.0 and ablesung["y_P2"] == 15.8314
    assert ablesung["t_P3"] == "" and ablesung["y_P3"] == ""
    assert len(modelle) == 1
    m = modelle[0]
    assert m["Typ"] == "PT1TT" and m["n"] == "" and m["T_M"] == ""
    assert m["Methode"] == "Tangente M1 (TG)"
    assert m["k_M"] == pytest.approx(2.0)
    assert m["T_T"] == pytest.approx(REF_TT, abs=1e-6)
    assert m["T_1"] == pytest.approx(REF_TG, abs=1e-6)
    assert m["Guete"] == pytest.approx(REF_INTEGRAL_1, rel=1e-9)


def test_projekt_zeilen_methode_3_zwei_modelle_ohne_messung():
    _, modelle = pt1tt_projekt_zeilen(methode=3, **REF)
    assert [m["Methode"] for m in modelle] == ["Tangente M1 (TG)", "Tangente M2 (TG1)"]
    assert modelle[1]["T_1"] == pytest.approx(REF_TG1, abs=1e-6)
    assert all(m["Guete"] == "" for m in modelle)


def test_projekt_zeilen_tangente_schief_keine_modelle():
    falsch = {**REF, "x_tp1": 10.0}          # t1 == tTP1 -> keine Kennwerte
    ablesung, modelle = pt1tt_projekt_zeilen(**falsch)
    assert modelle == []
    assert ablesung["y_P1"] == 10.0


def test_ablesung_rundweg_ueber_die_datei():
    ablesung, modelle = pt1tt_projekt_zeilen(**REF)
    p = projektdatei.neu("Fall", programm="Test")
    projektdatei.ablesung_ersetzen(p, "Tangente", ablesung, modelle)
    q = projektdatei.lesen(projektdatei.schreiben(p))
    zeile = projektdatei.ablesung_finden(q, "Tangente")
    eingaben = pt1tt_ablesung_zu_eingaben(zeile)
    assert eingaben == {k: pytest.approx(v) for k, v in REF.items()}
    assert q["modelle"][0]["Ablesung_Nr"] == zeile["Nr"]
