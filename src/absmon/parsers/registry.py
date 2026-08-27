from .ford_auto import FordAutoParser
from .carmax_auto import CarMaxAutoParser
from .santander_drive import SantanderDriveParser
from .navient_ffelp import NavientFfelpParser

PARSERS = {
    "ford_auto": FordAutoParser,
    "carmax_auto": CarMaxAutoParser,
    "santander_drive": SantanderDriveParser,
    "navient_ffelp": NavientFfelpParser,
}


def get_parser(key: str):
    try:
        return PARSERS[key]()
    except KeyError as e:
        raise KeyError(f"No parser registered for '{key}'. Known: {sorted(PARSERS)}") from e
