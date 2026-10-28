"""
autoerfassung.py – automatisches Ablesen der 10/50/90-%-Eingaben aus Messdaten.

Grundlage des Automatisierungsgrads **c** (vollautomatisch): aus den geladenen
Messwerten werden YA, YE, UA, UE, t0, die drei Ablesehoehen Y10/Y50/Y90 und die
zugehoerigen Zeiten t10/t50/t90 bestimmt und in die Eingabefelder geschrieben.
Der Nutzer kann jeden Wert danach aendern - die Erfassung ist ein Vorschlag,
keine Festlegung.

Genutzt von PTn-ZPK und PT1TT-3Punkt (beide lesen bei 10/50/90 % ab). Die
Schluessel folgen der ZPK-Benennung (y = Messgroesse, u = Stellgroesse); die
3-Punkt-App ordnet sie im Frontend ihren Feldern zu (dort X = Ausgang).
Bis 2026-10-27 lag das Modul app-lokal in PTn-ZPK.

Robustheit gegen Messrauschen: Ruhe- und Endniveau werden als **Median** eines
Randbereichs bestimmt, nicht als Einzelwert. Die Schwellenzeiten werden
zwischen den beiden Nachbarpunkten **linear interpoliert**, sonst haengt das
Ergebnis an der Abtastrate.

Fallende Spruenge (DY < 0) sind mitbehandelt: gesucht wird jeweils der erste
Durchgang durch die Schwelle, unabhaengig von der Richtung.
"""

from __future__ import annotations

from statistics import median

# Anteil der Messpunkte am Anfang bzw. Ende, aus dem Ruhe- und Endniveau
# gebildet werden. 5 % ist ein Kompromiss: genug Punkte gegen Rauschen,
# kurz genug, um bei traegen Strecken nicht in den Uebergang zu geraten.
RANDANTEIL = 0.05
MIN_RANDPUNKTE = 3

# Ab welcher Abweichung vom Ruhewert gilt die Antwort als losgelaufen
# (Anteil des Gesamthubs). Nur als Notbehelf gedacht, wenn keine Stellgroesse
# vorliegt: eine Strecke hoeherer Ordnung laeuft nach dem Sprung fast waagerecht
# los, deshalb wird die Schwelle spaeter erreicht als der Sprung stattfand -
# 0,5 % haelt diesen Fehler klein, ohne im Rauschen unterzugehen.
LOSBRECH_ANTEIL = 0.005


class ErfassungError(ValueError):
    """Fehler mit verstaendlicher Meldung fuer das Frontend."""


def _randmedian(werte: list[float], vom_ende: bool) -> float:
    """Median des ersten bzw. letzten Randbereichs."""
    n = max(MIN_RANDPUNKTE, int(len(werte) * RANDANTEIL))
    n = min(n, len(werte))
    ausschnitt = werte[-n:] if vom_ende else werte[:n]
    return float(median(ausschnitt))


def _schnittzeit(zeit: list[float], werte: list[float], schwelle: float,
                 steigend: bool, ab_index: int = 0) -> float | None:
    """Zeitpunkt des ersten Schwellendurchgangs, linear interpoliert.

    `steigend` sagt, ob die Schwelle von unten oder von oben erreicht wird.
    Rueckgabe None, wenn die Schwelle im Messbereich nie erreicht wird - dann
    ist die Messung zu kurz oder der Endwert falsch geschaetzt.
    """
    erreicht = (lambda v: v >= schwelle) if steigend else (lambda v: v <= schwelle)
    for i in range(max(ab_index, 1), len(werte)):
        if not erreicht(werte[i]):
            continue
        v0, v1 = werte[i - 1], werte[i]
        t0, t1 = zeit[i - 1], zeit[i]
        if v1 == v0:                       # senkrechte Flanke: Zeitpunkt nehmen
            return float(t1)
        anteil = (schwelle - v0) / (v1 - v0)
        anteil = min(max(anteil, 0.0), 1.0)
        return float(t0 + anteil * (t1 - t0))
    return None


def _sprungindex(u_daten: list[float]) -> int | None:
    """Index der groessten Aenderung in der Stellgroesse (= Sprungstelle)."""
    if len(u_daten) < 2:
        return None
    groesste, stelle = 0.0, None
    for i in range(1, len(u_daten)):
        delta = abs(u_daten[i] - u_daten[i - 1])
        if delta > groesste:
            groesste, stelle = delta, i
    # Eine konstante Stellgroesse hat keinen Sprung - dann lieber nichts sagen.
    spanne = max(u_daten) - min(u_daten)
    if stelle is None or spanne == 0 or groesste < 0.5 * spanne:
        return None
    return stelle


def erfassen(zeit: list[float], y_daten: list[float],
             u_daten: list[float] | None = None) -> dict:
    """Liest alle ZPK-Eingaben aus einer gemessenen Sprungantwort ab.

    Rueckgabe: die Feldwerte (None, wo nichts bestimmbar war) plus `hinweise`
    mit Klartext zu allem, was der Nutzer nachpruefen sollte.
    """
    if not zeit or not y_daten or len(zeit) != len(y_daten):
        raise ErfassungError("Messdaten fehlen oder Zeit und Messgröße sind "
                             "unterschiedlich lang.")
    if len(zeit) < 2 * MIN_RANDPUNKTE:
        raise ErfassungError(f"Zu wenige Messpunkte ({len(zeit)}) für eine "
                             "automatische Erfassung.")

    hinweise: list[str] = []
    hat_u = bool(u_daten) and len(u_daten) == len(zeit)

    # ── Ruhe- und Endniveau der Ausgangsgroesse ──────────────────────────────
    ya_grob = _randmedian(y_daten, vom_ende=False)
    ye = _randmedian(y_daten, vom_ende=True)
    hub = ye - ya_grob
    if hub == 0:
        raise ErfassungError("Die Messgröße ändert sich nicht – es ist keine "
                             "Sprungantwort erkennbar.")
    steigend = hub > 0

    # ── Sprungzeitpunkt und Stellgroesse ─────────────────────────────────────
    ua = ue = None
    t0 = None
    if hat_u:
        stelle = _sprungindex(u_daten)
        if stelle is not None:
            t0 = float(zeit[stelle - 1])
            ua = float(median(u_daten[:stelle])) if stelle >= 1 else float(u_daten[0])
            ue = float(median(u_daten[stelle:]))
        else:
            hinweise.append("Die Stellgröße zeigt keinen eindeutigen Sprung – "
                            "UA, UE und t₀ bitte prüfen.")
    else:
        hinweise.append("Die Datei enthält keine Stellgröße: UA und UE müssen "
                        "von Hand eingetragen werden.")

    # Ohne brauchbare Stellgroesse ist t0 aus der Messung NICHT bestimmbar:
    # eine Strecke hoeherer Ordnung laeuft nach dem Sprung fast waagerecht los,
    # jede Schaetzung liegt daher zu spaet. Da t0 unmittelbar in die
    # ZPK-Rechnung eingeht, verfaelscht ein zu spaeter Wert die Ordnung massiv
    # (gemessen: aus PT5 wird PT1). Deshalb wird t0 dann NICHT eingetragen,
    # sondern nur als Anhaltspunkt genannt - wie UA und UE.
    t0_geschaetzt = None
    if t0 is None:
        schwelle = ya_grob + LOSBRECH_ANTEIL * hub
        t_los = _schnittzeit(zeit, y_daten, schwelle, steigend)
        if t_los is None:
            raise ErfassungError("Der Sprungzeitpunkt ließ sich nicht bestimmen.")
        davor = [t for t in zeit if t < t_los]
        t0_geschaetzt = float(davor[-1]) if davor else float(t_los)
        hinweise.append(
            f"t₀ lässt sich ohne Stellgröße nicht sicher bestimmen und bleibt "
            f"offen – die Messgröße läuft erst bei t = {t0_geschaetzt:.3f} "
            f"sichtbar an, der Sprung liegt davor. Bitte im Diagramm ablesen.")

    # ── Ruhewert praeziser: nur die Punkte vor dem Sprung ────────────────────
    # Fuer die Rechnung zaehlt der Anlaufpunkt, auch wenn t0 offen bleibt.
    t_grenze = t0 if t0 is not None else t0_geschaetzt
    vor_sprung = [y for t, y in zip(zeit, y_daten) if t < t_grenze]
    ya = float(median(vor_sprung)) if len(vor_sprung) >= MIN_RANDPUNKTE else ya_grob
    if len(vor_sprung) < MIN_RANDPUNKTE:
        hinweise.append("Vor dem Sprung liegen kaum Messpunkte – YA ist nur grob "
                        "geschätzt.")

    dy = ye - ya
    if dy == 0:
        raise ErfassungError("Ruhe- und Endwert sind gleich – kein auswertbarer Hub.")
    steigend = dy > 0

    # ── Ablesehoehen und Schwellenzeiten ─────────────────────────────────────
    a = ablesen(zeit, y_daten, ya, ye, t_grenze)
    hinweise.extend(a["hinweise"])

    return {
        "ya": ya,
        "ye": ye,
        "ua": ua,
        "ue": ue,
        "t0": t0,                          # None = offen, siehe hinweise
        "t0_geschaetzt": t0_geschaetzt,    # Anhaltspunkt, bewusst nicht gesetzt
        "y10": a["y10"], "y50": a["y50"], "y90": a["y90"],
        "t10": a["t10"], "t50": a["t50"], "t90": a["t90"],
        "hat_u": hat_u,
        "hinweise": hinweise,
    }


def ablesen(zeit: list[float], y_daten: list[float], ya: float, ye: float,
            t_ab: float | None = None) -> dict:
    """Hoehen bei 10/50/90 % zwischen ``ya`` und ``ye`` und die Zeiten, zu denen
    die Messung sie zuerst erreicht.

    Teil von :func:`erfassen`, aber auch einzeln nutzbar: korrigiert der
    Nutzer in Grad c Ruhe- oder Endwert bzw. t0, liest die App damit neu ab,
    statt die ganze Erfassung zu wiederholen. Gesucht wird erst ab ``t_ab``
    (dem Sprung), sonst faengt Rauschen davor die Schwelle ab.
    """
    if not zeit or len(zeit) != len(y_daten):
        raise ErfassungError("Messdaten fehlen oder Zeit und Messgröße sind "
                             "unterschiedlich lang.")
    dy = ye - ya
    if dy == 0:
        raise ErfassungError("Ruhe- und Endwert sind gleich – kein auswertbarer Hub.")
    steigend = dy > 0
    ab_index = 0 if t_ab is None else next(
        (i for i, t in enumerate(zeit) if t >= t_ab), len(zeit))

    erg: dict = {"hinweise": []}
    for anteil, name in ((0.10, "10"), (0.50, "50"), (0.90, "90")):
        schwelle = ya + anteil * dy
        erg["y" + name] = float(schwelle)
        erg["t" + name] = _schnittzeit(zeit, y_daten, schwelle, steigend, ab_index)

    fehlend = [k for k in ("t10", "t50", "t90") if erg[k] is None]
    if fehlend:
        erg["hinweise"].append(
            "Nicht abgelesen werden konnte: " + ", ".join(fehlend)
            + " – die Messung endet vermutlich vor dem Beharrungszustand"
              " oder Ruhe-/Endwert liegen außerhalb der Messung.")
    return erg
