"""Uygulama genelinde paylaşılan Enum sabitleri."""
from enum import Enum


class ProgramPreference(str, Enum):
    """Üyelik başvurusundaki eğitim programı tercihi.

    Değerler kasıtlı olarak küçük harf ve snake_case'tir;
    DB ve API katmanı aynı string'i kullanır.
    """
    optimist    = "optimist"
    ilca        = "ilca"
    four_twenty = "420"
    wing_foil   = "wing_foil"
    para_yelken = "para_yelken"
