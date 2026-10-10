"""Tests der AGP-Projektdatei (Formatversion 1, Spec V1)."""

import io

import pytest
from openpyxl import Workbook, load_workbook

from agp_control_kern import projektdatei as pd
from agp_control_kern import ProjektdateiError


BEISPIEL_SYSTEM = {
    "systemname": "PT2-Test", "eingabeform": "ss",
    "a_text": "[0 1; -2 -3]", "b_text": "0; 1", "c_text": "1 0",
    "u_min": "0", "u_max": "100", "k_s": "0.8", "y_min": "20",
    "beschreibung": "Testfall",
}


def test_neu_schreiben_lesen_roundtrip():
    p = pd.neu("Fall-A", "Beschreibung", programm="Test")
    p["system"] = dict(BEISPIEL_SYSTEM)
    inhalt = pd.schreiben(p, programm="Test", aktion="System geschrieben")
    q = pd.lesen(inhalt)
    assert q["meta"]["formatversion"] == 1
    assert q["meta"]["fallname"] == "Fall-A"
    # Historie: "angelegt" + "System geschrieben"
    aktionen = [h["aktion"] for h in q["meta"]["historie"]]
    assert aktionen == ["Projekt angelegt", "System geschrieben"]
    assert q["system"]["a_text"] == "[0 1; -2 -3]"
    assert q["stoerungen"] is None and q["modelle"] is None


def test_alle_tabellen_roundtrip():
    p = pd.neu("Fall-B", programm="Test")
    p["system"] = dict(BEISPIEL_SYSTEM)
    p["stoerungen"] = [{"Nr": 1, "Typ": "sinus", "Angriff": "ausgang",
                        "Aktiv": "ja", "Amplitude": 0.5, "Startzeit": 10,
                        "Frequenz": 0.05, "Phase": 0}]
    p["zeitverlaeufe"] = {"spalten": ["t", "u", "y"],
                          "daten": [[0, 1, 2], [50, 50, 50], [20, 20.5, 21]]}
    p["modelle"] = [{"Nr": 1, "Typ": "PTn", "Methode": "Zeit-Prozent",
                     "k_M": 0.8, "n": 3.4, "T_M": 2.2, "Guete": 0.01},
                    {"Nr": 2, "Typ": "PT1TT", "Methode": "Tangente",
                     "k_M": 0.8, "T_T": 1.1, "T_1": 6.5, "Guete": 0.02}]
    p["regler"] = [{"Nr": 1, "Modell_Nr": 1, "Verfahren": "Latzel",
                    "Reglertyp": "PI", "Optionen": "h_m=0.1", "T_A": 0,
                    "k_P": 1.2, "T_N": 4.3}]
    p["kennwerte"] = [{"Regler_Nr": 1, "Simulationsart": "fuehrungssprung",
                       "Toleranzband": 0.05, "h_m": 0.08, "T_aus": 22.5,
                       "u_max": 71.0}]
    q = pd.lesen(pd.schreiben(p, programm="Test", aktion="alles"))
    assert q["stoerungen"][0]["Typ"] == "sinus"
    assert q["stoerungen"][0]["Angriff"] == "ausgang"
    assert q["zeitverlaeufe"]["spalten"] == ["t", "u", "y"]
    assert q["zeitverlaeufe"]["daten"][2] == [20, 20.5, 21]
    assert len(q["modelle"]) == 2
    assert q["modelle"][1]["T_1"] == 6.5
    assert q["regler"][0]["k_P"] == 1.2
    assert q["kennwerte"][0]["T_aus"] == 22.5


def test_fremde_blaetter_bleiben_erhalten():
    """Programm B liest, ergänzt sein Blatt, schreibt – Blatt von A bleibt."""
    p = pd.neu("Fall-C", programm="A")
    p["system"] = dict(BEISPIEL_SYSTEM)
    inhalt_a = pd.schreiben(p, programm="A", aktion="System")
    q = pd.lesen(inhalt_a)
    q["modelle"] = [{"Nr": 1, "Typ": "PTn", "k_M": 1.0, "n": 3, "T_M": 1.0}]
    inhalt_b = pd.schreiben(q, programm="B", aktion="Modelle")
    r = pd.lesen(inhalt_b)
    assert r["system"]["systemname"] == "PT2-Test"     # von A, unangetastet
    assert r["modelle"][0]["n"] == 3                   # von B
    assert [h["programm"] for h in r["meta"]["historie"]] == ["A", "A", "B"]


def test_altformat_import():
    """RKZ-Systemdatei (nur Blatt System) wird beim Lesen überführt."""
    wb = Workbook()
    ws = wb.active
    ws.title = "System"
    ws.append(["Feld", "Wert"])
    labels = dict(pd.SYSTEM_FELDER)
    for key in ("systemname", "a_text", "b_text", "c_text",
                "u_min", "u_max", "k_s", "y_min"):
        ws.append([labels[key], BEISPIEL_SYSTEM[key]])
    buf = io.BytesIO()
    wb.save(buf)

    q = pd.lesen(buf.getvalue())
    assert q["meta"]["formatversion"] == 1
    assert q["meta"]["fallname"] == "PT2-Test"
    assert q["meta"]["angelegt_von"] == "Altformat-Import"
    assert q["system"]["k_s"] == "0.8"


def test_zu_neue_formatversion():
    p = pd.neu("Fall-D", programm="Test")
    p["meta"]["formatversion"] = 2
    inhalt = pd.schreiben(p)
    with pytest.raises(ProjektdateiError, match="Formatversion 2"):
        pd.lesen(inhalt)


def test_keine_agp_datei():
    wb = Workbook()
    wb.active.title = "Irgendwas"
    wb.active.append(["x"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ProjektdateiError, match="AGP-Datei"):
        pd.lesen(buf.getvalue())


def test_dateiname_schema():
    name = pd.dateiname("Fall A/B")
    assert name.startswith("Fall_A_B-20")
    assert name.endswith(".xlsx")


def test_teilsysteme_rundreise():
    """Kaskade (2026-10-08): Blatt Teilsysteme, eine Spalte je Teilsystem."""
    p = pd.neu("Kaskade")
    p["system"] = {"a_text": "-1", "b_text": "2", "c_text": "1", "u_min": 0,
                   "u_max": 100, "k_s": 2, "y_min": 0, "struktur": 2}
    p["teilsysteme"] = [
        {"a_text": "-1", "b_text": "2", "c_text": "1", "t_t": 0, "y_min": 0, "y_max": 60},
        {"a_text": "0 1; -0.01 -0.2", "b_text": "0; 0.01", "c_text": "1 0",
         "t_t": 2.5, "eingabeform": "zk", "nenner_zk_text": "(10s+1)^2"},
    ]
    q = pd.lesen(pd.schreiben(p))
    assert q["system"]["struktur"] == "2"
    assert len(q["teilsysteme"]) == 2
    assert q["teilsysteme"][1]["a_text"] == "0 1; -0.01 -0.2"
    assert float(q["teilsysteme"][1]["t_t"]) == 2.5
    assert q["teilsysteme"][1]["eingabeform"] == "zk"
    assert q["teilsysteme"][0]["y_max"] == "60"
    assert q["teilsysteme"][0].get("regler", "") == ""     # leer = ja


def test_teilsysteme_eigener_regler():
    """Kap. 54, F4: Zeile „Eigener Regler“ (nein = durchgeschaltet)."""
    p = pd.neu("Stellglied")
    p["teilsysteme"] = [
        {"a_text": "-5", "b_text": "5", "c_text": "1", "regler": "nein"},
        {"a_text": "-1", "b_text": "1", "c_text": "1"},
    ]
    q = pd.lesen(pd.schreiben(p))
    assert q["teilsysteme"][0]["regler"] == "nein"
    assert q["teilsysteme"][1]["regler"] == ""


def test_einzelkreis_hat_kein_blatt_teilsysteme():
    from openpyxl import load_workbook
    import io
    p = pd.neu("Einzel")
    p["system"] = {"a_text": "-1", "b_text": "1", "c_text": "1", "u_min": 0,
                   "u_max": 1, "k_s": 1, "y_min": 0}
    inhalt = pd.schreiben(p)
    assert "Teilsysteme" not in load_workbook(io.BytesIO(inhalt)).sheetnames
    assert pd.lesen(inhalt)["teilsysteme"] is None


def test_aufschaltungen_rundreise():
    """Kap. 54, F6: Blatt Aufschaltungen, eine Zeile je Aufschaltung."""
    p = pd.neu("Aufschaltung")
    p["stoerungen"] = [{"Nr": 1, "Typ": "sprung", "Angriff": "eingang2", "Aktiv": "ja",
                        "Amplitude": -10, "Startzeit": 20}]
    p["aufschaltungen"] = [
        {"Nr": 1, "Aktiv": "ja", "Stoerung": 1, "Punkt": "stellgroesse", "T_M": "",
         "T_tM": 0.5, "Form": "pdt1", "K_SA": -0.5, "T_V": 1, "T_1": 0.2},
        {"Nr": 2, "Aktiv": "nein", "Stoerung": 1, "Punkt": "sollwert_1", "Form": "frei",
         "Zaehler": "-0.5 -0.5", "Nenner": "0.2 1", "Kommentar": "PD"},
    ]
    q = pd.lesen(pd.schreiben(p))
    a = q["aufschaltungen"]
    assert len(a) == 2
    assert a[0]["Form"] == "pdt1" and float(a[0]["K_SA"]) == -0.5 and float(a[0]["T_tM"]) == 0.5
    assert a[1]["Punkt"] == "sollwert_1" and a[1]["Zaehler"] == "-0.5 -0.5"
    assert a[1]["Aktiv"] == "nein"


def test_ohne_aufschaltungen_kein_blatt():
    from openpyxl import load_workbook
    import io
    p = pd.neu("Ohne")
    inhalt = pd.schreiben(p)
    assert "Aufschaltungen" not in load_workbook(io.BytesIO(inhalt)).sheetnames
    assert pd.lesen(inhalt)["aufschaltungen"] is None
