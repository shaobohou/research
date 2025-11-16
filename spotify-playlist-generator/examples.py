"""Helpers for showcasing playlists generated from random seeds."""

from __future__ import annotations

import argparse
from random import Random
from typing import Sequence

from data import load_sample_catalog
from playlist import PlaylistGenerator, Song


def generate_random_playlist(
    *,
    length: int = 5,
    seed: int | None = None,
    seed_song_id: str | None = None,
) -> list[Song]:
    """Generate a playlist that starts from a random or explicit seed song."""

    catalog = load_sample_catalog()
    songs = list(catalog.songs())
    if not songs:
        return []

    if seed_song_id:
        try:
            seed_song = catalog.song(seed_song_id)
        except KeyError as exc:
            raise ValueError(f"Unknown seed song id: {seed_song_id}") from exc
    else:
        rng = Random(seed)
        seed_song = rng.choice(songs)

    generator = PlaylistGenerator(catalog)
    return generator.generate(seed_song_id=seed_song.id, length=length)


def _format_playlist(playlist: Sequence[Song]) -> str:
    catalog = load_sample_catalog()
    lines = []
    for index, song in enumerate(playlist, start=1):
        base = f"{index}. {song.artist} – {song.title} (popularity {song.popularity})"
        if song.cover_of:
            try:
                original = catalog.song(song.cover_of)
            except KeyError:
                original = None
            if original:
                base += f" — cover of {original.artist} – {original.title}"
        lines.append(base)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--length", type=int, default=5, help="Desired playlist length")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible demonstrations",
    )
    parser.add_argument(
        "--seed-song",
        type=str,
        default=None,
        help="Explicit song id to start from; overrides --seed when provided",
    )
    args = parser.parse_args()
    playlist = generate_random_playlist(
        length=args.length,
        seed=args.seed,
        seed_song_id=args.seed_song,
    )
    print(_format_playlist(playlist))


if __name__ == "__main__":
    main()
