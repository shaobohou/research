"""Tests for the real Spotify playlist generator."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from real_spotify_generator import RealSpotifyPlaylistGenerator, print_playlist

FAKE_TRACK = {
    "id": "track1",
    "name": "Feeling Good",
    "artist": "Nina Simone",
    "popularity": 80,
    "uri": "spotify:track:track1",
    "url": "https://open.spotify.com/track/track1",
    "album": "I Put A Spell On You",
    "release_date": "1965-01-01",
}

FAKE_COVER = {
    "id": "track2",
    "name": "Feeling Good",
    "artist": "Muse",
    "popularity": 73,
    "uri": "spotify:track:track2",
    "url": "https://open.spotify.com/track/track2",
    "album": "Hullabaloo Soundtrack",
    "release_date": "2002-01-01",
    "cover_of": "track1",
    "cover_of_artist": "Nina Simone",
    "cover_of_title": "Feeling Good",
}


def make_generator() -> RealSpotifyPlaylistGenerator:
    """Return a generator with a mocked Spotify client."""
    with patch("real_spotify_generator.SpotifyClientCredentials"), patch("real_spotify_generator.spotipy.Spotify"):
        return RealSpotifyPlaylistGenerator("fake_id", "fake_secret")


class TestPrintPlaylist:
    def test_single_song(self, capsys) -> None:
        print_playlist([FAKE_TRACK])
        out = capsys.readouterr().out
        assert "Nina Simone" in out
        assert "Feeling Good" in out
        assert "80" in out

    def test_cover_annotation(self, capsys) -> None:
        print_playlist([FAKE_TRACK, FAKE_COVER])
        out = capsys.readouterr().out
        assert "cover of Nina Simone" in out

    def test_statistics_block(self, capsys) -> None:
        print_playlist([FAKE_TRACK, FAKE_COVER])
        out = capsys.readouterr().out
        assert "STATISTICS" in out
        assert "Total songs: 2" in out
        assert "Unique artists: 2/2" in out


class TestSearchSong:
    def test_returns_none_on_empty_results(self) -> None:
        gen = make_generator()
        gen.spotify.search = MagicMock(return_value={"tracks": {"items": []}})
        assert gen.search_song("Unknown", "Unknown Song") is None

    def test_returns_none_when_api_returns_none(self) -> None:
        gen = make_generator()
        gen.spotify.search = MagicMock(return_value=None)
        assert gen.search_song("Unknown", "Unknown Song") is None

    def test_returns_most_popular_track(self) -> None:
        gen = make_generator()
        gen.spotify.search = MagicMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "id": "a",
                            "name": "Feeling Good",
                            "artists": [{"name": "Nina Simone"}],
                            "popularity": 80,
                            "uri": "spotify:track:a",
                            "external_urls": {"spotify": "https://open.spotify.com/track/a"},
                            "album": {"name": "Album A", "release_date": "1965"},
                        },
                        {
                            "id": "b",
                            "name": "Feeling Good (Live)",
                            "artists": [{"name": "Nina Simone"}],
                            "popularity": 40,
                            "uri": "spotify:track:b",
                            "external_urls": {"spotify": "https://open.spotify.com/track/b"},
                            "album": {"name": "Album B", "release_date": "1970"},
                        },
                    ]
                }
            }
        )
        result = gen.search_song("Nina Simone", "Feeling Good")
        assert result is not None
        assert result["id"] == "a"
        assert result["popularity"] == 80

    def test_caches_results(self) -> None:
        gen = make_generator()
        gen.spotify.search = MagicMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "id": "a",
                            "name": "Song",
                            "artists": [{"name": "Artist"}],
                            "popularity": 70,
                            "uri": "spotify:track:a",
                            "external_urls": {"spotify": "https://open.spotify.com/track/a"},
                            "album": {"name": "Album", "release_date": "2000"},
                        }
                    ]
                }
            }
        )
        gen.search_song("Artist", "Song")
        gen.search_song("Artist", "Song")
        assert gen.spotify.search.call_count == 1


class TestFindCovers:
    def test_excludes_original_artist(self) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value={"id": "orig", "popularity": 80})  # type: ignore[method-assign]
        gen.spotify.search = MagicMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "id": "x",
                            "name": "Feeling Good",
                            "artists": [{"name": "Nina Simone"}],
                            "popularity": 60,
                            "uri": "spotify:track:x",
                            "external_urls": {"spotify": "https://open.spotify.com/track/x"},
                        }
                    ]
                }
            }
        )
        covers = gen.find_covers("Nina Simone", "Feeling Good")
        assert all(c["artist"] != "Nina Simone" for c in covers)

    def test_excludes_more_popular_than_original(self) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value={"id": "orig", "popularity": 50})  # type: ignore[method-assign]
        gen.spotify.search = MagicMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "id": "x",
                            "name": "Feeling Good",
                            "artists": [{"name": "Muse"}],
                            "popularity": 75,  # more popular than original (50)
                            "uri": "spotify:track:x",
                            "external_urls": {"spotify": "https://open.spotify.com/track/x"},
                        }
                    ]
                }
            }
        )
        covers = gen.find_covers("Nina Simone", "Feeling Good")
        assert covers == []

    def test_returns_empty_on_none_api_result(self) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value={"id": "orig", "popularity": 80})  # type: ignore[method-assign]
        gen.spotify.search = MagicMock(return_value=None)
        assert gen.find_covers("Nina Simone", "Feeling Good") == []


class TestGeneratePlaylist:
    def test_returns_empty_when_seed_not_found(self, capsys) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value=None)  # type: ignore[method-assign]
        result = gen.generate_playlist("Unknown Artist", "Unknown Song")
        assert result == []

    def test_single_song_when_no_covers(self) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value=FAKE_TRACK)  # type: ignore[method-assign]
        gen.find_covers = MagicMock(return_value=[])  # type: ignore[method-assign]
        gen.spotify.search = MagicMock(return_value={"artists": {"items": []}})
        result = gen.generate_playlist("Nina Simone", "Feeling Good", length=5)
        assert len(result) == 1
        assert result[0]["artist"] == "Nina Simone"

    def test_chains_cover_to_next(self) -> None:
        gen = make_generator()

        # seed search returns FAKE_TRACK, all other searches return nothing
        gen.search_song = MagicMock(return_value=FAKE_TRACK)  # type: ignore[method-assign]
        gen.find_covers = MagicMock(
            side_effect=[  # type: ignore[method-assign]
                [FAKE_COVER],  # first call: returns a cover
                [],  # second call: no more covers → chain ends
            ]
        )
        gen.spotify.search = MagicMock(return_value={"artists": {"items": []}})

        result = gen.generate_playlist("Nina Simone", "Feeling Good", length=5)
        assert len(result) == 2
        assert result[0]["artist"] == "Nina Simone"
        assert result[1]["artist"] == "Muse"

    def test_no_artist_repetition(self) -> None:
        gen = make_generator()
        gen.search_song = MagicMock(return_value=FAKE_TRACK)  # type: ignore[method-assign]
        duplicate_artist_cover = {**FAKE_COVER, "artist": "Nina Simone"}  # same artist as seed
        gen.find_covers = MagicMock(return_value=[duplicate_artist_cover])  # type: ignore[method-assign]
        gen.spotify.search = MagicMock(return_value={"artists": {"items": []}})

        result = gen.generate_playlist("Nina Simone", "Feeling Good", length=5)
        artists = [s["artist"] for s in result]
        assert len(artists) == len(set(artists))
