"""Analyze the catalog to find optimal seed songs for long playlist chains."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from data import load_sample_catalog
from playlist import Catalog, PlaylistGenerator, Song


def analyze_cover_network(catalog: Catalog) -> Dict[str, int]:
    """Count how many covers exist for each artist."""

    artist_cover_count: Dict[str, int] = defaultdict(int)

    for song in catalog.songs():
        if song.is_cover and song.cover_of:
            original = catalog.song(song.cover_of)
            artist_cover_count[original.artist] += 1

    return dict(artist_cover_count)


def analyze_artist_connections(catalog: Catalog) -> Dict[str, Set[str]]:
    """Map each artist to the set of artists who cover their songs."""

    artist_to_cover_artists: Dict[str, Set[str]] = defaultdict(set)

    for song in catalog.songs():
        if song.is_cover and song.cover_of:
            original = catalog.song(song.cover_of)
            artist_to_cover_artists[original.artist].add(song.artist)

    return {k: v for k, v in artist_to_cover_artists.items()}


def find_best_seeds(catalog: Catalog, generator: PlaylistGenerator) -> List[tuple[str, Song, int]]:
    """Find songs that generate the longest playlists."""

    results = []

    for song in catalog.songs():
        playlist = generator.generate(song.id, length=20)
        results.append((song.id, song, len(playlist)))

    # Sort by playlist length descending, then by popularity descending
    results.sort(key=lambda x: (-x[2], -x[1].popularity))

    return results


def main() -> None:
    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    print("=" * 80)
    print("CATALOG ANALYSIS: Finding Optimal Seed Songs")
    print("=" * 80)
    print()

    # Analyze cover network
    print("1. COVER COUNTS BY ARTIST")
    print("-" * 80)
    cover_counts = analyze_cover_network(catalog)
    for artist, count in sorted(cover_counts.items(), key=lambda x: -x[1]):
        print(f"   {artist}: {count} covers")
    print()

    # Analyze connections
    print("2. ARTIST CONNECTIONS (who covers whom)")
    print("-" * 80)
    connections = analyze_artist_connections(catalog)
    for artist, cover_artists in sorted(connections.items()):
        print(f"   {artist} → covered by: {', '.join(sorted(cover_artists))}")
    print()

    # Find best seeds
    print("3. TESTING ALL SONGS AS SEEDS")
    print("-" * 80)
    print("   Generating playlists from all songs to find longest chains...")
    print()

    best_seeds = find_best_seeds(catalog, generator)

    # Show top 15 seeds
    print("4. TOP 15 SEEDS BY PLAYLIST LENGTH")
    print("=" * 80)
    for i, (song_id, song, length) in enumerate(best_seeds[:15], 1):
        cover_marker = " [COVER]" if song.is_cover else ""
        print(f"{i:2d}. Length {length:2d} | Pop {song.popularity:2.0f} | "
              f"{song.artist} – {song.title}{cover_marker}")
        print(f"     ID: {song_id}")
    print()

    # Analyze by length groups
    print("5. DISTRIBUTION SUMMARY")
    print("-" * 80)
    length_groups = defaultdict(int)
    for _, _, length in best_seeds:
        length_groups[length] += 1

    for length in sorted(length_groups.keys(), reverse=True):
        count = length_groups[length]
        bar = "█" * count
        print(f"   Length {length:2d}: {count:2d} songs {bar}")
    print()

    # Select diverse top seeds
    print("6. RECOMMENDED SEEDS (diverse, high-performing)")
    print("=" * 80)
    recommended = []
    seen_artists = set()

    for song_id, song, length in best_seeds:
        if len(recommended) >= 10:
            break
        if song.artist not in seen_artists and not song.is_cover:
            recommended.append((song_id, song, length))
            seen_artists.add(song.artist)

    print("\nTop 10 non-cover seeds from different artists:\n")
    for i, (song_id, song, length) in enumerate(recommended, 1):
        print(f"{i:2d}. {song.artist} – {song.title}")
        print(f"     Popularity: {song.popularity}, Expected length: {length}")
        print(f"     ID: {song_id}")
        print()


if __name__ == "__main__":
    main()
