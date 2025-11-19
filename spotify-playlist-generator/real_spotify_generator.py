"""Generate playlists using only real songs from Spotify API."""

from __future__ import annotations

import os
import sys
from typing import Dict, List, Optional, Set

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False
    print("Error: spotipy not installed. Run: pip install spotipy")
    sys.exit(1)


class RealSpotifyPlaylistGenerator:
    """Generate playlists using real songs from Spotify."""

    def __init__(self, client_id: str, client_secret: str):
        """Initialize with Spotify credentials."""
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.spotify = spotipy.Spotify(auth_manager=auth_manager)
        self.cache: Dict[str, Dict] = {}

    def search_song(self, artist: str, title: str) -> Optional[Dict]:
        """Search for a song on Spotify and return track info."""
        cache_key = f"{artist}||{title}".lower()
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            # Clean up title (remove parentheticals that might be covers)
            clean_title = title.split("(")[0].strip()
            query = f'artist:"{artist}" track:"{clean_title}"'
            results = self.spotify.search(q=query, type="track", limit=5)

            if results["tracks"]["items"]:
                # Get the most popular match
                tracks = results["tracks"]["items"]
                best_match = max(tracks, key=lambda t: t["popularity"])

                track_info = {
                    "id": best_match["id"],
                    "name": best_match["name"],
                    "artist": best_match["artists"][0]["name"],
                    "popularity": best_match["popularity"],
                    "uri": best_match["uri"],
                    "url": best_match["external_urls"]["spotify"],
                    "album": best_match["album"]["name"],
                    "release_date": best_match["album"]["release_date"],
                }

                self.cache[cache_key] = track_info
                return track_info
            return None
        except Exception as e:
            print(f"Error searching for {artist} - {title}: {e}")
            return None

    def find_covers(self, original_artist: str, song_title: str) -> List[Dict]:
        """Find cover versions of a song on Spotify."""
        covers = []

        try:
            # Search for covers
            clean_title = song_title.split("(")[0].strip()
            query = f'track:"{clean_title}" NOT artist:"{original_artist}"'
            results = self.spotify.search(q=query, type="track", limit=20)

            original_info = self.search_song(original_artist, song_title)
            if not original_info:
                return []

            original_pop = original_info["popularity"]

            for track in results["tracks"]["items"]:
                artist_name = track["artists"][0]["name"]
                track_name = track["name"]
                popularity = track["popularity"]

                # Only include if:
                # 1. Different artist
                # 2. Similar title (cover)
                # 3. Less popular than original
                if (artist_name.lower() != original_artist.lower() and
                    clean_title.lower() in track_name.lower() and
                    popularity < original_pop and
                    popularity > 40):  # Minimum popularity threshold

                    covers.append({
                        "id": track["id"],
                        "name": track_name,
                        "artist": artist_name,
                        "popularity": popularity,
                        "uri": track["uri"],
                        "url": track["external_urls"]["spotify"],
                        "cover_of": original_info["id"],
                        "cover_of_artist": original_artist,
                        "cover_of_title": song_title,
                    })

            # Sort by popularity (descending)
            covers.sort(key=lambda x: -x["popularity"])

        except Exception as e:
            print(f"Error finding covers: {e}")

        return covers

    def generate_playlist(self, seed_artist: str, seed_title: str, length: int = 10) -> List[Dict]:
        """Generate a playlist starting from a seed song."""

        # Get the seed song
        seed = self.search_song(seed_artist, seed_title)
        if not seed:
            print(f"❌ Could not find seed song: {seed_artist} - {seed_title}")
            return []

        print(f"✓ Found seed: {seed['artist']} - {seed['name']} (pop: {seed['popularity']})")
        print(f"  🔗 {seed['url']}\n")

        playlist = [seed]
        used_artists: Set[str] = {seed['artist'].lower()}
        used_song_ids: Set[str] = {seed['id']}

        current_artist = seed['artist']
        current_title = seed['name']

        for i in range(1, length):
            print(f"Step {i}: Looking for covers of {current_artist} songs...")

            # Find covers of the current artist's songs
            # Try the current song first, then other popular songs by the artist
            covers = self.find_covers(current_artist, current_title)

            # Filter out already used artists and songs
            valid_covers = [
                c for c in covers
                if c['artist'].lower() not in used_artists
                and c['id'] not in used_song_ids
            ]

            if not valid_covers:
                # Try finding covers of other songs by this artist
                print(f"  No new covers found for '{current_title}'")
                print(f"  Searching for artist's other popular songs...")

                # Search for artist's top tracks
                try:
                    artist_search = self.spotify.search(q=f'artist:"{current_artist}"', type="artist", limit=1)
                    if artist_search["artists"]["items"]:
                        artist_id = artist_search["artists"]["items"][0]["id"]
                        top_tracks = self.spotify.artist_top_tracks(artist_id)

                        # Try to find covers of other popular songs
                        for track in top_tracks["tracks"][:5]:
                            if track["name"] != current_title:
                                other_covers = self.find_covers(current_artist, track["name"])
                                valid_other = [
                                    c for c in other_covers
                                    if c['artist'].lower() not in used_artists
                                    and c['id'] not in used_song_ids
                                ]
                                if valid_other:
                                    valid_covers = valid_other
                                    break
                except Exception as e:
                    print(f"  Error searching top tracks: {e}")

            if not valid_covers:
                print(f"  ⚠ Chain ended - no more unique covers found")
                break

            # Pick the most popular valid cover
            next_song = valid_covers[0]
            playlist.append(next_song)
            used_artists.add(next_song['artist'].lower())
            used_song_ids.add(next_song['id'])

            print(f"  ✓ Found: {next_song['artist']} - {next_song['name']} (pop: {next_song['popularity']})")
            print(f"    Cover of: {next_song['cover_of_artist']} - {next_song['cover_of_title']}")
            print(f"    🔗 {next_song['url']}\n")

            # Next iteration: look for covers by artists who cover this new artist
            current_artist = next_song['artist']
            current_title = next_song['name']

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

        print(f"{i}. {song['artist']} – {song['name']} (popularity {song['popularity']}){cover_info}")
        print(f"   🔗 {song['url']}")
        if "album" in song:
            print(f"   💿 {song['album']} ({song.get('release_date', 'N/A')})")
        print()

    # Statistics
    popularities = [s['popularity'] for s in playlist]
    artists = [s['artist'] for s in playlist]

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
    print("REAL SPOTIFY PLAYLIST GENERATOR")
    print("=" * 80)
    print()

    # Get credentials from environment
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ Spotify API credentials required!")
        print()
        print("Set these environment variables:")
        print("  export SPOTIFY_CLIENT_ID='your_client_id'")
        print("  export SPOTIFY_CLIENT_SECRET='your_client_secret'")
        print()
        print("Get credentials at: https://developer.spotify.com/dashboard")
        print("  1. Create an app")
        print("  2. Copy Client ID and Client Secret")
        print()
        sys.exit(1)

    print("✓ Spotify credentials found")
    print()

    generator = RealSpotifyPlaylistGenerator(client_id, client_secret)

    # Test with well-known songs that have many covers
    test_seeds = [
        ("The Beatles", "Yesterday"),
        ("Leonard Cohen", "Hallelujah"),
        ("Johnny Cash", "Hurt"),
        ("Nina Simone", "Feeling Good"),
        ("Jeff Buckley", "Hallelujah"),
    ]

    for artist, title in test_seeds[:1]:  # Start with one seed
        print("=" * 80)
        print(f"SEED: {artist} - {title}")
        print("=" * 80)
        print()

        playlist = generator.generate_playlist(artist, title, length=10)

        if playlist:
            print_playlist(playlist)

            # Option to create actual Spotify playlist
            print("=" * 80)
            print("💡 To create this as an actual Spotify playlist, use:")
            print("   spotify.user_playlist_create() with user authentication")
            print("=" * 80)
            print()

        break  # Remove this to test all seeds


if __name__ == "__main__":
    main()
