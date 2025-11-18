"""Test the playlist generator with 10 popular songs as seeds."""

from __future__ import annotations

from data import load_sample_catalog
from examples import _format_playlist
from playlist import PlaylistGenerator

# Select 10 most popular songs from the catalog as seeds
POPULAR_SEED_SONGS = [
    "screamin-jay-hawkins-i-put-a-spell-on-you",  # popularity 96
    "nina-simone-sinnerman",  # popularity 93
    "aria-north-city-lights",  # popularity 93
    "nina-simone-feeling-good",  # popularity 92
    "aria-north-luminous-veil",  # popularity 92
    "neon-rivers-glass-tides",  # popularity 91
    "muse-supermassive-black-hole",  # popularity 90
    "golden-age-ivory-seasons",  # popularity 90
    "neon-rivers-midnight-current",  # popularity 89
    "velvet-echo-midnight-script",  # popularity 89
]


def main() -> None:
    """Generate playlists from 10 popular seed songs."""

    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    print("=" * 80)
    print("TESTING SPOTIFY PLAYLIST GENERATOR WITH 10 POPULAR SEEDS")
    print("=" * 80)
    print()

    for i, seed_id in enumerate(POPULAR_SEED_SONGS, start=1):
        seed_song = catalog.song(seed_id)
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/10")
        print(f"Seed Song: {seed_song.artist} – {seed_song.title}")
        print(f"Popularity: {seed_song.popularity}")
        print(f"Song ID: {seed_id}")
        print(f"{'=' * 80}\n")

        # Generate playlist of 10 songs
        playlist = generator.generate(seed_id, length=10)

        print(f"Generated Playlist ({len(playlist)} songs):\n")
        print(_format_playlist(playlist))

        # Analyze the playlist
        if len(playlist) < 10:
            print(f"\n⚠ Note: Playlist stopped early at {len(playlist)} songs")
            print("   (no more valid covers found)")

        # Show popularity trend
        popularities = [song.popularity for song in playlist]
        print(f"\nPopularity trend: {' → '.join(str(int(p)) for p in popularities)}")

        if len(playlist) > 1:
            drop = popularities[0] - popularities[-1]
            avg_drop = drop / (len(playlist) - 1)
            print(f"Total popularity drop: {int(drop)} (avg {avg_drop:.1f} per transition)")

    print(f"\n{'=' * 80}")
    print("ALL TESTS COMPLETED")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
