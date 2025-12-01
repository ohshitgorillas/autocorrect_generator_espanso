"""Espanso correction organization utilities."""

from collections import defaultdict

from loguru import logger

from entroppy.core import Correction
from entroppy.platforms.espanso.yaml_conversion import correction_to_yaml_dict


def organize_by_letter(
    corrections: list[Correction], verbose: bool = False
) -> dict[str, list[dict]]:
    """Group corrections by first letter of correct word."""
    by_letter = defaultdict(list)

    if verbose:
        logger.info(f"  Organizing {len(corrections)} corrections...")

    for correction in corrections:
        _, word, _ = correction

        first_char = word[0].lower() if word else ""

        if first_char.isalpha():
            file_key = first_char
        else:
            file_key = "symbols"

        yaml_dict = correction_to_yaml_dict(correction)
        by_letter[file_key].append(yaml_dict)

    return by_letter
