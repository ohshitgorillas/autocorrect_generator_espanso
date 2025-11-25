"""Typo generation algorithms."""


def generate_transpositions(word: str) -> list[str]:
    """Generate all possible adjacent character transpositions."""
    typos = []
    for i in range(len(word) - 1):
        typo = word[:i] + word[i + 1] + word[i] + word[i + 2 :]
        typos.append(typo)
    return typos


def generate_omissions(word: str) -> list[str]:
    """Generate single character omissions (only for words with 4+ characters)."""
    if len(word) < 4:
        return []

    typos = []
    for i in range(len(word)):
        typo = word[:i] + word[i + 1 :]
        typos.append(typo)
    return typos


def generate_duplications(word: str) -> list[str]:
    """Generate typos by duplicating each letter."""
    typos = []
    for i in range(len(word)):
        typo = word[:i] + word[i] + word[i:]
        typos.append(typo)
    return typos


def generate_insertions(word: str, adj_letters_map: dict[str, str]) -> list[str]:
    """Generate typos by inserting adjacent letters."""
    if not adj_letters_map:
        return []

    typos = []
    for i, char in enumerate(word):
        if char in adj_letters_map:
            for adj in adj_letters_map[char]:
                typos.append(word[: i + 1] + adj + word[i + 1 :])
                typos.append(word[:i] + adj + word[i:])

    return typos


def generate_replacements(word: str, adj_letters_map: dict[str, str]) -> list[str]:
    """Generate typos by replacing characters with adjacent keys."""
    if not adj_letters_map:
        return []

    typos = []
    for i, char in enumerate(word):
        if char in adj_letters_map:
            for replacement in adj_letters_map[char]:
                typos.append(word[:i] + replacement + word[i + 1 :])

    return typos


def generate_all_typos(
    word: str, adj_letters_map: dict[str, str] | None = None
) -> list[str]:
    """Generate all types of typos for a word."""
    typos = (
        generate_transpositions(word)
        + generate_omissions(word)
        + generate_duplications(word)
    )

    if adj_letters_map:
        typos.extend(generate_insertions(word, adj_letters_map))
        typos.extend(generate_replacements(word, adj_letters_map))

    return typos
