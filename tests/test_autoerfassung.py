"""Tests fuer agp_control_kern.autoerfassung (Ablesen bei 10/50/90 %).

Die ausfuehrlichen Faelle (Rauschen, fallender Sprung, Rueckrechnung der
Ordnung) laufen zusaetzlich ueber die API in PTn-ZPK/test_server.py.
"""

import math

import numpy as np
import pytest

from agp_control_kern import autoerfassung


def _pt1tt_messung(K=2.0, T=5.0, TT=1.5, t0=2.0, ya=10.0, ua=1.0, ue=3.0,
                   t_ende=60.0, punkte=1201):
    zeit = list(np.linspace(0.0, t_ende, punkte))
    y, u = [], []
    for t in zeit:
        u.append(ue if t > t0 else ua)
        tau = t - t0 - TT
        y.append(ya + K * (ue - ua) * (1 - math.exp(-tau / T)) if tau > 0 else ya)
    return zeit, y, u


def test_pt1tt_sprung_wird_abgelesen():
    K, T, TT, t0, ya = 2.0, 5.0, 1.5, 2.0, 10.0
    zeit, y, u = _pt1tt_messung(K=K, T=T, TT=TT, t0=t0, ya=ya)
    e = autoerfassung.erfassen(zeit, y, u)

    dy = K * 2.0
    assert e["ya"] == pytest.approx(ya, abs=1e-6)
    assert e["ye"] == pytest.approx(ya + dy, abs=0.01)
    assert e["ua"] == pytest.approx(1.0) and e["ue"] == pytest.approx(3.0)
    assert e["t0"] == pytest.approx(t0, abs=0.06)
    assert e["y50"] == pytest.approx(ya + 0.5 * dy, abs=0.01)
    for anteil, k in ((0.10, "t10"), (0.50, "t50"), (0.90, "t90")):
        soll = t0 + TT - T * math.log(1 - anteil)
        assert e[k] == pytest.approx(soll, abs=0.06)


def test_ohne_stellgroesse_bleibt_t0_offen():
    zeit, y, _ = _pt1tt_messung()
    e = autoerfassung.erfassen(zeit, y, None)
    assert e["t0"] is None and e["t0_geschaetzt"] is not None
    assert e["ua"] is None and e["ue"] is None
    assert e["t10"] < e["t50"] < e["t90"]


def test_konstante_messung_wird_gemeldet():
    with pytest.raises(autoerfassung.ErfassungError):
        autoerfassung.erfassen([float(i) for i in range(20)], [1.0] * 20)
