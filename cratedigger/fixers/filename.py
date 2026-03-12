"""Clean up and standardize filenames."""

import re
from dataclasses import dataclass
from pathlib import Path



@dataclass
class FileRename:
    old_path: Path
    new_path: Path
    reason: str


# Junk to strip from filenames
JUNK_STRIP = [
    (re.compile(r"\[www\..+?\]", re.IGNORECASE), "website watermark"),
    (re.compile(r"\(www\..+?\)", re.IGNORECASE), "website watermark"),
    (re.compile(r"www\.\S+", re.IGNORECASE), "URL"),
    (re.compile(r"https?://\S+", re.IGNORECASE), "URL"),
    (re.compile(r"_copy\b", re.IGNORECASE), "copy suffix"),
    (re.compile(r"__+"), "multiple underscores"),
]


def plan_filename_fixes(audio_files: list[Path], keep_bitrate_tag: bool = True) -> list[FileRename]:
    """
    Plan filename cleanups. Does NOT rename anything.

    Returns list of proposed renames.
    """
    renames: list[FileRename] = []

    for path in audio_files:
        stem = path.stem
        ext = path.suffix
        parent = path.parent
        new_stem = stem
        reasons: list[str] = []

        # Strip junk patterns
        for pattern, desc in JUNK_STRIP:
            if pattern.search(new_stem):
                new_stem = pattern.sub("", new_stem)
                reasons.append(f"removed {desc}")

        # Clean up multiple spaces
        if "  " in new_stem:
            new_stem = re.sub(r"\s{2,}", " ", new_stem)
            reasons.append("fixed spacing")

        # Trim leading/trailing whitespace and hyphens
        cleaned = new_stem.strip(" -")
        if cleaned != new_stem:
            new_stem = cleaned
            reasons.append("trimmed whitespace")

        # Only propose a rename if something actually changed
        if new_stem != stem:
            new_path = parent / f"{new_stem}{ext}"
            renames.append(FileRename(
                old_path=path,
                new_path=new_path,
                reason=", ".join(reasons),
            ))

    return renames


def apply_filename_fixes(renames: list[FileRename]) -> tuple[int, list[str]]:
    """
    Apply filename renames.

    Returns:
        (success_count, error_messages)
    """
    success = 0
    errors: list[str] = []

    for rename in renames:
        try:
            if rename.new_path.exists():
                errors.append(f"{rename.old_path.name}: target already exists ({rename.new_path.name})")
                continue
            rename.old_path.rename(rename.new_path)
            success += 1
        except Exception as e:
            errors.append(f"{rename.old_path.name}: {e}")

    return success, errors
