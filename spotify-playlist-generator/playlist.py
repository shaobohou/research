"""Core playlist generation logic for the cover-focused experiment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class Song:
    """Represents a track in the catalog.

    Attributes:
        id: Unique identifier for the song.
        title: Display title.
        artist: Performing artist.
        popularity: Simplified popularity metric (0-100).
        cover_of: Optional song id that this track covers.
    """

    id: str
    title: str
    artist: str
    popularity: float
    cover_of: str | None = None

    @property
    def is_cover(self) -> bool:
        """Return True when the song is a cover."""

        return self.cover_of is not None

    @property
    def composition_id(self) -> str:
        """Return the canonical identifier for the musical work itself."""

        return self.cover_of or self.id


class Catalog:
    """In-memory collection of songs and helper lookups."""

    def __init__(self, songs: Iterable[Song]):
        self._songs: Dict[str, Song] = {song.id: song for song in songs}
        self._covers_by_original_artist: Dict[str, List[Song]] = {}
        for song in self._songs.values():
            if not song.is_cover or song.cover_of is None:
                continue
            original = self._songs.get(song.cover_of)
            if not original:
                continue
            self._covers_by_original_artist.setdefault(original.artist, []).append(song)

    def song(self, song_id: str) -> Song:
        """Return a song by id, raising KeyError when it is missing."""

        return self._songs[song_id]

    def covers_for_artist(self, artist: str) -> Sequence[Song]:
        """Return every cover recorded for songs written by ``artist``."""

        return tuple(self._covers_by_original_artist.get(artist, ()))

    def songs(self) -> Sequence[Song]:
        """Return all songs stored in the catalog."""

        return tuple(self._songs.values())


class PlaylistGenerator:
    """Generates playlists where each step follows a cover-of-current-artist rule."""

    def __init__(
        self,
        catalog: Catalog,
        *,
        well_known_threshold: float = 80.0,
    ) -> None:
        self.catalog = catalog
        self.well_known_threshold = well_known_threshold

    def generate(self, seed_song_id: str, length: int = 10) -> List[Song]:
        """Build a playlist starting from ``seed_song_id``.

        Args:
            seed_song_id: Identifier of the first song.
            length: Desired playlist length; the generator may stop early when no
                valid cover can be found for the current artist.
        """

        if length <= 0:
            raise ValueError("length must be positive")

        playlist: List[Song] = [self.catalog.song(seed_song_id)]
        used_song_ids = {seed_song_id}
        used_compositions = {playlist[0].composition_id}
        current = playlist[0]

        while len(playlist) < length:
            next_song = self._pick_next_song(current, used_song_ids, used_compositions)
            if not next_song:
                break
            playlist.append(next_song)
            used_song_ids.add(next_song.id)
            used_compositions.add(next_song.composition_id)
            current = next_song
        return playlist

    def _pick_next_song(self, current: Song, used_song_ids: set[str], used_compositions: set[str]) -> Song | None:
        """Return the next cover, or ``None`` when the chain must stop."""

        candidates = []
        for cover in self.catalog.covers_for_artist(current.artist):
            if cover.id in used_song_ids:
                continue
            if cover.composition_id in used_compositions:
                continue
            original = self.catalog.song(cover.cover_of) if cover.cover_of else None
            if not original:
                continue
            if original.popularity < self.well_known_threshold:
                continue
            if cover.popularity >= original.popularity:
                continue
            gap = original.popularity - cover.popularity
            # Include the song id in the ranking tuple so ties break deterministically.
            candidates.append((gap, -cover.popularity, cover.id, cover))

        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][3]
