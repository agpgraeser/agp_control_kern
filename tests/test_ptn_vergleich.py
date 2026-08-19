"""Tests des Vergleichs mehrerer PTn-Modelle."""

import numpy as np
import pytest

from agp_control_kern import (T99, ptn_sprungantwort, ptn_modell_aus_projekt,
                              signalwerte_aus_projekt, system_gueltig,
                              vergleich, zeitachse)
from agp_control_kern.ptn_vergleich import SYNTH_PUNKTE


def sys_(name="S", y_a=0.0, t0=0.0, d_u=1.0, k_s=1.0, n=3, T_s=2.0, aktiv=True):
    return {"name": name, "y_a": y_a, "t0": t0, "d_u": d_u,
            "k_s": k_s, "n": n, "T_s": T_s, "aktiv": aktiv}


# ── Gueltigkeitspruefung ────────────────────────────────────────────────────

def test_vollstaendiges_system_ist_gueltig():
    assert system_gueltig(sys_())


@pytest.mark.parametrize("aenderung", [
    {"y_a": None}, {"t0": None}, {"T_s": None},
    {"d_u": 0},            # kein Sprung -> keine Antwort
    {"k_s": 0},            # keine Verstaerkung
    {"T_s": 0}, {"T_s": -1},
    {"n": 0}, {"n": 11}, {"n": None},
    {"y_a": float("nan")},
])
def test_unvollstaendige_systeme_sind_ungueltig(aenderung):
    assert not system_gueltig(sys_(**aenderung))


def test_krumme_ordnung_wird_gerundet():
    erg = vergleich([sys_(n=3.4, T_s=1.0, t0=0.0)])
    # n=3.4 -> 3; Kurve muss der eines PT3 entsprechen
    erwartet = ptn_sprungantwort(np.asarray(erg["zeit"]), 1.0, 3, 0.0, 0.0, 1.0, 1.0)
    np.testing.assert_allclose(erg["kurven"][0]["daten"], erwartet, rtol=1e-12)


# ── Zeitachse ───────────────────────────────────────────────────────────────

def test_zeitachse_ohne_messung_reicht_bis_99_prozent():
    T_s, n, t0 = 2.0, 3, 1.0
    z = zeitachse([sys_(n=n, T_s=T_s, t0=t0)])
    assert len(z) == SYNTH_PUNKTE
    assert z[-1] == pytest.approx(t0 + T99[n] * T_s)
    # am Ende ist die Antwort tatsaechlich nahe 99 %
    y = ptn_sprungantwort(np.array([z[-1]]), T_s, n, t0, 0.0, 1.0, 1.0)
    assert y[0] == pytest.approx(0.99, abs=0.005)


def test_zeitachse_richtet_sich_nach_dem_langsamsten_system():
    schnell, langsam = sys_(T_s=1.0, n=1), sys_(T_s=5.0, n=10)
    z = zeitachse([schnell, langsam])
    assert z[-1] == pytest.approx(T99[10] * 5.0)


def test_messdaten_haben_vorrang():
    eigene = [0.0, 1.0, 2.0, 3.0]
    assert zeitachse([sys_()], zeit_daten=eigene) == eigene


def test_zeitachse_ohne_gueltiges_system_ist_leer():
    assert zeitachse([sys_(T_s=None)]) == []


# ── Vergleich ───────────────────────────────────────────────────────────────

def test_nur_aktive_systeme_werden_gerechnet():
    erg = vergleich([sys_(name="A"), sys_(name="B", aktiv=False), sys_(name="C")])
    assert [k["name"] for k in erg["kurven"]] == ["A", "C"]
    # der Index verweist auf die Position in der Eingabeliste
    assert [k["index"] for k in erg["kurven"]] == [0, 2]


def test_ungueltiges_system_wird_uebersprungen_ohne_fehler():
    erg = vergleich([sys_(name="gut"), sys_(name="kaputt", T_s=-1)])
    assert [k["name"] for k in erg["kurven"]] == ["gut"]


def test_ohne_namen_wird_durchnummeriert():
    erg = vergleich([sys_(name=""), sys_(name="")])
    assert [k["name"] for k in erg["kurven"]] == ["System 1", "System 2"]


def test_kurve_startet_bei_ya_und_endet_bei_ya_plus_ks_du():
    erg = vergleich([sys_(y_a=10.0, k_s=2.0, d_u=3.0, n=2, T_s=1.0, t0=0.0)])
    daten = erg["kurven"][0]["daten"]
    assert daten[0] == pytest.approx(10.0)
    assert daten[-1] == pytest.approx(10.0 + 6.0, rel=0.02)


def test_fehlerintegral_null_bei_passendem_modell():
    T_s, n, t0 = 2.0, 3, 0.0
    zeit = np.linspace(0, 40, 400)
    mess = ptn_sprungantwort(zeit, T_s, n, t0, 0.0, 1.0, 1.0)
    erg = vergleich([sys_(n=n, T_s=T_s, t0=t0)],
                    zeit_daten=zeit.tolist(), mess_daten=mess.tolist())
    assert erg["fehlerintegral"][0] == pytest.approx(0.0, abs=1e-12)


def test_fehlerintegral_unterscheidet_modelle():
    T_s, n, t0 = 2.0, 3, 0.0
    zeit = np.linspace(0, 40, 400)
    mess = ptn_sprungantwort(zeit, T_s, n, t0, 0.0, 1.0, 1.0)
    erg = vergleich([sys_(name="passt", n=3, T_s=2.0),
                     sys_(name="daneben", n=5, T_s=2.0)],
                    zeit_daten=zeit.tolist(), mess_daten=mess.tolist())
    assert erg["fehlerintegral"][0] < erg["fehlerintegral"][1]


def test_ohne_messung_kein_fehlerintegral():
    erg = vergleich([sys_()])
    assert erg["fehlerintegral"] == [None]


def test_abgeschaltetes_system_hat_kein_fehlerintegral():
    zeit = np.linspace(0, 20, 100)
    mess = ptn_sprungantwort(zeit, 2.0, 3, 0.0, 0.0, 1.0, 1.0)
    erg = vergleich([sys_(aktiv=False), sys_()],
                    zeit_daten=zeit.tolist(), mess_daten=mess.tolist())
    assert erg["fehlerintegral"][0] is None
    assert erg["fehlerintegral"][1] is not None


# ── AGP-Projektdatei ────────────────────────────────────────────────────────

def test_erstes_ptn_modell_wird_genommen():
    projekt = {
        "meta": {"fallname": "Teilnehmer Mueller"},
        "modelle": [
            {"Typ": "PT1TT", "k_M": 9, "n": 1, "T_M": 9},     # wird uebersprungen
            {"Typ": "PTn", "k_M": 1.5, "n": 4, "T_M": 2.5},
            {"Typ": "PTn", "k_M": 9, "n": 9, "T_M": 9},       # nur das erste zaehlt
        ],
    }
    m = ptn_modell_aus_projekt(projekt)
    assert m == {"name": "Teilnehmer Mueller", "k_s": 1.5, "n": 4, "T_s": 2.5}


def test_projekt_ohne_ptn_modell():
    assert ptn_modell_aus_projekt({"modelle": [{"Typ": "PT1TT", "k_M": 1, "n": 1, "T_M": 1}]}) is None
    assert ptn_modell_aus_projekt({}) is None


def test_projekt_modell_mit_unbrauchbaren_werten():
    assert ptn_modell_aus_projekt({"modelle": [{"Typ": "PTn", "k_M": "x", "n": 3, "T_M": 2}]}) is None
    assert ptn_modell_aus_projekt({"modelle": [{"Typ": "PTn", "k_M": 1, "n": 3, "T_M": 0}]}) is None


def test_signalwerte_aus_zeitverlaeufen():
    # In der Projektdatei liegen die Daten SPALTENweise: daten[i] = Spalte i.
    # u springt zwischen t=2 und t=3 von 0 auf 10.
    projekt = {"zeitverlaeufe": {
        "spalten": ["t", "y", "u"],
        "daten": [[0, 1, 2, 3, 4],          # t
                  [20, 20, 20, 21, 25],     # y
                  [0, 0, 0, 10, 10]],       # u
    }}
    s = signalwerte_aus_projekt(projekt)
    assert s["y_a"] == 20 and s["u_a"] == 0
    assert s["d_u"] == 10
    assert s["t0"] == 2          # letzter Zeitpunkt vor dem Sprung


def test_signalwerte_ohne_zeitverlaeufe():
    assert signalwerte_aus_projekt({}) is None
    # Spalte u fehlt -> keine Signalwerte ableitbar
    assert signalwerte_aus_projekt(
        {"zeitverlaeufe": {"spalten": ["t", "y"], "daten": [[0, 1], [5, 6]]}}) is None


def test_signalwerte_bei_ungleich_langen_spalten():
    """Kuerzeste Spalte bestimmt die Laenge – keine IndexError."""
    projekt = {"zeitverlaeufe": {
        "spalten": ["t", "y", "u"],
        "daten": [[0, 1, 2, 3], [10, 11, 12], [0, 0, 5]],
    }}
    s = signalwerte_aus_projekt(projekt)
    assert s is not None and s["y_a"] == 10


# ── Totzeit T_t (PTnTT) ─────────────────────────────────────────────────────

def test_totzeit_verschiebt_antwort_um_t_t():
    """PTnTT: die Antwort ist die reine PTn-Antwort, um t_t nach hinten
    verschoben (G(s) = k_S/(1+T*s)^n * e^{-t_t*s})."""
    t = np.linspace(0, 30, 601)
    mit = ptn_sprungantwort(t, 1.0, 3, 0.0, 0.0, 1.0, 1.0, 5.0)
    # Vor t0+t_t = 5 ist die Antwort noch 0
    assert np.allclose(mit[t <= 5.0], 0.0)
    # mit(t) == ohne(t-5): dieselbe Kurve, nur verschoben
    ohne_verschoben = ptn_sprungantwort(t - 5.0, 1.0, 3, 0.0, 0.0, 1.0, 1.0, 0.0)
    np.testing.assert_allclose(mit, ohne_verschoben, atol=1e-12)


def test_totzeit_null_wie_ohne_totzeit():
    """t_t = 0 (oder fehlend) ist exakt das bisherige PTn-Verhalten."""
    t = np.linspace(0, 20, 401)
    ohne = ptn_sprungantwort(t, 2.0, 4, 1.0, 0.0, 1.0, 1.0)
    tt0 = ptn_sprungantwort(t, 2.0, 4, 1.0, 0.0, 1.0, 1.0, 0.0)
    np.testing.assert_allclose(ohne, tt0, atol=1e-15)


def test_totzeit_negativ_ist_ungueltig():
    assert system_gueltig(dict(sys_(), T_t=0.0))
    assert system_gueltig(dict(sys_(), T_t=3.5))
    assert not system_gueltig(dict(sys_(), T_t=-1.0))
    assert not system_gueltig(dict(sys_(), T_t=float("nan")))


def test_vergleich_mit_totzeit_verschiebt_kurve_und_zeitachse():
    s = dict(sys_(t0=0.0, T_s=1.0, n=3), T_t=5.0)
    e = vergleich([s])
    zeit = np.asarray(e["zeit"])
    daten = np.asarray(e["kurven"][0]["daten"])
    # Vor der Totzeit ist die Kurve 0 ...
    assert np.allclose(daten[zeit <= 5.0], 0.0, atol=1e-9)
    # ... und die (synthetische) Zeitachse reicht ueber die Totzeit hinaus
    assert zeit[-1] > 5.0
