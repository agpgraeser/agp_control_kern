"""Tests der PTn-Bestimmung nach der Zeit-Prozent-Kennwert-Methode.

Kernpruefung ist die Gegenprobe: aus einer exakten PTn-Sprungantwort werden
t10/t50/t90 numerisch bestimmt; das Verfahren muss daraus wieder die
Ordnung n und die Zeitkonstante T gewinnen.
"""

import math

import numpy as np
import pytest

from agp_control_kern import (ALPHA, ALPHA_INV, MY_THEO_1090,
                              ptn_sprungantwort, ptn_sprungantwort_norm,
                              zpk_auswertung, zpk_kennwerte)
from agp_control_kern.ptn_zpk import abweichung


def _zeit_fuer_anteil(anteil: float, T: float, n: int, t0: float) -> float:
    """Sucht t mit y_norm(t) = anteil (Bisektion; Antwort ist monoton)."""
    lo, hi = t0, t0 + 100.0 * T * n
    for _ in range(200):
        mitte = (lo + hi) / 2
        if ptn_sprungantwort_norm(mitte, T, n, t0) < anteil:
            lo = mitte
        else:
            hi = mitte
    return (lo + hi) / 2


# ── Tabellen ────────────────────────────────────────────────────────────────

def test_tabellen_form_und_inverse():
    assert len(MY_THEO_1090) == 10
    assert len(ALPHA) == 10 and all(len(z) == 3 for z in ALPHA)
    for zeile_a, zeile_i in zip(ALPHA, ALPHA_INV):
        for a, i in zip(zeile_a, zeile_i):
            assert i == pytest.approx(1.0 / a)


# ── Sprungantwort ───────────────────────────────────────────────────────────

def test_sprungantwort_randwerte():
    # vor dem Sprung null, danach monoton gegen den Endwert
    assert ptn_sprungantwort_norm(-1.0, 1.0, 3, 0.0) == 0.0
    assert ptn_sprungantwort_norm(0.0, 1.0, 3, 0.0) == 0.0
    assert ptn_sprungantwort_norm(1e4, 1.0, 3, 0.0) == pytest.approx(1.0)

    # PT1 hat die bekannte 63-%-Eigenschaft bei t = T
    assert ptn_sprungantwort_norm(1.0, 1.0, 1, 0.0) == pytest.approx(1 - math.exp(-1))


def test_sprungantwort_prozessgroessen():
    # y(t0) = y_A, y(unendlich) = y_A + k_S*dU
    y = ptn_sprungantwort(np.array([0.0, 1e4]), 2.0, 2, 0.0, y_a=5.0, k_s=3.0, d_u=4.0)
    assert y[0] == pytest.approx(5.0)
    assert y[1] == pytest.approx(5.0 + 12.0)


def test_sprungantwort_akzeptiert_skalar_und_array():
    assert isinstance(ptn_sprungantwort_norm(1.0, 1.0, 2, 0.0), float)
    assert isinstance(ptn_sprungantwort_norm(np.array([1.0, 2.0]), 1.0, 2, 0.0), np.ndarray)


def test_ungueltige_zeitkonstante_gibt_null():
    assert ptn_sprungantwort_norm(5.0, 0.0, 3, 0.0) == 0.0
    assert ptn_sprungantwort_norm(5.0, -1.0, 3, 0.0) == 0.0


# ── Gegenprobe: exakte PTn-Systeme zurueckgewinnen ──────────────────────────

@pytest.mark.parametrize("n", range(1, 11))
def test_exaktes_system_wird_wiedergefunden(n):
    T, t0 = 2.5, 1.0
    t10 = _zeit_fuer_anteil(0.10, T, n, t0)
    t50 = _zeit_fuer_anteil(0.50, T, n, t0)
    t90 = _zeit_fuer_anteil(0.90, T, n, t0)

    kw = zpk_kennwerte(t0, t10, t50, t90)

    assert kw["gueltig"]
    assert kw["n_opt"] == n, f"Ordnung {n} nicht wiedergefunden"
    # Zeitkonstante auf 1 % genau (Tabellenwerte sind gerundet)
    assert kw["T_n_opt"] == pytest.approx(T, rel=0.01)


@pytest.mark.parametrize("n", range(1, 11))
def test_theoretisches_t10_t90_verhaeltnis(n):
    """t10/t90 eines exakten PTn muss der Tabelle MY_THEO_1090 entsprechen."""
    T, t0 = 1.0, 0.0
    t10 = _zeit_fuer_anteil(0.10, T, n, t0)
    t90 = _zeit_fuer_anteil(0.90, T, n, t0)
    assert t10 / t90 == pytest.approx(MY_THEO_1090[n - 1], abs=5e-4)


# ── Nachbarordnungen / Randfaelle ───────────────────────────────────────────

def test_nachbarn_am_unteren_rand():
    T, t0, n = 1.0, 0.0, 1
    kw = zpk_kennwerte(t0,
                       _zeit_fuer_anteil(0.10, T, n, t0),
                       _zeit_fuer_anteil(0.50, T, n, t0),
                       _zeit_fuer_anteil(0.90, T, n, t0))
    assert kw["n_opt"] == 1
    assert kw["n_opt_m1"] is None and kw["T_n_opt_m1"] is None
    assert kw["n_opt_p1"] == 2 and kw["T_n_opt_p1"] is not None


def test_nachbarn_am_oberen_rand():
    T, t0, n = 1.0, 0.0, 10
    kw = zpk_kennwerte(t0,
                       _zeit_fuer_anteil(0.10, T, n, t0),
                       _zeit_fuer_anteil(0.50, T, n, t0),
                       _zeit_fuer_anteil(0.90, T, n, t0))
    assert kw["n_opt"] == 10
    assert kw["n_opt_p1"] is None and kw["T_n_opt_p1"] is None
    assert kw["n_opt_m1"] == 9 and kw["T_n_opt_m1"] is not None


def test_nachbarn_in_der_mitte():
    kw = zpk_kennwerte(0.0, 1.0, 3.0, 8.0)
    assert kw["gueltig"]
    if 1 < kw["n_opt"] < 10:
        assert kw["n_opt_m1"] == kw["n_opt"] - 1
        assert kw["n_opt_p1"] == kw["n_opt"] + 1


# ── Zwischenwerte ───────────────────────────────────────────────────────────

def test_zwischenwerte_konsistent():
    kw = zpk_kennwerte(0.0, 1.0, 3.0, 8.0)
    zw = np.array(kw["zw_werte"])
    assert zw.shape == (10, 3)
    # Zeitkonstante je Ordnung ist die Summe der drei Einzelschaetzungen
    np.testing.assert_allclose(zw.sum(axis=1), kw["zeiten"], rtol=1e-12)
    # Mittelwert und Populationsvarianz zeilenweise
    np.testing.assert_allclose(zw.mean(axis=1), kw["zw_mean"], rtol=1e-12)
    np.testing.assert_allclose(zw.var(axis=1), kw["zw_var"], rtol=1e-12)


def test_varianz_null_bei_perfekt_passendem_system():
    """Bei einem exakten PTn streuen die drei Einzelschaetzungen kaum."""
    T, t0, n = 3.0, 0.0, 4
    kw = zpk_kennwerte(t0,
                       _zeit_fuer_anteil(0.10, T, n, t0),
                       _zeit_fuer_anteil(0.50, T, n, t0),
                       _zeit_fuer_anteil(0.90, T, n, t0))
    # T/3 pro Spalte -> Varianz klein gegenueber (T/3)^2
    assert kw["var_n_opt"] < 1e-3 * (T / 3) ** 2


# ── Ungueltige Eingaben ─────────────────────────────────────────────────────

@pytest.mark.parametrize("t0,t10,t50,t90", [
    (0.0, 5.0, 3.0, 8.0),      # nicht monoton (t50 < t10)
    (0.0, 1.0, 9.0, 8.0),      # nicht monoton (t90 < t50)
    (5.0, 1.0, 3.0, 8.0),      # t0 groesser als t10
    (0.0, 0.0, 0.0, 0.0),      # t90 == t0
    (0.0, 1.0, 3.0, float("nan")),
])
def test_ungueltige_eingaben(t0, t10, t50, t90):
    kw = zpk_kennwerte(t0, t10, t50, t90)
    assert kw["gueltig"] is False
    assert kw["n_opt"] is None


# ── Abweichungen ────────────────────────────────────────────────────────────

def test_abweichung_rechnet_integral():
    zeit = [0.0, 1.0, 2.0]
    mess = [0.0, 2.0, 4.0]
    modell = [0.0, 1.0, 1.0]
    a = abweichung(zeit, mess, modell)
    assert a["diffs"] == [0.0, 1.0, 3.0]
    assert a["diff_qu"] == [0.0, 1.0, 9.0]
    # dt: 0, 1, 1  ->  kumuliert 0, 1, 10
    assert a["kum_summe"] == [0.0, 1.0, 10.0]
    assert a["kum_summe_gesamt"] == pytest.approx(10.0)


def test_abweichung_ohne_daten():
    a = abweichung([], [], [])
    assert a["diffs"] == [] and a["kum_summe_gesamt"] is None
    # unterschiedliche Laengen sind ebenfalls kein gueltiger Vergleich
    assert abweichung([0, 1], [1.0], [1.0, 2.0])["diffs"] == []


def test_abweichung_null_bei_identischen_verlaeufen():
    a = abweichung([0.0, 1.0, 2.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert a["kum_summe_gesamt"] == pytest.approx(0.0)


# ── Gesamtauswertung ────────────────────────────────────────────────────────

def test_auswertung_ohne_messdaten_erzeugt_modellkurven():
    erg = zpk_auswertung(0.0, 1.0, 3.0, 8.0, k_s=2.0, d_u=1.0, y_a=0.0)
    assert erg["gueltig"]
    assert len(erg["zeit_effektiv"]) == 1000
    assert len(erg["modell_opt"]) == 1000
    # ohne Messdaten gibt es nichts zu vergleichen
    assert erg["abw_opt"]["diffs"] == []
    # Kurve startet bei y_A und laeuft gegen y_A + k_S*dU
    assert erg["modell_opt"][0] == pytest.approx(0.0)
    assert erg["modell_opt"][-1] == pytest.approx(2.0, rel=0.05)


def test_auswertung_ohne_kennwerte_liefert_keine_kurven():
    erg = zpk_auswertung(0.0, 1.0, 3.0, 8.0)      # k_s/d_u/y_a fehlen
    assert erg["gueltig"]
    assert erg["modell_opt"] == []


def test_auswertung_mit_messdaten_vergleicht():
    """Messdaten aus einem exakten PT3 -> Abweichung zum PT3-Modell ist winzig."""
    T, t0, n = 2.0, 0.0, 3
    k_s, d_u, y_a = 1.5, 2.0, 10.0
    zeit = np.linspace(0, 40, 400)
    mess = ptn_sprungantwort(zeit, T, n, t0, y_a, k_s, d_u)

    t10 = _zeit_fuer_anteil(0.10, T, n, t0)
    t50 = _zeit_fuer_anteil(0.50, T, n, t0)
    t90 = _zeit_fuer_anteil(0.90, T, n, t0)

    erg = zpk_auswertung(t0, t10, t50, t90, k_s=k_s, d_u=d_u, y_a=y_a,
                         zeit_daten=zeit.tolist(), mess_daten=mess.tolist())

    assert erg["n_opt"] == 3
    assert erg["zeit_effektiv"] == pytest.approx(zeit.tolist())
    assert len(erg["modell_opt"]) == len(zeit)
    # Restfehler nur aus den gerundeten Tabellenwerten
    assert erg["abw_opt"]["kum_summe_gesamt"] < 1e-3
    # das Nachbarmodell passt schlechter als das optimale
    assert erg["abw_p1"]["kum_summe_gesamt"] > erg["abw_opt"]["kum_summe_gesamt"]


def test_auswertung_ungueltig_bleibt_leer():
    erg = zpk_auswertung(0.0, 5.0, 3.0, 8.0)
    assert erg["gueltig"] is False
    assert erg["modell_opt"] == [] and erg["zeit_effektiv"] == []
