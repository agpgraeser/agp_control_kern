"""
ptn_zpk.py – PTn-Parameterbestimmung nach der Zeit-Prozent-Kennwert-Methode.

Portiert aus der React-App PTkPTn (`src/utils/ptnMath.ts`, Spec
SpecDocPTkPTn_v1.1 Schritt 4) im Zuge der Stack-Vereinheitlichung
(2026-08-17). Fachlich unveraendert – die Zahlenwerte sind bewusst 1:1
uebernommen, damit alte und neue App dieselben Ergebnisse liefern.

Verfahren: Aus den drei Zeiten t10/t50/t90 einer Sprungantwort wird
ueber das Verhaeltnis t10/t90 die Modellordnung n bestimmt und daraus
mit den alpha-Korrekturfaktoren die Zeitkonstante T. Zusaetzlich werden
die Nachbarordnungen n-1 und n+1 mitgerechnet, damit der Anwender
vergleichen kann.

Die Funktionen geben reine Python-Typen zurueck (Listen/floats), sind
also direkt JSON-serialisierbar und koennen ohne Umweg aus einer
FastAPI-Route zurueckgegeben werden.
"""

from __future__ import annotations

import math

import numpy as np

# ── Konstante Vorgabevektoren / -matrizen ────────────────────────────────────

#: MY_THEO_1090[i] = t10/t90 eines exakten PTn-Systems der Ordnung n = i+1
MY_THEO_1090: list[float] = [
    0.0460, 0.1371, 0.2073, 0.2614, 0.3046,
    0.3400, 0.3700, 0.3958, 0.4182, 0.4381,
]

#: ZPK-Korrekturfaktoren, Zeilen n = 1..10, Spalten alpha10 / alpha50 / alpha90
ALPHA: list[list[float]] = [
    [9.4340, 1.4430, 0.4344],
    [1.8762, 0.5956, 0.2571],
    [0.9066, 0.3740, 0.1879],
    [0.5727, 0.2723, 0.1497],
    [0.4108, 0.2141, 0.1251],
    [0.3172, 0.1764, 0.1078],
    [0.2567, 0.1499, 0.0950],
    [0.2147, 0.1304, 0.0850],
    [0.1840, 0.1154, 0.0770],
    [0.1607, 0.1034, 0.0704],
]

#: Elementweise Inverse von ALPHA (in der Alt-App als `alphaInv` exportiert)
ALPHA_INV: list[list[float]] = [[1.0 / v for v in zeile] for zeile in ALPHA]

_ALPHA_NP = np.array(ALPHA, dtype=float)

#: Anzahl Stuetzstellen des synthetischen Zeitvektors (ohne Messdaten)
SYNTH_PUNKTE = 1000


# ── PTn-Sprungantwort ────────────────────────────────────────────────────────

def ptn_sprungantwort_norm(t, T: float, n: int, t0: float):
    """Normierte PTn-Sprungantwort (Endwert 1).

        0                                    fuer t <= t0
        1 - e^-tau * SUMME_{i=0}^{n-1} tau^i / i!   fuer t > t0

    mit tau = (t - t0) / T. `t` darf Skalar oder Array sein; der
    Rueckgabetyp folgt der Eingabe.
    """
    skalar = np.isscalar(t)
    t_arr = np.asarray(t, dtype=float)

    if T <= 0 or n < 1:
        ergebnis = np.zeros_like(t_arr)
        return float(ergebnis) if skalar else ergebnis

    tau = (t_arr - t0) / T
    aktiv = t_arr > t0

    # Reihe SUMME tau^i / i! stabil aufbauen (Term_i = Term_{i-1} * tau / i)
    reihe = np.zeros_like(t_arr)
    term = np.ones_like(t_arr)
    for i in range(n):
        if i > 0:
            term = term * tau / i
        reihe = reihe + term

    with np.errstate(over="ignore", invalid="ignore"):
        ergebnis = np.where(aktiv, 1.0 - np.exp(-tau) * reihe, 0.0)
    ergebnis = np.nan_to_num(ergebnis, nan=0.0, posinf=1.0, neginf=0.0)

    return float(ergebnis) if skalar else ergebnis


def ptn_sprungantwort(t, T: float, n: int, t0: float,
                      y_a: float, k_s: float, d_u: float):
    """PTn-Sprungantwort in Prozessgroessen:  y(t) = y_A + k_S * dU * y_norm(t)."""
    return y_a + k_s * d_u * ptn_sprungantwort_norm(t, T, n, t0)


# ── ZPK-Identifikation ───────────────────────────────────────────────────────

def zpk_kennwerte(t0: float, t10: float, t50: float, t90: float) -> dict:
    """Bestimmt aus den drei Zeitwerten die PTn-Kennwerte.

    Liefert immer ein dict mit dem Schluessel ``gueltig``. Bei ungueltiger
    Eingabe (nicht monoton, t90 == t0, NaN) ist ``gueltig`` False und alle
    Ergebnisfelder sind None – bewusst kein Fehler, damit die Oberflaeche
    waehrend des Tippens weiterrechnen kann.

    Ergebnisfelder:
      n_opt, T_n_opt, var_n_opt          – beste Ordnung mit Zeitkonstante/Varianz
      n_opt_m1, T_n_opt_m1, var_n_opt_m1 – Nachbar n-1 (None wenn n_opt == 1)
      n_opt_p1, T_n_opt_p1, var_n_opt_p1 – Nachbar n+1 (None wenn n_opt == 10)
      zeiten                             – Zeitkonstante je Ordnung 1..10
      zw_werte, zw_mean, zw_var          – Zwischenwerte je Ordnung (10x3) und Statistik
      my_mess_1090, my_diff, t_vec       – Kennzahl t10/t90, Abstaende, relative Zeiten
    """
    leer = {
        "gueltig": False,
        "t_vec": None, "my_mess_1090": None, "my_diff": None, "n_opt": None,
        "zeiten": None, "zw_werte": None, "zw_mean": None, "zw_var": None,
        "n_opt_m1": None, "T_n_opt_m1": None, "var_n_opt_m1": None,
        "T_n_opt": None, "var_n_opt": None,
        "n_opt_p1": None, "T_n_opt_p1": None, "var_n_opt_p1": None,
    }

    werte = (t0, t10, t50, t90)
    if any(v is None or not math.isfinite(v) for v in werte):
        return leer
    if not (t0 <= t10 <= t50 <= t90):
        return leer

    t10r, t50r, t90r = t10 - t0, t50 - t0, t90 - t0
    if t90r == 0:
        return leer

    t_vec = np.array([t10r, t50r, t90r], dtype=float)

    my_mess_1090 = t10r / t90r
    my_diff = [abs(my_mess_1090 - v) for v in MY_THEO_1090]

    # argmin: bei Gleichstand gewinnt die kleinere Ordnung (wie in der Alt-App)
    n_opt = int(np.argmin(my_diff)) + 1

    # Zeitkonstante je Ordnung:  T_n = 1/3 * (a10*t10 + a50*t50 + a90*t90)
    zeiten = (_ALPHA_NP @ t_vec) / 3.0

    # Zwischenwerte: die drei Einzelschaetzungen je Ordnung (10x3)
    zw_werte = (_ALPHA_NP * t_vec) / 3.0
    zw_mean = zw_werte.mean(axis=1)
    zw_var = zw_werte.var(axis=1)          # Populationsvarianz (ddof=0)

    ergebnis = {
        "gueltig": True,
        "t_vec": [t10r, t50r, t90r],
        "my_mess_1090": my_mess_1090,
        "my_diff": my_diff,
        "n_opt": n_opt,
        "zeiten": zeiten.tolist(),
        "zw_werte": zw_werte.tolist(),
        "zw_mean": zw_mean.tolist(),
        "zw_var": zw_var.tolist(),
        "T_n_opt": float(zeiten[n_opt - 1]),
        "var_n_opt": float(zw_var[n_opt - 1]),
        "n_opt_m1": None, "T_n_opt_m1": None, "var_n_opt_m1": None,
        "n_opt_p1": None, "T_n_opt_p1": None, "var_n_opt_p1": None,
    }

    # Nachbarordnungen; an den Raendern gibt es nur einen Nachbarn
    if n_opt > 1:
        m1 = n_opt - 1
        ergebnis.update(n_opt_m1=m1,
                        T_n_opt_m1=float(zeiten[m1 - 1]),
                        var_n_opt_m1=float(zw_var[m1 - 1]))
    if n_opt < 10:
        p1 = n_opt + 1
        ergebnis.update(n_opt_p1=p1,
                        T_n_opt_p1=float(zeiten[p1 - 1]),
                        var_n_opt_p1=float(zw_var[p1 - 1]))

    return ergebnis


# ── Abweichungen Messung ./. Modell ──────────────────────────────────────────

def abweichung(zeit: list[float], mess: list[float], modell: list[float]) -> dict:
    """Abweichung, Abweichungsquadrat und laufendes Integral SUMME dy^2*dt.

    Gibt leere Listen zurueck, wenn keine oder unpassend lange Messdaten
    vorliegen (dann ist der Vergleich nicht definiert).
    """
    if not modell or not mess or len(mess) != len(modell):
        return {"diffs": [], "diff_qu": [], "kum_summe": [], "kum_summe_gesamt": None}

    m = np.asarray(mess, dtype=float)
    mo = np.asarray(modell, dtype=float)
    t = np.asarray(zeit, dtype=float)

    diffs = m - mo
    diff_qu = diffs ** 2

    dt = np.diff(t, prepend=t[0])          # erster Schritt = 0
    kum = np.cumsum(diff_qu * dt)

    return {
        "diffs": diffs.tolist(),
        "diff_qu": diff_qu.tolist(),
        "kum_summe": kum.tolist(),
        "kum_summe_gesamt": float(kum[-1]),
    }


# ── Gesamtauswertung ─────────────────────────────────────────────────────────

def zpk_auswertung(t0: float, t10: float, t50: float, t90: float,
                   k_s: float | None = None, d_u: float | None = None,
                   y_a: float | None = None,
                   zeit_daten: list[float] | None = None,
                   mess_daten: list[float] | None = None) -> dict:
    """Vollstaendige Auswertung: Kennwerte, Modellkurven und Abweichungen.

    Ohne Messdaten wird ein synthetischer Zeitvektor erzeugt
    (``SYNTH_PUNKTE`` Punkte von 0 bis t0 + T_opt * n_opt * 5), damit die
    Modellkurven auch ohne geladene Excel-Datei gezeichnet werden koennen.
    """
    zeit_daten = list(zeit_daten or [])
    mess_daten = list(mess_daten or [])

    kw = zpk_kennwerte(t0, t10, t50, t90)
    ergebnis = dict(kw)
    ergebnis.update(modell_opt=[], modell_m1=[], modell_p1=[],
                    zeit_effektiv=[],
                    abw_opt=abweichung([], [], []),
                    abw_m1=abweichung([], [], []),
                    abw_p1=abweichung([], [], []))

    if not kw["gueltig"]:
        return ergebnis

    n_opt, T_opt = kw["n_opt"], kw["T_n_opt"]

    # Zeitachse: Messdaten wenn vorhanden, sonst synthetisch
    if zeit_daten:
        zeit_eff = zeit_daten
    else:
        t_ende = t0 + T_opt * n_opt * 5
        if not math.isfinite(t_ende) or t_ende <= 0:
            return ergebnis
        zeit_eff = [(i / (SYNTH_PUNKTE - 1)) * t_ende for i in range(SYNTH_PUNKTE)]

    ergebnis["zeit_effektiv"] = zeit_eff

    if k_s is None or d_u is None or y_a is None:
        return ergebnis

    t_arr = np.asarray(zeit_eff, dtype=float)

    def kurve(T, n):
        if T is None or n is None or T <= 0:
            return []
        return ptn_sprungantwort(t_arr, T, n, t0, y_a, k_s, d_u).tolist()

    ergebnis["modell_opt"] = kurve(T_opt, n_opt)
    ergebnis["modell_m1"] = kurve(kw["T_n_opt_m1"], kw["n_opt_m1"])
    ergebnis["modell_p1"] = kurve(kw["T_n_opt_p1"], kw["n_opt_p1"])

    ergebnis["abw_opt"] = abweichung(zeit_eff, mess_daten, ergebnis["modell_opt"])
    ergebnis["abw_m1"] = abweichung(zeit_eff, mess_daten, ergebnis["modell_m1"])
    ergebnis["abw_p1"] = abweichung(zeit_eff, mess_daten, ergebnis["modell_p1"])

    return ergebnis
