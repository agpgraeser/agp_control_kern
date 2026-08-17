"""
agp_control_kern – Gemeinsamer Fachkern der AGP·Control-Programmfamilie.

Stufe V2 der Vereinheitlichung (Spec 25v07 + Antwortkonzept). Re-exportiert
die Kernfunktionen, damit Anwendungen einfach schreiben können:

    from agp_control_kern import parse_matrix, tf_to_ss, SimError
    from agp_control_kern import projektdatei
"""

from .kern import (  # noqa: F401
    SimError,
    MAX_ORDNUNG_NENNER,
    MAX_ORDNUNG_ZAEHLER,
    parse_matrix,
    parse_vector,
    parse_poly,
    parse_complex_list,
    parse_zeitkonstanten,
    zpk_to_tf,
    zk_to_tf,
    tf_to_ss,
    matrix_zu_text,
    vektor_zu_text,
)
from . import projektdatei  # noqa: F401
from .projektdatei import ProjektdateiError  # noqa: F401
from . import ptn_zpk  # noqa: F401
from .ptn_zpk import (  # noqa: F401
    MY_THEO_1090,
    ALPHA,
    ALPHA_INV,
    ptn_sprungantwort,
    ptn_sprungantwort_norm,
    zpk_kennwerte,
    zpk_auswertung,
)
from . import ptn_vergleich  # noqa: F401
from .ptn_vergleich import (  # noqa: F401
    T99,
    vergleich,
    zeitachse,
    system_gueltig,
    ptn_modell_aus_projekt,
    signalwerte_aus_projekt,
)

__version__ = "0.1.0"
