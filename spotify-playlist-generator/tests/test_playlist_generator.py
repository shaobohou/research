from __future__ import annotations

# ruff: noqa: E402

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from spotify_playlist_generator.data import load_sample_catalog
from spotify_playlist_generator.examples import generate_random_playlist
from spotify_playlist_generator.playlist import Catalog, PlaylistGenerator, Song


def assert_transition_is_less_famous_cover(
    previous: Song, current: Song, catalog: Catalog
) -> None:
    original = catalog.song(current.cover_of) if current.cover_of else None
    assert original is not None
    assert original.artist == previous.artist
    assert current.popularity < original.popularity


def test_generator_builds_cover_chain() -> None:
    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    playlist = generator.generate("aria-north-city-lights", length=6)

    assert len(playlist) == 6
    for prev, cur in zip(playlist, playlist[1:]):
        assert_transition_is_less_famous_cover(prev, cur, catalog)


def test_generator_stops_when_no_cover_exists() -> None:
    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    # Choose a cover by an artist that has no covers of their catalog in our sample data.
    # Late Summer only covers Aria North and does not have covers of their own songs.
    playlist = generator.generate("late-summer-city-lights-cover", length=4)

    assert len(playlist) == 1


def test_invalid_length() -> None:
    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    try:
        generator.generate("aria-north-city-lights", length=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError when requesting non-positive length")


def test_random_playlist_is_seeded() -> None:
    playlist = generate_random_playlist(length=4, seed=1337)

    assert [song.id for song in playlist] == [
        "neon-rivers-luminous-veil-cover",
        "velvet-echo-glass-tides-cover",
        "hollow-pines-midnight-script-cover",
        "golden-age-stone-gardens-cover",
    ]


def test_playlist_can_start_from_explicit_seed_song() -> None:
    playlist = generate_random_playlist(
        length=5, seed_song_id="screamin-jay-hawkins-i-put-a-spell-on-you"
    )

    assert [song.id for song in playlist] == [
        "screamin-jay-hawkins-i-put-a-spell-on-you",
        "nina-simone-little-demon-cover",
        "muse-feeling-good-cover",
        "velvet-echo-supermassive-black-hole-cover",
        "hollow-pines-midnight-script-cover",
    ]


def test_playlist_never_repeats_same_composition() -> None:
    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    playlist = generator.generate("screamin-jay-hawkins-i-put-a-spell-on-you", length=6)

    composition_ids: set[str] = set()
    for song in playlist:
        assert song.composition_id not in composition_ids
        composition_ids.add(song.composition_id)
