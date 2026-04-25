"""Generate playlists using MusicBrainz (no API key required!)"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

try:
    import musicbrainzngs as mb

    MB_AVAILABLE = True
except ImportError:
    MB_AVAILABLE = False
    print("Error: musicbrainzngs not installed. Run: pip install musicbrainzngs")
    import sys

    sys.exit(1)

# Set user agent (required by MusicBrainz - include contact info per their guidelines)
mb.set_useragent("playlist-generator", "0.1", "https://github.com/shaobohou/research")
mb.set_rate_limit(limit_or_interval=1.0)


class MusicBrainzPlaylistGenerator:
    """Generate playlists using MusicBrainz data (no API key needed!)."""

    def __init__(self):
        """Initialize generator."""
        self.cache: Dict[str, Dict] = {}
        self.last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce 1 request per second rate limit."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self.last_request_time = time.time()

    def search_recording(self, artist: str, title: str) -> Optional[Dict]:
        """Search for a recording on MusicBrainz."""
        cache_key = f"{artist}||{title}".lower()
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            self._rate_limit()
            result = mb.search_recordings(artist=artist, recording=title, limit=10, strict=False)

            if result["recording-list"]:
                # Get the first recording with an artist credit
                for recording in result["recording-list"]:
                    if "artist-credit" in recording:
                        # Get rating/score (0-100) as popularity proxy
                        score = int(recording.get("ext:score", "0"))
                        rating = recording.get("rating", {})
                        votes = rating.get("votes-count", 0) if rating else 0

                        # Combine score and rating for popularity estimate
                        popularity = score + (votes * 2)  # Rough heuristic

                        recording_info = {
                            "id": recording["id"],
                            "title": recording["title"],
                            "artist": recording["artist-credit-phrase"],
                            "popularity": min(popularity, 100),  # Cap at 100
                            "length": recording.get("length", "Unknown"),
                            "mbid": recording["id"],
                        }

                        self.cache[cache_key] = recording_info
                        return recording_info

            return None

        except Exception as e:
            print(f"Error searching for {artist} - {title}: {e}")
            return None

    def find_covers(self, original_mbid: str, original_artist: str, original_title: str) -> List[Dict]:
        """Find cover versions of a recording using MusicBrainz relationships."""
        covers = []

        try:
            # Search for recordings that reference this one as "cover"
            self._rate_limit()
            search_result = mb.search_recordings(query=f'"{original_title}"', limit=50)

            original_info = self.search_recording(original_artist, original_title)
            if not original_info:
                return []

            original_pop = original_info["popularity"]

            for recording in search_result.get("recording-list", []):
                if "artist-credit" in recording:
                    artist_name = recording["artist-credit-phrase"]

                    # Skip if same artist
                    if artist_name.lower() == original_artist.lower():
                        continue

                    # Check if title matches (likely a cover)
                    rec_title = recording["title"]
                    if original_title.lower() not in rec_title.lower():
                        continue

                    score = int(recording.get("ext:score", "0"))
                    rating = recording.get("rating", {})
                    votes = rating.get("votes-count", 0) if rating else 0
                    popularity = score + (votes * 2)

                    # Only include if less popular than original
                    if popularity >= original_pop:
                        continue

                    # Require minimum popularity to filter noise
                    if popularity < 20:
                        continue

                    covers.append(
                        {
                            "id": recording["id"],
                            "title": rec_title,
                            "artist": artist_name,
                            "popularity": min(popularity, 100),
                            "mbid": recording["id"],
                            "cover_of": original_mbid,
                            "cover_of_artist": original_artist,
                            "cover_of_title": original_title,
                        }
                    )

            # Sort by popularity (descending) to favor more well-known covers
            covers.sort(key=lambda x: -x["popularity"])

        except Exception as e:
            print(f"Error finding covers: {e}")

        return covers

    def generate_playlist(self, seed_artist: str, seed_title: str, length: int = 10) -> List[Dict]:
        """Generate a playlist starting from a seed song."""

        # Get the seed song
        seed = self.search_recording(seed_artist, seed_title)
        if not seed:
            print(f"❌ Could not find seed song: {seed_artist} - {seed_title}")
            return []

        print(f"✓ Found seed: {seed['artist']} - {seed['title']} (pop: {seed['popularity']})")
        print(f"  🔗 https://musicbrainz.org/recording/{seed['mbid']}\n")

        playlist = [seed]
        used_artists = {seed["artist"].lower()}
        used_recording_ids = {seed["id"]}

        current_mbid = seed["mbid"]
        current_artist = seed["artist"]
        current_title = seed["title"]

        for i in range(1, length):
            print(f"Step {i}: Looking for covers of {current_artist} songs...")

            covers = self.find_covers(current_mbid, current_artist, current_title)

            # Filter out already used artists and recordings
            valid_covers = [
                c for c in covers if c["artist"].lower() not in used_artists and c["id"] not in used_recording_ids
            ]

            if not valid_covers:
                print("  ⚠ Chain ended - no more unique covers found")
                break

            # Pick the most popular valid cover
            next_song = valid_covers[0]
            playlist.append(next_song)
            used_artists.add(next_song["artist"].lower())
            used_recording_ids.add(next_song["id"])

            print(f"  ✓ Found: {next_song['artist']} - {next_song['title']} (pop: {next_song['popularity']})")
            print(f"    Cover of: {next_song['cover_of_artist']} - {next_song['cover_of_title']}")
            print(f"    🔗 https://musicbrainz.org/recording/{next_song['mbid']}\n")

            # Next iteration
            current_mbid = next_song["mbid"]
            current_artist = next_song["artist"]
            current_title = next_song["title"]

        return playlist


def print_playlist(playlist: List[Dict]) -> None:
    """Print a formatted playlist."""
    print("=" * 80)
    print(f"GENERATED PLAYLIST ({len(playlist)} songs)")
    print("=" * 80)
    print()

    for i, song in enumerate(playlist, 1):
        cover_info = ""
        if "cover_of_artist" in song:
            cover_info = f" — cover of {song['cover_of_artist']} – {song['cover_of_title']}"

        print(f"{i}. {song['artist']} – {song['title']} (popularity {song['popularity']}){cover_info}")
        print(f"   🔗 https://musicbrainz.org/recording/{song['mbid']}")
        print()

    # Statistics
    popularities = [s["popularity"] for s in playlist]
    artists = [s["artist"] for s in playlist]

    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Total songs: {len(playlist)}")
    print(f"Unique artists: {len(set(artists))}/{len(artists)}")
    print(f"Popularity range: {min(popularities)} - {max(popularities)}")
    print(f"Popularity trend: {' → '.join(str(p) for p in popularities)}")
    print(f"Average popularity: {sum(popularities) / len(popularities):.1f}")
    print()


def main():
    """Main entry point."""
    print("=" * 80)
    print("MUSICBRAINZ PLAYLIST GENERATOR (No API Key Required!)")
    print("=" * 80)
    print()
    print("Using MusicBrainz - the open music encyclopedia")
    print("Rate limit: 1 request/second (be patient!)")
    print()

    generator = MusicBrainzPlaylistGenerator()

    # Test with well-known songs that have many covers
    test_seeds = [
        ("The Beatles", "Yesterday"),
        ("Leonard Cohen", "Hallelujah"),
        ("Nina Simone", "Feeling Good"),
        ("Bob Dylan", "All Along the Watchtower"),
    ]

    for artist, title in test_seeds[:1]:  # Start with one
        print("=" * 80)
        print(f"SEED: {artist} - {title}")
        print("=" * 80)
        print()

        playlist = generator.generate_playlist(artist, title, length=5)

        if playlist:
            print_playlist(playlist)

        break


if __name__ == "__main__":
    main()
