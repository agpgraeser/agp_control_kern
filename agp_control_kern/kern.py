"""
kern.py – Gemeinsamer Fachkern der AGP·Control-Programmfamilie.

Herausgelöst aus RegelkreisZustandsDemo/sim_core.py (Stufe V2 der
Vereinheitlichung, 2026-07-16). Enthält:
- Parser (Matlab-Konvention): A, b, c, Polynome, Pole/Nullstellen,
  Zeitkonstanten-Faktoren
- Umwandlungen: zpk→tf, Zeitkonstanten→tf, tf→Zustandsraum
  (Regelungs-/Beobachtungs-/Modalform)
- Textausgabe der Matrizen/Vektoren mit voller Präzision

Die Simulation (Regelkreis, Streckentest) bleibt in RegelkreisZustandsDemo;
die Projektdatei-Ein-/Ausgabe liegt in projektdatei.py.
"""

from __future__ import annotations

import re

import numpy as np

class SimError(ValueError):
    """Fehler mit verständlicher Meldung für das Frontend."""


# ─── Parsen (Matlab-Konvention) ──────────────────────────────────────────────

# Toleranz gegenüber Klammern und typografischen Minuszeichen (z. B. aus
# PDF/Word kopiert): Klammern werden wie Leerzeichen behandelt, −/–/— wie '-'.
_ZEICHEN_ERSATZ = str.maketrans({
    "(": " ", ")": " ", "[": " ", "]": " ", "{": " ", "}": " ",
    "−": "-",   # − mathematisches Minus
    "–": "-",   # – Halbgeviertstrich
    "—": "-",   # — Geviertstrich
    " ": " ",   # geschütztes Leerzeichen
})


def _normalisieren(text: str) -> str:
    return text.translate(_ZEICHEN_ERSATZ)


def _parse_row(row: str, quelle: str) -> list[float]:
    werte = []
    for tok in row.replace(",", " ").split():
        try:
            werte.append(float(tok))
        except ValueError:
            raise SimError(
                f"{quelle}: '{tok}' ist keine Zahl. "
                "Dezimaltrennzeichen ist der Punkt, z.B. 0.5"
            )
    return werte


def parse_matrix(text: str, quelle: str = "Matrix A") -> np.ndarray:
    """Parst '[a11 a12; a21 a22]' (Matlab-Konvention) zu einer n×n-Matrix."""
    text = _normalisieren(text).strip()
    if not text:
        raise SimError(f"{quelle}: Eingabe ist leer.")
    zeilen = [z for z in text.split(";") if z.strip()]
    daten = [_parse_row(z, quelle) for z in zeilen]
    laengen = {len(z) for z in daten}
    if len(laengen) != 1:
        raise SimError(f"{quelle}: Zeilen haben unterschiedlich viele Elemente.")
    M = np.array(daten, dtype=float)
    if M.shape[0] != M.shape[1]:
        raise SimError(
            f"{quelle}: Matrix muss quadratisch sein, ist {M.shape[0]}×{M.shape[1]}."
        )
    return M


def parse_vector(text: str, n: int, quelle: str) -> np.ndarray:
    """Parst einen Vektor; Trenner sind Semikolon, Komma oder Leerzeichen."""
    text = _normalisieren(text).strip()
    if not text:
        raise SimError(f"{quelle}: Eingabe ist leer.")
    v = np.array(_parse_row(text.replace(";", " "), quelle), dtype=float)
    if len(v) != n:
        raise SimError(f"{quelle}: {len(v)} Werte eingegeben, {n} erwartet (Ordnung n={n}).")
    return v


# ─── Übertragungsfunktion G(s) → Zustandsraumdarstellung (v0.6) ─────────────

def parse_poly(text: str, quelle: str) -> np.ndarray:
    """
    Parst ein Polynom als Matlab-Zeilenvektor absteigender Potenzen,
    z. B. '[1 3 2]' für s² + 3s + 2. Führende Nullen werden entfernt.
    """
    text = _normalisieren(text).strip()
    if not text:
        raise SimError(f"{quelle}: Eingabe ist leer.")
    koeff = np.array(_parse_row(text.replace(";", " "), quelle), dtype=float)
    nicht_null = np.nonzero(np.abs(koeff) > 0)[0]
    if len(nicht_null) == 0:
        raise SimError(f"{quelle}: Polynom darf nicht das Nullpolynom sein.")
    return koeff[nicht_null[0]:]


def parse_complex_list(text: str, quelle: str) -> np.ndarray:
    """
    Parst eine Liste reeller/komplexer Zahlen (Pole/Nullstellen).
    Komplexe Zahlen ohne Leerzeichen schreiben, z. B. -1+2i oder -0.5-0.5j;
    Trenner sind Semikolon, Komma oder Leerzeichen.
    """
    text = _normalisieren(text).strip()
    if not text:
        return np.array([], dtype=complex)
    werte = []
    for tok in text.replace(";", " ").replace(",", " ").split():
        try:
            werte.append(complex(tok.replace("i", "j")))
        except ValueError:
            raise SimError(
                f"{quelle}: '{tok}' ist keine Zahl. Komplexe Werte ohne "
                "Leerzeichen schreiben, z. B. -1+2i; Dezimaltrennzeichen ist der Punkt."
            )
    return np.array(werte, dtype=complex)


def zpk_to_tf(nullstellen, pole, k_faktor: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Pole/Nullstellen/K → Zähler-/Nennerpolynom (reell). Komplexe Werte müssen
    paarweise konjugiert auftreten, sonst wäre das Polynom komplex.
    """
    nullstellen = np.atleast_1d(np.asarray(nullstellen, dtype=complex))
    pole = np.atleast_1d(np.asarray(pole, dtype=complex))
    if len(pole) == 0:
        raise SimError("G(s): mindestens ein Pol ist erforderlich.")

    def reell_machen(koeff: np.ndarray, name: str) -> np.ndarray:
        skala = max(np.max(np.abs(koeff)), 1.0)
        if np.max(np.abs(koeff.imag)) > 1e-9 * skala:
            raise SimError(
                f"G(s): {name} müssen reell oder paarweise konjugiert-komplex "
                "sein (z. B. -1+2i und -1-2i)."
            )
        return koeff.real

    zaehler = k_faktor * (np.poly(nullstellen) if len(nullstellen) else np.array([1.0]))
    nenner = np.poly(pole)
    return (reell_machen(np.atleast_1d(zaehler), "Nullstellen"),
            reell_machen(np.atleast_1d(nenner), "Pole"))


# ─── Zeitkonstanten-Form: G(s) = K·Π(T·s+1)/Π(…)  (Erweiterung 2026-07-16) ──

MAX_ORDNUNG_NENNER = 10   # Gesamtordnung des Nenners
MAX_ORDNUNG_ZAEHLER = 9   # Gesamtordnung des Zählers

# Eigene Normalisierung: Klammern sind hier BEDEUTUNGSTRAGEND (Faktorgrenzen)
# und dürfen nicht wie in _normalisieren durch Leerzeichen ersetzt werden.
# Eckige/geschweifte Klammern werden toleriert und zu runden gemacht.
_ZK_ERSATZ = str.maketrans({
    "[": "(", "]": ")", "{": "(", "}": ")",
    "−": "-", "–": "-", "—": "-",
    " ": " ",
})


def _parse_zk_faktor(f_text: str, quelle: str) -> np.ndarray:
    """
    Parst EINEN Zeitkonstanten-Faktor (Inhalt einer Klammer) zu Koeffizienten
    absteigender Potenzen. Erlaubt sind Faktoren 1. oder 2. Ordnung mit
    Absolutglied 1:  (T*s+1)  bzw.  (a2*s^2+a1*s+1).
    Toleriert: fehlendes '*', Leerzeichen, beliebige Termreihenfolge (1+2s),
    Malzeichen ·/×, Hochzahlen ²/³.
    """
    t = (f_text.replace(" ", "").replace("·", "*").replace("×", "*")
         .replace("²", "^2").replace("³", "^3"))
    if not t:
        raise SimError(f"{quelle}: leere Klammer () gefunden.")

    # e-Notation schützen, damit '+'/'-' im Exponenten nicht als Term-Trenner gilt
    t = re.sub(r"([0-9.])[eE]\+", r"\1e§p", t)
    t = re.sub(r"([0-9.])[eE]-", r"\1e§m", t)
    terme = re.findall(r"[+-]?[^+-]+", t)

    koeff = {0: 0.0, 1: 0.0, 2: 0.0}
    for term in terme:
        term = term.replace("e§p", "e+").replace("e§m", "e-")
        m = re.fullmatch(
            r"([+-]?)((?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)?\*?(?:(s)(?:\^(\d+))?)?",
            term)
        if not m or (m.group(2) is None and m.group(3) is None):
            raise SimError(
                f"{quelle}: Term '{term}' nicht verstanden. Erlaubt sind Faktoren "
                "wie (2s+1) oder (0.5s^2+0.1s+1); Dezimaltrennzeichen ist der Punkt.")
        vorz = -1.0 if m.group(1) == "-" else 1.0
        zahl = float(m.group(2)) if m.group(2) is not None else 1.0
        if m.group(3) is None:
            potenz = 0
        else:
            potenz = int(m.group(4)) if m.group(4) is not None else 1
        if potenz > 2:
            raise SimError(
                f"{quelle}: Faktor ({f_text}) hat Grad {potenz} – erlaubt sind nur "
                "Faktoren 1. oder 2. Ordnung: (T*s+1) oder (a2*s^2+a1*s+1).")
        koeff[potenz] += vorz * zahl

    if abs(koeff[0] - 1.0) > 1e-12:
        raise SimError(
            f"{quelle}: Faktor ({f_text}) hat das Absolutglied {koeff[0]:g} – die "
            "Zeitkonstanten-Form verlangt Absolutglied 1, z. B. (2s+1). Für andere "
            "Formen die Eingabe 'G(s) Polynome' oder 'G(s) Pole/Nullst.' verwenden.")
    if koeff[1] == 0.0 and koeff[2] == 0.0:
        raise SimError(f"{quelle}: Faktor ({f_text}) enthält kein s – kein gültiger "
                       "Zeitkonstanten-Faktor.")

    if koeff[2] != 0.0:
        return np.array([koeff[2], koeff[1], 1.0])
    return np.array([koeff[1], 1.0])


def parse_zeitkonstanten(text: str, quelle: str) -> np.ndarray:
    """
    Parst ein Produkt von Zeitkonstanten-Faktoren, z. B.
    '(2s+1)(0.5s^2+0.1s+1)', zu einem Polynom (Koeffizienten absteigender
    Potenzen, Absolutglied 1). Leere Eingabe → konstantes Polynom 1.
    """
    text = text.translate(_ZK_ERSATZ).strip()
    if not text:
        return np.array([1.0])

    faktoren = re.findall(r"\(([^()]*)\)", text)
    rest = re.sub(r"\([^()]*\)", "", text).replace("*", "").replace("·", "").strip()
    if not faktoren or rest:
        raise SimError(
            f"{quelle}: Faktoren bitte einzeln in Klammern schreiben, "
            "z. B. (2s+1)(0.5s^2+0.1s+1)."
            + (f" Nicht zuordenbar: '{rest}'." if rest else ""))

    poly = np.array([1.0])
    for f in faktoren:
        poly = np.convolve(poly, _parse_zk_faktor(f, quelle))
    return poly


def zk_to_tf(zaehler_text: str, nenner_text: str,
             k_faktor: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Zeitkonstanten-Eingabe → Zähler-/Nennerpolynom:
    G(s) = K · Π(Zähler-Faktoren) / Π(Nenner-Faktoren).
    Da alle Faktoren das Absolutglied 1 haben, gilt G(0) = K.
    Grenzen: Nenner-Gesamtordnung ≤ 10, Zähler-Gesamtordnung ≤ 9.
    """
    if k_faktor == 0:
        raise SimError("G(s): Verstärkung K darf nicht 0 sein.")
    zaehler = k_faktor * parse_zeitkonstanten(zaehler_text, "G(s) Zähler-Zeitkonstanten")
    nenner = parse_zeitkonstanten(nenner_text, "G(s) Nenner-Zeitkonstanten")

    if len(nenner) - 1 < 1:
        raise SimError("G(s): mindestens ein Zeitkonstanten-Faktor im Nenner "
                       "erforderlich, z. B. (5s+1).")
    if len(nenner) - 1 > MAX_ORDNUNG_NENNER:
        raise SimError(f"G(s): Nenner-Gesamtordnung {len(nenner) - 1} überschreitet "
                       f"das Maximum {MAX_ORDNUNG_NENNER}.")
    if len(zaehler) - 1 > MAX_ORDNUNG_ZAEHLER:
        raise SimError(f"G(s): Zähler-Gesamtordnung {len(zaehler) - 1} überschreitet "
                       f"das Maximum {MAX_ORDNUNG_ZAEHLER}.")
    return zaehler, nenner


def matrix_zu_text(M: np.ndarray) -> str:
    """Matrix als Matlab-Text mit voller Präzision (für die Eingabefelder)."""
    return "[" + "; ".join(" ".join(f"{v:.12g}" for v in zeile)
                           for zeile in np.atleast_2d(M)) + "]"


def vektor_zu_text(v: np.ndarray, trenner: str = " ") -> str:
    return trenner.join(f"{x:.12g}" for x in np.asarray(v).flatten())


def tf_to_ss(zaehler, nenner, normalform: str = "rnf") -> dict:
    """
    G(s) = Zähler/Nenner (Koeffizienten absteigender Potenzen) →
    Zustandsraumdarstellung in wählbarer Normalform:
      'rnf'   Regelungsnormalform (Begleitmatrix, immer möglich)
      'bnf'   Beobachtungsnormalform (Duale der RNF)
      'modal' Modalform (reelle Blockform; Fehler bei mehrfachen Polen)
    Voraussetzung: Zählergrad < Nennergrad (kein Durchgriff, D = 0).
    """
    zaehler = np.atleast_1d(np.asarray(zaehler, dtype=float))
    nenner = np.atleast_1d(np.asarray(nenner, dtype=float))

    n = len(nenner) - 1
    m = len(zaehler) - 1
    if n < 1:
        raise SimError("G(s): Nennergrad muss mindestens 1 sein.")
    if m >= n:
        raise SimError(
            f"G(s): Zählergrad ({m}) muss kleiner als der Nennergrad ({n}) sein "
            "(kein Durchgriff, D = 0)."
        )

    # auf monischen Nenner normieren
    zaehler = zaehler / nenner[0]
    nenner = nenner / nenner[0]

    warnungen: list[str] = []
    pole = np.roots(nenner)
    nullstellen = np.roots(zaehler) if m >= 1 else np.array([])

    # Hinweis bei (nahezu) kürzbaren gemeinsamen Faktoren
    for ns in nullstellen:
        if len(pole) and np.min(np.abs(pole - ns)) < 1e-9 * max(1.0, abs(ns)):
            warnungen.append(
                "Hinweis: Zähler und Nenner haben (nahezu) gemeinsame Wurzeln – "
                "die Realisierung ist nicht minimal."
            )
            break

    # Regelungsnormalform (Konvention wie die Beispiele der App:
    # letzte Zeile -a_0 … -a_{n-1}, b = [0…0 1]ᵀ, c = [β_0 … β_{n-1}])
    a_auf = nenner[1:][::-1]          # [a_0, a_1, …, a_{n-1}] (aufsteigend)
    beta = np.zeros(n)
    beta[:m + 1] = zaehler[::-1]      # [β_0, …, β_m]
    A_r = np.zeros((n, n))
    if n > 1:
        A_r[:-1, 1:] = np.eye(n - 1)
    A_r[-1, :] = -a_auf
    b_r = np.zeros(n)
    b_r[-1] = 1.0
    c_r = beta.copy()

    if normalform == "rnf":
        A, b, c = A_r, b_r, c_r
    elif normalform == "bnf":
        A, b, c = A_r.T, c_r.copy(), b_r.copy()
    elif normalform == "modal":
        A, b, c = _modalform(A_r, b_r, c_r, pole)
    else:
        raise SimError(f"Unbekannte Normalform: '{normalform}'.")

    # DC-Verstärkung G(0) = β_0 / a_0 (falls definiert)
    g0_tf: float | None = None
    if abs(a_auf[0]) > 1e-12:
        g0_tf = float(beta[0] / a_auf[0])

    return {
        "A": A.tolist(), "b": b.tolist(), "c": c.tolist(),
        "n": n,
        "zaehler": zaehler.tolist(), "nenner": nenner.tolist(),
        "pole": [{"re": float(p.real), "im": float(p.imag)} for p in pole],
        "nullstellen": [{"re": float(z.real), "im": float(z.imag)} for z in nullstellen],
        "g0_tf": g0_tf,
        "normalform": normalform,
        "a_text": matrix_zu_text(A),
        "b_text": vektor_zu_text(b, "; "),
        "c_text": vektor_zu_text(c, " "),
        "warnungen": warnungen,
    }


def _modalform(A_r, b_r, c_r, pole) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Reelle Modalform über die Eigenzerlegung der RNF: reelle Eigenwerte als
    1×1-Diagonalelemente, konjugierte Paare als 2×2-Blöcke [[σ, ω], [−ω, σ]].
    Bei (nahezu) mehrfachen Polen ist die Transformation singulär → Fehler.
    """
    n = A_r.shape[0]
    # (nahezu) mehrfache Pole erkennen
    for i in range(n):
        for j in range(i + 1, n):
            if abs(pole[i] - pole[j]) < 1e-6 * max(1.0, abs(pole[i])):
                raise SimError(
                    "Modalform ist bei mehrfachen (oder numerisch fast gleichen) "
                    "Polen nicht möglich – bitte Regelungs- oder "
                    "Beobachtungsnormalform wählen."
                )

    ew, EV = np.linalg.eig(A_r)
    # reelle Transformationsmatrix aufbauen: Re/Im-Spalten je konjugiertem Paar
    T = np.zeros((n, n))
    verbraucht = np.zeros(len(ew), dtype=bool)
    spalte = 0
    for i in range(len(ew)):
        if verbraucht[i]:
            continue
        if abs(ew[i].imag) < 1e-9 * max(1.0, abs(ew[i])):
            T[:, spalte] = EV[:, i].real
            verbraucht[i] = True
            spalte += 1
        else:
            # konjugierten Partner suchen
            partner = None
            for j in range(i + 1, len(ew)):
                if not verbraucht[j] and abs(ew[j] - np.conj(ew[i])) < \
                        1e-6 * max(1.0, abs(ew[i])):
                    partner = j
                    break
            if partner is None:
                raise SimError("Modalform: konjugiertes Polpaar nicht gefunden "
                               "(numerisches Problem).")
            T[:, spalte] = EV[:, i].real
            T[:, spalte + 1] = EV[:, i].imag
            verbraucht[i] = verbraucht[partner] = True
            spalte += 2

    if np.linalg.cond(T) >= 1e8:
        raise SimError(
            "Modalform: Transformationsmatrix ist schlecht konditioniert "
            "(Pole liegen zu dicht beieinander) – bitte Regelungs- oder "
            "Beobachtungsnormalform wählen."
        )

    A_m = np.linalg.solve(T, A_r @ T)
    b_m = np.linalg.solve(T, b_r)
    c_m = c_r @ T
    # numerisches Rauschen für eine saubere Blockstruktur entfernen
    schwelle = 1e-9 * max(1.0, np.max(np.abs(A_m)))
    A_m[np.abs(A_m) < schwelle] = 0.0
    return A_m, b_m, c_m

