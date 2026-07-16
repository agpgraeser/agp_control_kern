"""Rauchtests des Kerns (die ausführliche Abdeckung liegt historisch in den
Test-Suiten der Anwendungen, v. a. RegelkreisZustandsDemo/test_sim_core.py)."""

import numpy as np
import pytest

from agp_control_kern import (SimError, parse_matrix, parse_vector, parse_poly,
                              parse_complex_list, parse_zeitkonstanten,
                              zpk_to_tf, zk_to_tf, tf_to_ss,
                              matrix_zu_text, vektor_zu_text)


def test_parse_matrix_und_vector():
    A = parse_matrix("[0 1; -2 -3]")
    np.testing.assert_allclose(A, [[0, 1], [-2, -3]])
    b = parse_vector("0; 1", 2, "b")
    np.testing.assert_allclose(b, [0, 1])
    with pytest.raises(SimError):
        parse_matrix("[1 2; 3]")


def test_parse_poly_und_complex():
    np.testing.assert_allclose(parse_poly("[1 3 2]", "N"), [1, 3, 2])
    w = parse_complex_list("-1+2i; -1-2i", "Pole")
    assert w[0] == complex(-1, 2)


def test_zpk_und_zk_to_tf():
    z, n = zpk_to_tf([], [-1, -2], 2.0)
    np.testing.assert_allclose(z, [2.0])
    np.testing.assert_allclose(n, [1, 3, 2])
    z2, n2 = zk_to_tf("", "(s+1)(2s+1)", 5.0)
    np.testing.assert_allclose(z2, [5.0])
    np.testing.assert_allclose(n2, [2, 3, 1])


def test_zeitkonstanten_parser():
    np.testing.assert_allclose(
        parse_zeitkonstanten("(2*s+1)(0.5s^2 + 0.1s + 1)", "T"),
        [1.0, 0.7, 2.1, 1.0])


def test_tf_to_ss_rnf():
    erg = tf_to_ss([1.0], [1.0, 3.0, 2.0], "rnf")
    np.testing.assert_allclose(erg["A"], [[0, 1], [-2, -3]])
    assert erg["g0_tf"] == pytest.approx(0.5)
    assert erg["a_text"].startswith("[")


def test_texte():
    assert matrix_zu_text(np.array([[0.5, 1], [2, 3]])) == "[0.5 1; 2 3]"
    assert vektor_zu_text(np.array([1.0, 2.5]), "; ") == "1; 2.5"
