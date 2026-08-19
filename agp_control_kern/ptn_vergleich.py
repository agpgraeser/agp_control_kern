"""
ptn_vergleich.py – Vergleich mehrerer PTn-Streckenmodelle mit einer Messung.

Portiert aus der React-App PTkPTn-Vergleiche (`src/utils/math.ts`) im Zuge
der Stack-Vereinheitlichung (2026-08-17). Fachlich unveraendert.

Anwendungsfall: mehrere Teilnehmer haben fuer dieselbe Strecke je ein
PTn-Modell bestimmt. Hier werden ihre Sprungantworten gemeinsam
gezeichnet und – wenn eine Referenzmessung vorliegt – ueber das
Fehlerintegral verglichen.

Die PTn-Sprungantwort selbst kommt aus `ptn_zpk`; beide Programme der
Familie rechnen damit dieselbe Kurve.
"""

from __future__ import annotations

import math

import numpy as np

from .ptn_zpk import ptn_sprungantwort

#: Vielfaches der Zeitkonstante, nach dem ein PTn-System 99 % des
#: Endwertes erreicht hat (Index = Ordnung n). Bestimmt die Laenge der
#: Zeitachse, wenn keine Messung vorliegt.
T99: dict[int, float] = {
    1: 4.6060, 2: 6.6400, 3: 8.4060, 4: 10.046, 5: 11.6060,
    6: 13.1100, 7: 14.5720, 8: 16.0000, 9: 17.4040, 10: 18.7840,
}

#: Anzahl Stuetzstellen des synthetischen Zeitvektors (ohne Messdaten)
SYNTH_PUNKTE = 1000


def system_gueltig(sys: dict) -> bool:
    """Prueft, ob ein System vollstaendig und plausibel beschrieben ist.

    Erwartete Felder: y_a, t0, d_u, k_s, n, T_s. Die Ordnung n muss
    zwischen 1 und 10 liegen, d_u und k_s duerfen nicht 0 sein (sonst
    gibt es keine Sprungantwort), T_s muss positiv sein.
    """
    try:
        werte = [sys.get(k) for k in ("y_a", "t0", "d_u", "k_s", "T_s")]
        if any(v is None or not math.isfinite(float(v)) for v in werte):
            return False
        n = sys.get("n")
        if n is None or not math.isfinite(float(n)):
            return False
        n = int(round(float(n)))
        if not (1 <= n <= 10):
            return False
        if float(sys["d_u"]) == 0 or float(sys["k_s"]) == 0:
            return False
        if float(sys["T_s"]) <= 0:
            return False
        # Totzeit T_t ist optional; wenn angegeben, muss sie >= 0 sein.
        t_t = sys.get("T_t")
        if t_t is not None:
            t_t = float(t_t)
            if not math.isfinite(t_t) or t_t < 0:
                return False
    except (TypeError, ValueError):
        return False
    return True


def _ordnung(sys: dict) -> int:
    """Ordnung als ganze Zahl im Bereich 1..10 (die Modelle der Familie
    erlauben nur ganzzahlige Ordnungen; krumme Werte werden gerundet)."""
    return max(1, min(10, int(round(float(sys["n"])))))


def zeitachse(systeme: list[dict], zeit_daten: list[float] | None = None) -> list[float]:
    """Zeitachse fuer die Modellkurven.

    Mit Messdaten deren Zeitvektor, sonst ein synthetischer bis zu dem
    Zeitpunkt, an dem das langsamste System 99 % erreicht hat.
    """
    if zeit_daten:
        return list(zeit_daten)

    gueltige = [s for s in systeme if system_gueltig(s)]
    if not gueltige:
        return []

    t_ende = max(float(s["t0"]) + float(s.get("T_t") or 0.0)
                 + T99.get(_ordnung(s), 5.0) * float(s["T_s"])
                 for s in gueltige)
    if not math.isfinite(t_ende) or t_ende <= 0:
        return []
    return [(k / (SYNTH_PUNKTE - 1)) * t_ende for k in range(SYNTH_PUNKTE)]


def vergleich(systeme: list[dict],
              zeit_daten: list[float] | None = None,
              mess_daten: list[float] | None = None) -> dict:
    """Berechnet die Sprungantworten aller aktiven, gueltigen Systeme.

    `systeme` ist eine Liste von dicts mit den Feldern name, y_a, t0,
    d_u, k_s, n, T_s, aktiv und optional T_t (Totzeit >= 0, Vorgabe 0 =
    reines PTn-System). Ungueltige oder abgeschaltete Systeme
    werden uebersprungen – die Oberflaeche soll waehrend der Eingabe
    weiterzeichnen koennen.

    Liegt eine Messung vor, wird je System das Fehlerintegral
    SUMME (y_mess − y_modell)^2 · dt gebildet; damit lassen sich die
    Modelle objektiv vergleichen (kleiner ist besser).
    """
    zeit_daten = list(zeit_daten or [])
    mess_daten = list(mess_daten or [])

    zeit = zeitachse(systeme, zeit_daten)
    ergebnis = {"zeit": zeit, "kurven": [], "fehlerintegral": [None] * len(systeme)}
    if not zeit:
        return ergebnis

    t_arr = np.asarray(zeit, dtype=float)
    hat_messung = bool(zeit_daten) and len(mess_daten) == len(zeit)
    if hat_messung:
        m_arr = np.asarray(mess_daten, dtype=float)
        dt = np.diff(t_arr, prepend=t_arr[0])       # erster Schritt = 0

    for i, sys in enumerate(systeme):
        if not sys.get("aktiv", True) or not system_gueltig(sys):
            continue
        n = _ordnung(sys)
        t_t = float(sys.get("T_t") or 0.0)
        kurve = ptn_sprungantwort(t_arr, float(sys["T_s"]), n, float(sys["t0"]),
                                  float(sys["y_a"]), float(sys["k_s"]),
                                  float(sys["d_u"]), t_t)
        ergebnis["kurven"].append({
            "index": i,
            "name": sys.get("name") or f"System {i + 1}",
            "daten": kurve.tolist(),
        })
        if hat_messung:
            fehler = (m_arr - kurve) ** 2
            ergebnis["fehlerintegral"][i] = float(np.sum(fehler * dt))

    return ergebnis


# ── AGP-Projektdatei: Teilnehmer-Modell uebernehmen ──────────────────────────

def ptn_modell_aus_projekt(projekt: dict) -> dict | None:
    """Nimmt das erste PTn-Modell aus dem Blatt `Modelle` einer Projektdatei.

    Liefert {name, k_s, n, T_s} oder None, wenn die Datei kein PTn-Modell
    enthaelt. PT1TT-Modelle werden uebersprungen – dieses Programm
    vergleicht PTn-Modelle.
    """
    modelle = projekt.get("modelle") or []
    for zeile in modelle:
        if str(zeile.get("Typ", "")).strip().upper() != "PTN":
            continue
        try:
            k_s = float(zeile["k_M"])
            n = max(1, min(10, int(round(float(zeile["n"])))))
            T_s = float(zeile["T_M"])
        except (KeyError, TypeError, ValueError):
            continue
        if T_s <= 0:
            continue
        name = str((projekt.get("meta") or {}).get("fallname") or "").strip()
        return {"name": name, "k_s": k_s, "n": n, "T_s": T_s}
    return None


def signalwerte_aus_projekt(projekt: dict) -> dict | None:
    """Leitet YA, t0, UA und DU aus dem Blatt `Zeitverlaeufe` ab.

    Annahme wie in der Vorgaenger-App: Spalte `y` ist die Regelgroesse,
    Spalte `u` die Stellgroesse. YA/UA sind die Anfangswerte, DU die
    Sprunghoehe der Stellgroesse, t0 der Zeitpunkt des Sprungs.
    Liefert None, wenn die Datei keine brauchbaren Zeitverlaeufe hat.
    """
    # Achtung: in der Projektdatei ist `daten` SPALTENweise abgelegt –
    # daten[i] ist die komplette Spalte i, nicht eine Zeile.
    zv = projekt.get("zeitverlaeufe") or {}
    spalten = [str(s) for s in (zv.get("spalten") or [])]
    daten = zv.get("daten") or []
    if not spalten or not daten:
        return None

    def spalte(*kandidaten):
        for k in kandidaten:
            for i, s in enumerate(spalten):
                if s.strip().lower() == k:
                    return i
        return None

    i_t = spalte("t", "zeit", "time")
    i_y = spalte("y", "regelgroesse", "regelgröße")
    i_u = spalte("u", "stellgroesse", "stellgröße")
    if i_t is None or i_y is None or i_u is None:
        return None
    if max(i_t, i_y, i_u) >= len(daten):
        return None

    try:
        t = [float(v) for v in daten[i_t]]
        y = [float(v) for v in daten[i_y]]
        u = [float(v) for v in daten[i_u]]
    except (TypeError, ValueError):
        return None
    if not t or not y or not u:
        return None
    laenge = min(len(t), len(y), len(u))
    t, y, u = t[:laenge], y[:laenge], u[:laenge]

    y_a, u_a = y[0], u[0]
    # Sprungzeitpunkt: erste nennenswerte Aenderung der Stellgroesse
    u_ende = u[-1]
    d_u = u_ende - u_a
    t0 = t[0]
    if d_u != 0:
        schwelle = u_a + 0.5 * d_u
        for k in range(1, len(u)):
            if (d_u > 0 and u[k] >= schwelle) or (d_u < 0 and u[k] <= schwelle):
                t0 = t[k - 1]
                break

    return {"y_a": y_a, "t0": t0, "u_a": u_a, "d_u": d_u}
