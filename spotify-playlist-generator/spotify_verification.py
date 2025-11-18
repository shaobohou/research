"""Verify playlist generation using real Spotify API data."""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional

from data import load_sample_catalog
from examples import _format_playlist
from playlist import PlaylistGenerator, Song

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False


class SpotifyVerifier:
    """Verify playlist generation against real Spotify data."""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.spotify = None
        self.api_available = False

        if SPOTIPY_AVAILABLE and client_id and client_secret:
            try:
                auth_manager = SpotifyClientCredentials(
                    client_id=client_id,
                    client_secret=client_secret
                )
                self.spotify = spotipy.Spotify(auth_manager=auth_manager)
                self.api_available = True
                print("✓ Spotify API connected successfully")
            except Exception as e:
                print(f"⚠ Could not connect to Spotify API: {e}")
                print("  Running in demo mode (no API verification)")
        else:
            if not SPOTIPY_AVAILABLE:
                print("⚠ spotipy not installed")
            else:
                print("⚠ Spotify credentials not provided")
            print("  Running in demo mode (no API verification)")

    def search_song(self, artist: str, title: str) -> Optional[Dict]:
        """Search for a song on Spotify."""
        if not self.api_available:
            return None

        try:
            # Clean up the title to remove cover annotations
            clean_title = title.split("(")[0].strip()
            query = f"artist:{artist} track:{clean_title}"
            results = self.spotify.search(q=query, type="track", limit=5)

            if results["tracks"]["items"]:
                # Return the most popular match
                tracks = results["tracks"]["items"]
                best_match = max(tracks, key=lambda t: t["popularity"])
                return {
                    "id": best_match["id"],
                    "name": best_match["name"],
                    "artist": best_match["artists"][0]["name"],
                    "popularity": best_match["popularity"],
                    "uri": best_match["uri"],
                    "url": best_match["external_urls"]["spotify"],
                }
            return None
        except Exception as e:
            print(f"  Error searching for {artist} - {title}: {e}")
            return None

    def verify_song(self, song: Song) -> Dict:
        """Verify a song against Spotify data."""
        result = {
            "song": song,
            "found": False,
            "spotify_data": None,
            "popularity_match": False,
            "popularity_diff": None,
        }

        if not self.api_available:
            result["error"] = "API not available"
            return result

        spotify_data = self.search_song(song.artist, song.title)

        if spotify_data:
            result["found"] = True
            result["spotify_data"] = spotify_data
            result["popularity_diff"] = abs(song.popularity - spotify_data["popularity"])
            result["popularity_match"] = result["popularity_diff"] < 10  # Within 10 points
        else:
            result["error"] = "Song not found on Spotify"

        return result


def test_diverse_seeds(verifier: SpotifyVerifier) -> None:
    """Test playlist generation with diverse seed songs."""

    catalog = load_sample_catalog()
    generator = PlaylistGenerator(catalog)

    # Select diverse seeds across different artists and popularity ranges
    diverse_seeds = [
        # Real artists (high popularity)
        "screamin-jay-hawkins-i-put-a-spell-on-you",  # 96
        "nina-simone-feeling-good",  # 92
        "muse-supermassive-black-hole",  # 90

        # Fictional artists (high popularity)
        "aria-north-city-lights",  # 93
        "neon-rivers-glass-tides",  # 91
        "golden-age-ivory-seasons",  # 90

        # Mid-popularity songs
        "velvet-echo-midnight-script",  # 89
        "hollow-pines-stone-gardens",  # 87

        # Cover songs
        "nina-simone-i-put-a-spell-on-you-cover",  # 85
        "muse-feeling-good-cover",  # 75
    ]

    print("=" * 80)
    print("TESTING DIVERSE SEED SONGS WITH SPOTIFY VERIFICATION")
    print("=" * 80)
    print()

    results = []

    for i, seed_id in enumerate(diverse_seeds, start=1):
        seed_song = catalog.song(seed_id)
        print(f"\n{'=' * 80}")
        print(f"TEST {i}/{len(diverse_seeds)}")
        print(f"Seed: {seed_song.artist} – {seed_song.title}")
        print(f"Catalog Popularity: {seed_song.popularity}")
        print(f"{'=' * 80}\n")

        # Generate playlist
        playlist = generator.generate(seed_id, length=10)

        print(f"Generated Playlist ({len(playlist)} songs):\n")
        print(_format_playlist(playlist))

        # Verify against Spotify if available
        if verifier.api_available:
            print(f"\n{'─' * 80}")
            print("SPOTIFY VERIFICATION")
            print(f"{'─' * 80}\n")

            playlist_verified = []
            for j, song in enumerate(playlist, start=1):
                verification = verifier.verify_song(song)
                playlist_verified.append(verification)

                status = "✓" if verification["found"] else "✗"
                print(f"{j}. {status} {song.artist} – {song.title}")

                if verification["found"]:
                    spotify_data = verification["spotify_data"]
                    print(f"   Catalog pop: {song.popularity}, "
                          f"Spotify pop: {spotify_data['popularity']} "
                          f"(diff: {verification['popularity_diff']})")
                    if verification["popularity_diff"] > 20:
                        print(f"   ⚠ Large popularity difference!")
                else:
                    print(f"   ⚠ Not found on Spotify (likely fictional)")

        # Statistics
        popularities = [song.popularity for song in playlist]
        artists = [song.artist for song in playlist]
        unique_artists = set(artists)

        print(f"\n{'─' * 80}")
        print("STATISTICS")
        print(f"{'─' * 80}")
        print(f"Length: {len(playlist)} songs")
        print(f"Unique artists: {len(unique_artists)}/{len(playlist)} (no repetition: {len(unique_artists) == len(playlist)})")
        print(f"Popularity range: {min(popularities):.0f} - {max(popularities):.0f}")
        print(f"Popularity trend: {' → '.join(str(int(p)) for p in popularities)}")

        results.append({
            "seed_id": seed_id,
            "seed_song": seed_song,
            "playlist": playlist,
            "length": len(playlist),
            "unique_artists": len(unique_artists),
        })

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")

    total_songs = sum(r["length"] for r in results)
    avg_length = total_songs / len(results)
    all_unique = all(r["unique_artists"] == r["length"] for r in results)

    print(f"Total tests: {len(results)}")
    print(f"Total songs generated: {total_songs}")
    print(f"Average playlist length: {avg_length:.1f}")
    print(f"All playlists have unique artists: {all_unique}")

    # Distribution
    print(f"\nLength distribution:")
    from collections import Counter
    length_counts = Counter(r["length"] for r in results)
    for length in sorted(length_counts.keys(), reverse=True):
        count = length_counts[length]
        bar = "█" * count
        print(f"  {length:2d} songs: {count:2d} tests {bar}")


def main() -> None:
    """Main entry point."""

    print("=" * 80)
    print("SPOTIFY PLAYLIST GENERATOR VERIFICATION")
    print("=" * 80)
    print()

    # Try to get credentials from environment
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Spotify API credentials not found in environment.")
        print("\nTo enable Spotify verification, set these environment variables:")
        print("  export SPOTIFY_CLIENT_ID='your_client_id'")
        print("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
        print("\nGet credentials at: https://developer.spotify.com/dashboard")
        print("\nProceeding with demo mode (no API verification)...\n")

    verifier = SpotifyVerifier(client_id, client_secret)
    test_diverse_seeds(verifier)


if __name__ == "__main__":
    main()
