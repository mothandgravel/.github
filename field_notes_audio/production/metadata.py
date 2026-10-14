"""Editable publishing copy, independent of recording and renderer identities."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from field_notes_audio import site
from field_notes_audio.storage import read_object


@dataclass(frozen=True)
class PublishingCopy:
    title: str
    description: str
    tags: tuple[str, ...]
    hashtags: tuple[str, ...]


def text(value: object, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be nonempty text of at most {limit} characters")
    if any(ord(character) < 32 and character != "\n" for character in value):
        raise ValueError(f"{label} contains control characters")
    value.encode("utf-8")
    return value.strip()


def title_text(value: object, label: str) -> str:
    title = text(value, label, 100)
    if "\n" in title or "<" in title or ">" in title:
        raise ValueError(f"{label} must be one plain-text line")
    return title


def words(value: object, label: str, hashtags: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > (3 if hashtags else 30):
        raise ValueError(f"Invalid {label} list")
    items = tuple(text(item, label, 80) for item in value)
    if len(set(items)) != len(items):
        raise ValueError(f"Duplicate {label}")
    if any(
        not re.fullmatch(r"#[A-Za-z][A-Za-z0-9]*", item)
        if hashtags
        else "," in item or "\n" in item
        for item in items
    ):
        raise ValueError(f"Invalid {label}")
    return items


def load_metadata(path: Path) -> dict:
    config = read_object(path)
    if set(config) != {"schema_version", "show", "shared_tags", "shared_hashtags", "episodes"}:
        raise ValueError("Unknown or missing publishing settings")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("Unsupported publishing settings version")
    show = config["show"]
    if not isinstance(show, dict) or set(show) != {"title", "description"}:
        raise ValueError("Publishing show needs a title and description")
    show["title"] = title_text(show["title"], "Show title")
    show["description"] = text(show["description"], "Show description", 5000)
    if (
        len((show["description"] + "\n").encode("utf-8")) > 5000
        or "<" in show["description"]
        or ">" in show["description"]
    ):
        raise ValueError("Show description must be plain text within 5000 UTF-8 bytes")
    words(config["shared_tags"], "tags")
    words(config["shared_hashtags"], "hashtags", True)
    overrides = config["episodes"]
    if not isinstance(overrides, dict):
        raise ValueError("Publishing episodes must be an object")
    # Validate even unselected overrides before creating a partial batch.
    for identifier, override in overrides.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
            raise ValueError("Invalid publishing episode ID")
        if not isinstance(override, dict) or set(override) - {
            "title",
            "description",
            "tags",
            "hashtags",
        }:
            raise ValueError(f"Invalid publishing override: {identifier}")
        for field, limit in (("title", 100), ("description", 4000)):
            if field in override:
                title_text(override[field], field) if field == "title" else text(
                    override[field], field, limit
                )
        words(override.get("tags", []), "tags")
        words(override.get("hashtags", []), "hashtags", True)
    return config


def load_copy(path: Path, entry: dict, credit: str) -> PublishingCopy:
    return publishing_copy(load_metadata(path), entry, credit)


def publishing_copy(config: dict, entry: dict, credit: str) -> PublishingCopy:
    overrides = config["episodes"]
    override = overrides.get(entry["id"], {})
    tags = tuple(
        dict.fromkeys(
            (*words(config["shared_tags"], "tags"), *words(override.get("tags", []), "tags"))
        )
    )
    # Conservatively include separators and quotes around multiword tags.
    if sum(len(tag) + (2 if " " in tag else 0) for tag in tags) + max(0, len(tags) - 1) > 500:
        raise ValueError("Combined YouTube tags exceed 500 characters")
    hashtags = tuple(
        dict.fromkeys(
            (
                *words(config["shared_hashtags"], "hashtags", True),
                *words(override.get("hashtags", []), "hashtags", True),
            )
        )
    )
    if len(hashtags) > 3:
        raise ValueError("Use at most three description hashtags")
    title = title_text(override.get("title", entry["title"]), "Episode title")
    summary = text(override.get("description", entry["description"]), "Episode description", 4000)
    link = site.DOMAIN + (
        "/notes/" + entry["slug"] if entry.get("slug") else "/notes/#listen-archive"
    )
    description = text(
        f"{summary}\n\nWritten edition: {link}\n\n"
        f"AI-narrated. Machine-generated captions and transcript.\n\n"
        f"{credit}\n\n{' '.join(hashtags)}",
        "YouTube description",
        5000,
    )
    if len((description + "\n").encode("utf-8")) > 5000:
        raise ValueError("YouTube description exceeds 5000 UTF-8 bytes")
    if "<" in description or ">" in description:
        raise ValueError("YouTube description must be plain text without angle brackets")
    return PublishingCopy(title, description, tags, hashtags)
