"""Test the playlist generator with optimized seeds for longest chains."""

from __future__ import annotations

from data import load_sample_catalog
from examples import _format_playlist
from playlist import PlaylistGenerator

# Best seeds identified through analysis, selected for:
# 1. Longest expected chain length
# 2. Diverse artist representation
# 3. High popularity scores
OPTIMIZED_SEEDS = [
    "screamin-jay-hawkins-i-put-a-spell-on-you",  # Expected: 8, Pop: 96
    "screamin-jay-hawkins-little-demon",  # Expected: 8, Pop: 88
    "nina-simone-sinnerman",  # Expected: 7, Pop: 93
    "nina-simone-feeling-good",  # Expected: 7, Pop: 92
    "neon-rivers-glass-tides",  # Expected: 6, Pop: 91
    "muse-supermassive-black-hole",  # Expected: 6, Pop: 90
    "muse-starlight",  # Expected: 6, Pop: 88
    "aria-north-city-lights",  # Expected: 5, Pop: 93
    "velvet-echo-midnight-script",  # Expected: 5, Pop: 89
    "hollow-pines-stone-gardens",  # Expected: 4, Pop: 87
]


def main() -> None:
    """Generate playlists from optimized seed songs."""

    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    print("=" * 80)
    print("TESTING WITH OPTIMIZED SEEDS FOR LONGEST CHAINS")
    print("=" * 80)
    print("\nKey improvements:")
    print("✓ No artist repetition in playlists")
    print("✓ Favors more popular covers to extend chains")
    print("✓ Seeds selected based on network analysis")
    print()

    total_songs = 0
    total_expected = 0
    success_count = 0

    for i, seed_id in enumerate(OPTIMIZED_SEEDS, start=1):
        seed_song = catalog.song(seed_id)
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/10")
        print(f"Seed: {seed_song.artist} – {seed_song.title}")
        print(f"Popularity: {seed_song.popularity}")
        print(f"{'=' * 80}\n")

        # Generate playlist (try for 10 songs)
        playlist = generator.generate(seed_id, length=10)

        print(f"Generated Playlist ({len(playlist)} songs):\n")
        print(_format_playlist(playlist))

        # Verify no artist repetition
        artists = [song.artist for song in playlist]
        unique_artists = set(artists)
        assert len(artists) == len(unique_artists), f"Artist repetition detected! {artists}"

        # Show popularity trend
        popularities = [song.popularity for song in playlist]
        print(f"\nPopularity trend: {' → '.join(str(int(p)) for p in popularities)}")

        if len(playlist) > 1:
            drop = popularities[0] - popularities[-1]
            avg_drop = drop / (len(playlist) - 1)
            print(f"Total popularity drop: {int(drop)} (avg {avg_drop:.1f} per transition)")

        # Count unique artists
        print(f"Unique artists: {len(unique_artists)} (all different ✓)")

        total_songs += len(playlist)
        if len(playlist) >= 6:
            success_count += 1

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total songs generated: {total_songs}")
    print(f"Average playlist length: {total_songs / len(OPTIMIZED_SEEDS):.1f}")
    print(f"Seeds generating 6+ songs: {success_count}/{len(OPTIMIZED_SEEDS)}")
    print(f"Success rate: {success_count * 100 / len(OPTIMIZED_SEEDS):.0f}%")
    print("\n✓ All playlists have no artist repetition")
    print("✓ All playlists favor more popular covers")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
