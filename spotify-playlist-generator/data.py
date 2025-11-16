"""Curated dataset for demonstrating the playlist generator."""

from __future__ import annotations

from playlist import Catalog, Song


SAMPLE_SONGS = [
    # Original songs that qualify as "well known".
    Song(
        id="screamin-jay-hawkins-i-put-a-spell-on-you",
        title="I Put a Spell on You",
        artist="Screamin' Jay Hawkins",
        popularity=96,
    ),
    Song(
        id="screamin-jay-hawkins-little-demon",
        title="Little Demon",
        artist="Screamin' Jay Hawkins",
        popularity=88,
    ),
    Song(
        id="nina-simone-feeling-good",
        title="Feeling Good",
        artist="Nina Simone",
        popularity=92,
    ),
    Song(
        id="nina-simone-sinnerman",
        title="Sinnerman",
        artist="Nina Simone",
        popularity=93,
    ),
    Song(
        id="muse-supermassive-black-hole",
        title="Supermassive Black Hole",
        artist="Muse",
        popularity=90,
    ),
    Song(
        id="muse-starlight",
        title="Starlight",
        artist="Muse",
        popularity=88,
    ),
    Song(
        id="aria-north-city-lights",
        title="City Lights",
        artist="Aria North",
        popularity=93,
    ),
    Song(
        id="aria-north-luminous-veil",
        title="Luminous Veil",
        artist="Aria North",
        popularity=92,
    ),
    Song(
        id="neon-rivers-glass-tides",
        title="Glass Tides",
        artist="Neon Rivers",
        popularity=91,
    ),
    Song(
        id="neon-rivers-midnight-current",
        title="Midnight Current",
        artist="Neon Rivers",
        popularity=89,
    ),
    Song(
        id="velvet-echo-midnight-script",
        title="Midnight Script",
        artist="Velvet Echo",
        popularity=89,
    ),
    Song(
        id="velvet-echo-celestial-letters",
        title="Celestial Letters",
        artist="Velvet Echo",
        popularity=86,
    ),
    Song(
        id="hollow-pines-stone-gardens",
        title="Stone Gardens",
        artist="Hollow Pines",
        popularity=87,
    ),
    Song(
        id="hollow-pines-hidden-hollows",
        title="Hidden Hollows",
        artist="Hollow Pines",
        popularity=85,
    ),
    Song(
        id="golden-age-ivory-seasons",
        title="Ivory Seasons",
        artist="Golden Age",
        popularity=90,
    ),
    Song(
        id="golden-age-solstice-hymn",
        title="Solstice Hymn",
        artist="Golden Age",
        popularity=88,
    ),
    # Covers that form a loop between the featured artists.
    Song(
        id="nina-simone-i-put-a-spell-on-you-cover",
        title="I Put a Spell on You (Nina Simone cover)",
        artist="Nina Simone",
        popularity=85,
        cover_of="screamin-jay-hawkins-i-put-a-spell-on-you",
    ),
    Song(
        id="nina-simone-little-demon-cover",
        title="Little Demon (Nina Simone cover)",
        artist="Nina Simone",
        popularity=80,
        cover_of="screamin-jay-hawkins-little-demon",
    ),
    Song(
        id="muse-feeling-good-cover",
        title="Feeling Good (Muse cover)",
        artist="Muse",
        popularity=75,
        cover_of="nina-simone-feeling-good",
    ),
    Song(
        id="muse-sinnerman-cover",
        title="Sinnerman (Muse cover)",
        artist="Muse",
        popularity=78,
        cover_of="nina-simone-sinnerman",
    ),
    Song(
        id="velvet-echo-supermassive-black-hole-cover",
        title="Supermassive Black Hole (Velvet Echo cover)",
        artist="Velvet Echo",
        popularity=68,
        cover_of="muse-supermassive-black-hole",
    ),
    Song(
        id="velvet-echo-starlight-cover",
        title="Starlight (Velvet Echo cover)",
        artist="Velvet Echo",
        popularity=70,
        cover_of="muse-starlight",
    ),
    Song(
        id="neon-rivers-city-lights-cover",
        title="City Lights (Neon Rivers cover)",
        artist="Neon Rivers",
        popularity=60,
        cover_of="aria-north-city-lights",
    ),
    Song(
        id="neon-rivers-luminous-veil-cover",
        title="Luminous Veil (Neon Rivers cover)",
        artist="Neon Rivers",
        popularity=65,
        cover_of="aria-north-luminous-veil",
    ),
    Song(
        id="velvet-echo-glass-tides-cover",
        title="Glass Tides (Velvet Echo cover)",
        artist="Velvet Echo",
        popularity=58,
        cover_of="neon-rivers-glass-tides",
    ),
    Song(
        id="velvet-echo-midnight-current-cover",
        title="Midnight Current (Velvet Echo cover)",
        artist="Velvet Echo",
        popularity=62,
        cover_of="neon-rivers-midnight-current",
    ),
    Song(
        id="hollow-pines-midnight-script-cover",
        title="Midnight Script (Hollow Pines cover)",
        artist="Hollow Pines",
        popularity=55,
        cover_of="velvet-echo-midnight-script",
    ),
    Song(
        id="hollow-pines-celestial-letters-cover",
        title="Celestial Letters (Hollow Pines cover)",
        artist="Hollow Pines",
        popularity=56,
        cover_of="velvet-echo-celestial-letters",
    ),
    Song(
        id="golden-age-stone-gardens-cover",
        title="Stone Gardens (Golden Age cover)",
        artist="Golden Age",
        popularity=57,
        cover_of="hollow-pines-stone-gardens",
    ),
    Song(
        id="golden-age-hidden-hollows-cover",
        title="Hidden Hollows (Golden Age cover)",
        artist="Golden Age",
        popularity=58,
        cover_of="hollow-pines-hidden-hollows",
    ),
    Song(
        id="aria-north-ivory-seasons-cover",
        title="Ivory Seasons (Aria North cover)",
        artist="Aria North",
        popularity=59,
        cover_of="golden-age-ivory-seasons",
    ),
    Song(
        id="aria-north-solstice-hymn-cover",
        title="Solstice Hymn (Aria North cover)",
        artist="Aria North",
        popularity=60,
        cover_of="golden-age-solstice-hymn",
    ),
    # Additional alternative covers to create branching choices.
    Song(
        id="late-summer-city-lights-cover",
        title="City Lights (Late Summer live session)",
        artist="Late Summer",
        popularity=70,
        cover_of="aria-north-city-lights",
    ),
    Song(
        id="aria-north-glass-tides-cover",
        title="Glass Tides (Aria North acoustic)",
        artist="Aria North",
        popularity=70,
        cover_of="neon-rivers-glass-tides",
    ),
]


def load_sample_catalog() -> Catalog:
    """Return a catalog populated with ``SAMPLE_SONGS``."""

    return Catalog(SAMPLE_SONGS)
