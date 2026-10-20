"""
pt1tt_vergleich.py – mehrere PT1TT-Modelle an einer Sprungantwort vergleichen.

Portiert aus der React-App PT1TT_Vergleich (`src/utils/math.ts`, Netlify
`pt1tt-vergleich.agpcontrol.com`) am 2026-10-20. Fachlich unveraendert:

* Gemeinsames Eingangssignal: XA (Anfangswert der Regelgroesse), t0
  (Sprungzeitpunkt), YA (Anfangswert der Stellgroesse) und DY (Sprung der
  Stellgroesse).
* Bis zu vier Systeme mit KS, TT, TG, je ein- oder ausgeschaltet.
  Ein System zaehlt nur mit ``KS != 0``, ``TT >= 0``, ``TG > 0``.
* Modell je System::

      t <= t0 + TT :  x = XA
      sonst        :  x = XA + KS*DY * (1 - exp(-(t - t0 - TT) / TG))

  -- dieselbe Kurve wie bei Tangente und 3-Punkt
  (:func:`pt1tt_tangente.modell_sprungantwort`, dort mit ``k_s*d_y``).
* Zeitachse: die Messzeit, sonst 500 Punkte von 0 bis
  ``t0 + max(TT) + 5*max(TG)``.
* Mit Messung je System Abweichung, Quadrat und Fehlerintegral
  (:func:`pt1tt_tangente.guetemasse`, gleiche Rechteckregel wie die alte App).

Neu gegenueber der alten App: :func:`systeme_aus_projekt` holt die
PT1TT-Modelle, die Tangente, Wendetangente und 3-Punkt in dieselbe
AGP-Projektdatei geschrieben haben.
"""

from __future__ import annotations

import numpy as np

from .pt1tt_tangente import _zahl, guetemasse, modell_sprungantwort

#: Anzahl der Systeme wie in der alten App
ANZAHL_SYSTEME = 4

#: Punkte der synthetischen Zeitachse ohne Messung (alte App: 500)
PUNKTE_OHNE_MESSUNG = 500


def signal_fehler(xa, t0, ya, dy) -> dict:
    """Welche Signalfelder fehlerhaft sind (wie ``validateInputs``)."""
    w_dy = _zahl(dy)
    return {"XA": _zahl(xa) is None, "t0": _zahl(t0) is None,
            "YA": _zahl(ya) is None, "DY": w_dy is None or w_dy == 0}


def system_fehler(system: dict) -> dict:
    """Welche Felder eines Systems fehlerhaft sind; ausgeschaltete Systeme
    sind nie fehlerhaft (wie in der alten App)."""
    if not system.get("aktiv"):
        return {"KS": False, "TT": False, "TG": False}
    ks, tt, tg = _zahl(system.get("KS")), _zahl(system.get("TT")), _zahl(system.get("TG"))
    return {"KS": ks is None or ks == 0,
            "TT": tt is None or tt < 0,
            "TG": tg is None or tg <= 0}


def zeitachse(t0: float, systeme: list[dict], zeit=None) -> np.ndarray:
    """Messzeit, sonst 0 … t0 + max(TT) + 5·max(TG) in 500 Punkten."""
    if zeit is not None and len(zeit) > 0:
        return np.asarray(zeit, dtype=float)
    t_ende = t0 + max(s["TT"] for s in systeme) + 5 * max(s["TG"] for s in systeme)
    return np.linspace(0.0, t_ende, PUNKTE_OHNE_MESSUNG)


def vergleich(xa=None, t0=None, ya=None, dy=None, systeme=None,
              zeit=None, x_mess=None) -> dict:
    """Modellkurven aller gueltigen, eingeschalteten Systeme.

    ``systeme``: Liste von dicts mit ``name``, ``KS``, ``TT``, ``TG``,
    ``aktiv`` (Reihenfolge = Systemnummer). Rueckgabe ``zeit`` (Achse) und
    ``modelle`` -- je gueltigem System ``index`` (0-basiert), ``name``,
    ``kurve`` und, mit passender Messung, die Guetemasse. Ohne gueltiges
    Signal oder ohne gueltiges System sind beide Listen leer (alte App).
    ``YA`` geht wie in der alten App nicht in die Kurve ein.
    """
    systeme = list(systeme or [])
    fehler = {"signal": signal_fehler(xa, t0, ya, dy),
              "systeme": [system_fehler(s) for s in systeme]}

    w_xa, w_t0, w_dy = _zahl(xa), _zahl(t0), _zahl(dy)
    leer = {"zeit": [], "modelle": [], "fehler": fehler}
    if w_xa is None or w_t0 is None or w_dy is None or w_dy == 0:
        return leer

    gueltig = []
    for i, s in enumerate(systeme):
        if not s.get("aktiv"):
            continue
        ks, tt, tg = _zahl(s.get("KS")), _zahl(s.get("TT")), _zahl(s.get("TG"))
        if ks is None or ks == 0 or tt is None or tt < 0 or tg is None or tg <= 0:
            continue
        gueltig.append({"index": i, "name": s.get("name") or f"System {i + 1}",
                        "KS": ks, "TT": tt, "TG": tg})
    if not gueltig:
        return leer

    t = zeitachse(w_t0, gueltig, zeit)
    mess_passt = (zeit is not None and x_mess is not None
                  and len(zeit) > 0 and len(x_mess) == len(zeit))
    modelle = []
    for g in gueltig:
        kurve = modell_sprungantwort(t, w_xa, g["KS"], w_dy, w_t0, g["TT"], g["TG"])
        eintrag = {**g, "kurve": kurve}
        if mess_passt:
            eintrag.update(guetemasse(t, x_mess, kurve))
        modelle.append(eintrag)
    return {"zeit": t, "modelle": modelle, "fehler": fehler}


def systeme_aus_projekt(projekt: dict, anzahl: int = ANZAHL_SYSTEME) -> list[dict]:
    """PT1TT-Modelle aus dem Blatt Modelle einer Projektdatei als Systeme.

    Name = Spalte ``Methode`` (z. B. "Tangente M1 (TG)"), KS = ``k_M``,
    TT = ``T_T``, TG = ``T_1`` (Spec 25v07). Andere Typen (PTn …) und
    unvollstaendige Zeilen werden uebergangen; hoechstens ``anzahl`` Systeme,
    in der Reihenfolge des Blatts.
    """
    systeme = []
    for zeile in projekt.get("modelle") or []:
        if str(zeile.get("Typ", "")).strip().upper() != "PT1TT":
            continue
        ks, tt, tg = _zahl(zeile.get("k_M")), _zahl(zeile.get("T_T")), _zahl(zeile.get("T_1"))
        if None in (ks, tt, tg):
            continue
        systeme.append({"name": str(zeile.get("Methode") or "").strip()
                        or f"Modell {zeile.get('Nr', '')}".strip(),
                        "KS": ks, "TT": tt, "TG": tg, "aktiv": True})
        if len(systeme) == anzahl:
            break
    return systeme


def signal_aus_projekt(projekt: dict) -> dict | None:
    """XA, t0, YA, DY aus der ersten Ablesung des Projekts, sonst None.

    Alle Ermittlungsverfahren lesen dasselbe Signal ab; die erste Zeile
    genuegt. DY = u_E − u_A.
    """
    for zeile in projekt.get("ablesung") or []:
        xa, t0 = _zahl(zeile.get("y_A")), _zahl(zeile.get("t_0"))
        ua, ue = _zahl(zeile.get("u_A")), _zahl(zeile.get("u_E"))
        if None in (xa, t0, ua, ue):
            continue
        return {"XA": xa, "t0": t0, "YA": ua, "DY": ue - ua,
                "verfahren": str(zeile.get("Verfahren", ""))}
    return None
