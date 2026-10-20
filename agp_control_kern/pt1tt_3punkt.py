"""
pt1tt_3punkt.py – PT1TT-Modell aus einer Sprungantwort, 3-Punkt-Methode.

Portiert aus der React-App PT1TT_Berechnung (`src/utils/pt1ttMath.ts`,
Netlify `pt1tt-3pkt.agpcontrol.com`) am 2026-10-20. Fachlich unveraendert;
der Referenzfall ist mit dem **Original-TypeScript** nachgerechnet (Tests).

Der Teilnehmer liest an der Messkurve drei Zeitpunkte ab, zu denen die
Regelgroesse 10 %, 50 % und 90 % ihres Hubs erreicht hat:

::

    dX  = XE - XA          dY = YE - YA          kS = dX / dY
    X10 = XA + 0.1*dX      X50 = XA + 0.5*dX     X90 = XA + 0.9*dX

    t10r = t10 - t0        t50r = t50 - t0       t90r = t90 - t0
    TT   = (t10r - 0.046*t90r) / 0.954
    TG   = (9.491*(t10r - TT) + 1.443*(t50r - TT) + 0.434*(t90r - TT)) / 3

Die drei Faktoren sind die Kehrwerte von ln(1/0.9), ln 2 und ln 10 -- jeder
Summand ist fuer ein echtes PT1-Glied eine Schaetzung der Zeitkonstanten,
TG ihr Mittel. TT und TG entstehen nur bei ``t0 < t10 < t50 < t90``.

Modellkurve und Fehlerintegral sind dieselben wie bei der Tangente
(:mod:`pt1tt_tangente`).
"""

from __future__ import annotations

import numpy as np

from .pt1tt_tangente import _zahl, guetemasse, modell_sprungantwort

#: Name des Verfahrens in den Blaettern Ablesung und Modelle der Projektdatei.
VERFAHREN = "3-Punkt"


def eingaben_gueltig(xa, xe, ya, ye, t0, t10, t50, t90) -> tuple[bool, str]:
    """Pruefung wie in der alten App: alles angegeben, ``t0 >= 0`` und
    ``t0 < t10 < t50 < t90``. Gibt (gueltig, Begruendung) zurueck; die
    Begruendung nennt die erste verletzte Bedingung."""
    werte = {"XA": _zahl(xa), "XE": _zahl(xe), "YA": _zahl(ya), "YE": _zahl(ye),
             "t0": _zahl(t0), "t10": _zahl(t10), "t50": _zahl(t50), "t90": _zahl(t90)}
    fehlend = [name for name, wert in werte.items() if wert is None]
    if fehlend:
        return False, "nicht angegeben: " + ", ".join(fehlend)
    if werte["t0"] < 0:
        return False, "t0 muss >= 0 sein"
    if not werte["t10"] > werte["t0"]:
        return False, "t10 > t0 verletzt"
    if not werte["t50"] > werte["t10"]:
        return False, "t50 > t10 verletzt"
    if not werte["t90"] > werte["t50"]:
        return False, "t90 > t50 verletzt"
    return True, ""


def kennwerte(xa=None, xe=None, ya=None, ye=None, t0=None,
              t10=None, t50=None, t90=None) -> dict:
    """Kennwerte der 3-Punkt-Methode -- so weit, wie die Eingaben reichen.

    Rueckgabe: ``d_x``, ``d_y``, ``k_s``, ``x10``, ``x50``, ``x90``,
    ``TT``, ``TG``. Nicht bestimmbare Groessen sind ``None``.
    """
    w_xa, w_xe = _zahl(xa), _zahl(xe)
    w_ya, w_ye = _zahl(ya), _zahl(ye)
    w_t0, w_10, w_50, w_90 = _zahl(t0), _zahl(t10), _zahl(t50), _zahl(t90)

    d_x = w_xe - w_xa if w_xa is not None and w_xe is not None else None
    d_y = w_ye - w_ya if w_ya is not None and w_ye is not None else None
    k_s = d_x / d_y if d_x is not None and d_y not in (None, 0) else None
    x10 = w_xa + 0.1 * d_x if d_x is not None else None
    x50 = w_xa + 0.5 * d_x if d_x is not None else None
    x90 = w_xa + 0.9 * d_x if d_x is not None else None

    tt = tg = None
    if None not in (w_t0, w_10, w_50, w_90) and w_t0 < w_10 < w_50 < w_90:
        r10, r50, r90 = w_10 - w_t0, w_50 - w_t0, w_90 - w_t0
        tt = (r10 - 0.046 * r90) / 0.954
        tg = (9.491 * (r10 - tt) + 1.443 * (r50 - tt) + 0.434 * (r90 - tt)) / 3

    return {"d_x": d_x, "d_y": d_y, "k_s": k_s,
            "x10": x10, "x50": x50, "x90": x90, "TT": tt, "TG": tg}


def auswertung(zeit=None, x_mess=None, xa=None, xe=None, ya=None, ye=None,
               t0=None, t10=None, t50=None, t90=None) -> dict:
    """Kennwerte, Modellkurve und Guetemasse in einem Aufruf.

    ``modelle`` hat hoechstens einen Eintrag (``kurve`` und Guetemasse wie
    bei der Tangente); ohne Messdaten oder ohne TT/TG bleibt die Liste leer.
    Die alte App verlangt ausserdem ``TG != 0`` -- hier ``TG > 0``, weil
    eine negative Zeitkonstante keine Sprungantwort ergibt.
    """
    kw = kennwerte(xa=xa, xe=xe, ya=ya, ye=ye, t0=t0, t10=t10, t50=t50, t90=t90)
    modelle: list[dict] = []
    t = np.asarray(zeit, dtype=float) if zeit is not None else np.empty(0)
    hat_messung = t.size > 0 and x_mess is not None and len(x_mess) == t.size
    if (hat_messung and kw["TT"] is not None and kw["TG"] is not None
            and kw["TG"] > 0 and kw["k_s"] is not None):
        kurve = modell_sprungantwort(t, float(_zahl(xa)), kw["k_s"], kw["d_y"],
                                     float(_zahl(t0)), kw["TT"], kw["TG"])
        eintrag = {"methode": 1, "zeit_name": "TG", "TG": kw["TG"], "kurve": kurve}
        eintrag.update(guetemasse(t, x_mess, kurve))
        modelle.append(eintrag)
    return {**kw, "modelle": modelle}


def projekt_zeilen(zeit=None, x_mess=None, xa=None, xe=None, ya=None, ye=None,
                   t0=None, t10=None, t50=None, t90=None,
                   verfahren: str = VERFAHREN) -> tuple[dict, list[dict]]:
    """Ablesung und Modell fuer die AGP-Projektdatei (Spec 25v07).

    Punkte P1-P3 = (t10, X10), (t50, X50), (t90, X90); X10 … sind aus XA/XE
    berechnet, abgelesen sind die Zeiten. Modell ``Typ = PT1TT``,
    ``T_T`` = TT, ``T_1`` = TG, ``Guete`` = Σ Δx²·Δt (ohne Messung leer).
    """
    erg = auswertung(zeit=zeit, x_mess=x_mess, xa=xa, xe=xe, ya=ya, ye=ye,
                     t0=t0, t10=t10, t50=t50, t90=t90)

    def wert(v):
        z = _zahl(v)
        return "" if z is None else z

    ablesung = {"y_A": wert(xa), "y_E": wert(xe), "u_A": wert(ya), "u_E": wert(ye),
                "t_0": wert(t0),
                "t_P1": wert(t10), "y_P1": wert(erg["x10"]),
                "t_P2": wert(t50), "y_P2": wert(erg["x50"]),
                "t_P3": wert(t90), "y_P3": wert(erg["x90"]), "Kommentar": ""}
    modelle: list[dict] = []
    if erg["TT"] is not None and erg["TG"] is not None and erg["TG"] > 0 \
            and erg["k_s"] is not None:
        guete = erg["modelle"][0]["integral_ende"] if erg["modelle"] else None
        modelle.append({"Typ": "PT1TT", "Methode": f"{verfahren} (TG)",
                        "k_M": erg["k_s"], "n": "", "T_M": "",
                        "T_T": erg["TT"], "T_1": erg["TG"], "Guete": wert(guete)})
    return ablesung, modelle


def ablesung_zu_eingaben(zeile: dict | None) -> dict:
    """Zeile aus dem Blatt Ablesung → Eingaben (Kernnamen)."""
    zeile = zeile or {}
    return {"xa": _zahl(zeile.get("y_A")), "xe": _zahl(zeile.get("y_E")),
            "ya": _zahl(zeile.get("u_A")), "ye": _zahl(zeile.get("u_E")),
            "t0": _zahl(zeile.get("t_0")), "t10": _zahl(zeile.get("t_P1")),
            "t50": _zahl(zeile.get("t_P2")), "t90": _zahl(zeile.get("t_P3"))}
