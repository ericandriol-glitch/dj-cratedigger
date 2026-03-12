"""Camelot wheel compatibility scoring for harmonic mixing."""

# Camelot wheel positions: number (1-12), letter (A=minor, B=major)
# Adjacent keys on the wheel are harmonically compatible.

VALID_KEYS = {f"{n}{letter}" for n in range(1, 13) for letter in ("A", "B")}


def parse_camelot(key: str) -> tuple[int, str]:
    """Parse a Camelot key string into (number, letter).

    Args:
        key: Camelot key like "8A" or "11B".

    Returns:
        Tuple of (number 1-12, letter "A" or "B").

    Raises:
        ValueError: If key is not valid Camelot notation.
    """
    key = key.strip()
    if key not in VALID_KEYS:
        raise ValueError(f"Invalid Camelot key: '{key}'")

    letter = key[-1]
    number = int(key[:-1])
    return number, letter


def camelot_distance(key_a: str, key_b: str) -> int:
    """Calculate the shortest distance between two keys on the Camelot wheel.

    Same inner/outer position (A↔B) counts as 0 steps on the number wheel.
    Returns the minimum clockwise or counter-clockwise distance (0-6).
    """
    num_a, _ = parse_camelot(key_a)
    num_b, _ = parse_camelot(key_b)

    diff = abs(num_a - num_b)
    return min(diff, 12 - diff)


def compatibility_score(key_a: str, key_b: str) -> float:
    """Score harmonic compatibility between two Camelot keys.

    Returns:
        Float 0.0-1.0:
        - 1.0:  Same key
        - 0.95: Adjacent on wheel (±1)
        - 0.9:  Inner/outer swap (same number, A↔B)
        - 0.8:  Energy boost (+7 on wheel)
        - 0.5:  Two steps away
        - 0.2:  Incompatible
    """
    num_a, letter_a = parse_camelot(key_a)
    num_b, letter_b = parse_camelot(key_b)

    # Same key
    if num_a == num_b and letter_a == letter_b:
        return 1.0

    # Inner/outer swap (same position, major↔minor)
    if num_a == num_b and letter_a != letter_b:
        return 0.9

    dist = camelot_distance(key_a, key_b)

    # Adjacent (±1 on wheel), same inner/outer
    if dist == 1 and letter_a == letter_b:
        return 0.95

    # Adjacent but cross inner/outer
    if dist == 1 and letter_a != letter_b:
        return 0.85

    # Energy boost (+7 on wheel, same letter)
    if dist == 7 and letter_a == letter_b:
        return 0.8

    # Two steps away, same letter
    if dist == 2 and letter_a == letter_b:
        return 0.5

    # Two steps away, different letter
    if dist == 2 and letter_a != letter_b:
        return 0.4

    # Everything else is a clash
    return 0.2


def compatible_keys(key: str, min_score: float = 0.7) -> list[str]:
    """Find all Camelot keys compatible with the given key.

    Args:
        key: Camelot key to find matches for.
        min_score: Minimum compatibility score (default 0.7).

    Returns:
        List of compatible keys sorted by score (descending).
    """
    results = []
    for candidate in sorted(VALID_KEYS):
        if candidate == key:
            continue
        score = compatibility_score(key, candidate)
        if score >= min_score:
            results.append((candidate, score))

    results.sort(key=lambda x: (-x[1], x[0]))
    return [k for k, _ in results]
