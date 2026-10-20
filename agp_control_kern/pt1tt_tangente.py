"""
pt1tt_tangente.py – PT1TT-Modell aus einer Sprungantwort, Tangentenmethode.

Portiert aus der React-App PT1TT_Einspeicher_Tang (`src/utils/pt1ttMath.ts`)
nach `PT1TT_Einspeicher_Tang/SPEC-Portierung-Python.md` (2026-10-20).
Fachlich unveraendert; gepruefter Referenzfall siehe Abschnitt 6 der Spec.

Der Kern dient **zwei** Programmen der Familie:

* **PT1TT · Tangente** (Einspeichersystem): Der Teilnehmer legt die Tangente
  ueber zwei frei gewaehlte Punkte TP1 und TP2 auf der Messkurve fest -- ein
  Einspeichersystem hat keinen Wendepunkt.
* **PT1TT · Wendetangente**: dieselbe Rechnung, nur ist TP1 der Wendepunkt.

Deshalb heissen die Punkte hier neutral `tangentenpunkt1/2`; die
Oberflaechen benennen sie um.

Die inneren Namen des alten Quelltextes (`xWP`, `tWP`, `dx`, `dt`) stammen
noch von der Wendetangenten-App und sind hier **nicht** uebernommen -- sie
hiessen schon in der alten Oberflaeche XTP1/tTP1/XTP2/tTP2.

Rechenweg
---------
::

    dX = XE - XA        dY = YE - YA        kS = dX / dY
    a  = (XTP2 - XTP1) / (tTP2 - tTP1)          Steigung der Tangente
    t1 = tTP1 + (XA - XTP1) / a                 Tangente geschnitten mit XA
    t2 = tTP1 + (XE - XTP1) / a                 Tangente geschnitten mit XE

    Methode 1 (Kuepfmueller):  TT = t1 - t0,  TG  = t2 - t1
    Methode 2 (modifiziert):   TT = t1 - t0,  TG1 = t2 - tTP1
    Methode 3:                 beide

Zwei Pruefungen der alten App bleiben erhalten:

* Kennwerte entstehen nur bei ``t1 < tTP1 < t2`` -- sonst liegt die Tangente
  geometrisch falsch und es wird nichts ausgegeben.
* ``t0`` muss gesetzt und ``>= 0`` sein; **t1 und t2 werden dagegen
  unabhaengig von t0 gerechnet.**

Die Grenzen der Eingabepruefung sind am 20.10.2026 geaendert worden,
siehe :func:`eingaben_gueltig`.
"""

from __future__ import annotations

import math

import numpy as np

#: Methoden, die der Kern beherrscht. Die Oberflaeche der Tangenten-App
#: zeigt nur Methode 1; die Wendetangenten-App braucht alle drei.
METHODEN: tuple[int, ...] = (1, 2, 3)

#: Welche Ausgleichszeit welche Methode benutzt: 1 -> TG, 2 -> TG1,
#: 3 -> beide. Reihenfolge = Reihenfolge der Modelle in der Anzeige.
METHODE_ZEITEN: dict[int, tuple[str, ...]] = {
    1: ("TG",),
    2: ("TG1",),
    3: ("TG", "TG1"),
}


def _zahl(wert) -> float | None:
    """Wert als endliche Gleitkommazahl, sonst None.

    Ersetzt ``parseNum`` der alten App: leere Felder, Text und
    ``NaN``/``inf`` gelten als "nicht angegeben", nicht als Fehler.
    """
    if wert is None:
        return None
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return None
    return zahl if math.isfinite(zahl) else None


def eingaben_gueltig(
    xa, xe, t0, x_tp1, t_tp1, x_tp2, t_tp2
) -> tuple[bool, str]:
    """Pruefung der Eingabefelder, wie die Oberflaeche sie macht.

    Grenzen seit dem 20.10.2026 (Ansage Axel Graeser)::

        t0    >= 0
        XTP1  >= XA        XTP2 <= XE        XTP1 < XTP2
        tTP1  >  t0        tTP2 >  tTP1

    Die alte App verlangte ``XA < XTP1 < XE`` und ``XTP1 < XTP2 < XE``,
    liess dafuer aber zu, dass ein Tangentenpunkt **vor** dem Sprung liegt.
    Die neuen Grenzen lassen die Punkte bis an die Beharrungswerte heran und
    binden sie dafuer an den Sprungzeitpunkt. ``XTP1 < XTP2`` bleibt: ohne
    das waere die Steigung der Tangente null oder negativ.

    Die Reihenfolge ``XTP1 < XTP2`` ist hier die **einzige** Bedingung, die
    nicht aus der Ansage stammt.

    Gibt (gueltig, Begruendung) zurueck. Die Begruendung ist leer, wenn
    alles passt, und nennt sonst **die erste** verletzte Bedingung -- so
    kann die Oberflaeche sie unverkuerzt anzeigen.
    """
    werte = {
        "XA": _zahl(xa), "XE": _zahl(xe), "t0": _zahl(t0),
        "XTP1": _zahl(x_tp1), "tTP1": _zahl(t_tp1),
        "XTP2": _zahl(x_tp2), "tTP2": _zahl(t_tp2),
    }
    fehlend = [name for name, wert in werte.items() if wert is None]
    if fehlend:
        return False, "nicht angegeben: " + ", ".join(fehlend)

    if werte["t0"] < 0:
        return False, "t0 muss >= 0 sein"
    if not werte["XTP1"] >= werte["XA"]:
        return False, "XTP1 >= XA verletzt"
    if not werte["XTP2"] <= werte["XE"]:
        return False, "XTP2 <= XE verletzt"
    if not werte["XTP1"] < werte["XTP2"]:
        return False, "XTP1 < XTP2 verletzt"
    if not werte["tTP1"] > werte["t0"]:
        return False, "tTP1 > t0 verletzt"
    if not werte["tTP2"] > werte["tTP1"]:
        return False, "tTP2 > tTP1 verletzt"
    return True, ""


def kennwerte(
    xa=None, xe=None, ya=None, ye=None, t0=None,
    x_tp1=None, t_tp1=None, x_tp2=None, t_tp2=None,
) -> dict:
    """Kennwerte der Tangentenmethode.

    Rechnet so weit, wie die Eingaben reichen -- genau wie die alte App,
    die Felder einzeln und unvollstaendig fuellt. Nicht bestimmbare
    Groessen sind ``None``.

    Rueckgabe: ``d_x``, ``d_y``, ``k_s``, ``steigung``, ``t1``, ``t2``,
    ``TT``, ``TG``, ``TG1``.
    """
    w_xa, w_xe = _zahl(xa), _zahl(xe)
    w_ya, w_ye = _zahl(ya), _zahl(ye)
    w_t0 = _zahl(t0)
    w_x1, w_t1p = _zahl(x_tp1), _zahl(t_tp1)
    w_x2, w_t2p = _zahl(x_tp2), _zahl(t_tp2)

    d_x = w_xe - w_xa if w_xa is not None and w_xe is not None else None
    d_y = w_ye - w_ya if w_ya is not None and w_ye is not None else None
    k_s = d_x / d_y if d_x is not None and d_y not in (None, 0) else None

    steigung = t1 = t2 = None
    if None not in (w_xa, w_xe, w_x1, w_t1p, w_x2, w_t2p) and w_t2p != w_t1p:
        steigung = (w_x2 - w_x1) / (w_t2p - w_t1p)
        if steigung != 0:
            t1_roh = w_t1p + (w_xa - w_x1) / steigung
            t2_roh = w_t1p + (w_xe - w_x1) / steigung
            # Geometrische Pruefung: t1 vor TP1, t2 nach TP1
            if t1_roh < w_t1p < t2_roh:
                t1, t2 = t1_roh, t2_roh

    tt = tg = tg1 = None
    if t1 is not None and w_t0 is not None and w_t0 >= 0:
        tt = t1 - w_t0
        tg = t2 - t1          # Methode 1, Kuepfmueller
        tg1 = t2 - w_t1p      # Methode 2, modifiziert

    return {
        "d_x": d_x, "d_y": d_y, "k_s": k_s, "steigung": steigung,
        "t1": t1, "t2": t2, "TT": tt, "TG": tg, "TG1": tg1,
    }


def modell_sprungantwort(
    zeit, xa: float, k_s: float, d_y: float, t0: float, tt: float, tg: float
) -> np.ndarray:
    """Sprungantwort des PT1TT-Modells auf den Messzeitpunkten.

    ::

        t <= t0 + TT :  x = XA
        sonst        :  x = XA + kS*dY * (1 - exp(-(t - t0 - TT) / TG))

    ``TG`` ist je Methode die passende Ausgleichszeit (Methode 1: TG,
    Methode 2: TG1). ``TG > 0`` wird vorausgesetzt.
    """
    t = np.asarray(zeit, dtype=float)
    beginn = t0 + tt
    hub = k_s * d_y
    with np.errstate(over="ignore"):
        kurve = xa + hub * (1.0 - np.exp(-(t - beginn) / tg))
    return np.where(t <= beginn, float(xa), kurve)


def guetemasse(zeit, x_mess, x_modell) -> dict:
    """Abweichung der Messung vom Modell und ihr Fehlerintegral.

    ``abweichung`` = Messung - Modell, ``abweichung_quadrat`` deren
    Quadrat, ``integral`` das **laufende** Integral ``Summe dx^2*dt``
    nach der Rechteckregel ueber die Messzeitpunkte -- der erste Schritt
    mit ``dt = 0``, genau wie in der alten App -- und ``integral_ende``
    dessen Endwert.
    """
    t = np.asarray(zeit, dtype=float)
    mess = np.asarray(x_mess, dtype=float)
    modell = np.asarray(x_modell, dtype=float)

    abweichung = mess - modell
    quadrat = abweichung * abweichung

    schritt = np.zeros_like(t)
    if t.size > 1:
        schritt[1:] = np.diff(t)       # erster Schritt bleibt 0
    integral = np.cumsum(quadrat * schritt)

    return {
        "abweichung": abweichung,
        "abweichung_quadrat": quadrat,
        "integral": integral,
        "integral_ende": float(integral[-1]) if integral.size else None,
    }


def auswertung(
    zeit=None, x_mess=None, methode: int = 1,
    xa=None, xe=None, ya=None, ye=None, t0=None,
    x_tp1=None, t_tp1=None, x_tp2=None, t_tp2=None,
) -> dict:
    """Kennwerte, Modellkurven und Guetemasse in einem Aufruf.

    ``methode`` waehlt nach :data:`METHODE_ZEITEN`, welche Modelle
    entstehen (1, 2 oder beide). ``modelle`` ist eine Liste in der
    Reihenfolge der Anzeige; jeder Eintrag nennt ``methode``, ``zeit_name``
    ("TG" oder "TG1"), ``TG``, ``kurve`` und die Guetemasse. Ohne Messdaten
    bleibt die Liste leer -- die Kennwerte stehen trotzdem.
    """
    if methode not in METHODEN:
        raise ValueError(f"unbekannte Methode: {methode!r}")

    kw = kennwerte(xa=xa, xe=xe, ya=ya, ye=ye, t0=t0,
                   x_tp1=x_tp1, t_tp1=t_tp1, x_tp2=x_tp2, t_tp2=t_tp2)

    modelle: list[dict] = []
    t = np.asarray(zeit, dtype=float) if zeit is not None else np.empty(0)
    hat_messung = t.size > 0 and x_mess is not None and len(x_mess) == t.size

    if hat_messung and kw["TT"] is not None and kw["k_s"] is not None:
        for nummer, name in enumerate(METHODE_ZEITEN[methode], start=1):
            ausgleichszeit = kw[name]
            if ausgleichszeit is None or ausgleichszeit <= 0:
                continue
            kurve = modell_sprungantwort(
                t, float(xa), kw["k_s"], kw["d_y"],
                float(t0), kw["TT"], ausgleichszeit,
            )
            eintrag = {
                "methode": 1 if name == "TG" else 2,
                "zeit_name": name,
                "TG": ausgleichszeit,
                "kurve": kurve,
            }
            eintrag.update(guetemasse(t, x_mess, kurve))
            modelle.append(eintrag)

    return {**kw, "methode": methode, "modelle": modelle}


#: Name des Verfahrens in den Blättern Ablesung und Modelle der Projektdatei.
#: Die Wendetangenten-App setzt hier "Wendetangente" ein.
VERFAHREN = "Tangente"


def projekt_zeilen(
    zeit=None, x_mess=None, methode: int = 1,
    xa=None, xe=None, ya=None, ye=None, t0=None,
    x_tp1=None, t_tp1=None, x_tp2=None, t_tp2=None,
    verfahren: str = VERFAHREN,
) -> tuple[dict, list[dict]]:
    """Ablesung und Modelle für die AGP-Projektdatei (2026-10-20).

    Rückgabe ``(ablesung, modelle)`` im Format der Blätter ``Ablesung`` und
    ``Modelle`` – Nummern vergibt :func:`projektdatei.ablesung_ersetzen`.
    Je Ausgleichszeit der Methode (TG und/oder TG1) ein Modell
    ``Typ = PT1TT`` mit ``T_T`` = Totzeit und ``T_1`` = Ausgleichszeit;
    ``Guete`` ist Σ Δx²·Δt, ohne Messung leer.
    Liegt die Tangente geometrisch falsch, gibt es keine Modelle – die
    Ablesung wird trotzdem gespeichert.

    Volle Genauigkeit, nicht gerundet.
    """
    erg = auswertung(zeit=zeit, x_mess=x_mess, methode=methode,
                     xa=xa, xe=xe, ya=ya, ye=ye, t0=t0,
                     x_tp1=x_tp1, t_tp1=t_tp1, x_tp2=x_tp2, t_tp2=t_tp2)

    def wert(v):
        z = _zahl(v)
        return "" if z is None else z

    ablesung = {"y_A": wert(xa), "y_E": wert(xe), "u_A": wert(ya), "u_E": wert(ye),
                "t_0": wert(t0), "t_P1": wert(t_tp1), "y_P1": wert(x_tp1),
                "t_P2": wert(t_tp2), "y_P2": wert(x_tp2),
                "t_P3": "", "y_P3": "", "Kommentar": ""}

    guete = {m["zeit_name"]: m["integral_ende"] for m in erg["modelle"]}
    modelle: list[dict] = []
    if erg["TT"] is not None and erg["k_s"] is not None:
        for name in METHODE_ZEITEN[methode]:
            ausgleichszeit = erg[name]
            if ausgleichszeit is None or ausgleichszeit <= 0:
                continue
            # Spec 25v07, Blatt Modelle: PT1TT trägt T_T und T_1,
            # n und T_M (PTn-Spalten) bleiben leer.
            modelle.append({
                "Typ": "PT1TT",
                "Methode": f"{verfahren} M{1 if name == 'TG' else 2} ({name})",
                "k_M": erg["k_s"], "n": "", "T_M": "",
                "T_T": erg["TT"], "T_1": ausgleichszeit,
                "Guete": wert(guete.get(name)),
            })
    return ablesung, modelle


def ablesung_zu_eingaben(zeile: dict | None) -> dict:
    """Zeile aus dem Blatt Ablesung → Eingaben der Oberfläche (Kernnamen)."""
    zeile = zeile or {}
    return {"xa": _zahl(zeile.get("y_A")), "xe": _zahl(zeile.get("y_E")),
            "ya": _zahl(zeile.get("u_A")), "ye": _zahl(zeile.get("u_E")),
            "t0": _zahl(zeile.get("t_0")),
            "t_tp1": _zahl(zeile.get("t_P1")), "x_tp1": _zahl(zeile.get("y_P1")),
            "t_tp2": _zahl(zeile.get("t_P2")), "x_tp2": _zahl(zeile.get("y_P2"))}
