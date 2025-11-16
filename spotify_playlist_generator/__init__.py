"""Spotify playlist generator focused on cover-song chaining."""

from .playlist import Catalog, PlaylistGenerator, Song
from .data import load_sample_catalog

__all__ = [
    "Catalog",
    "PlaylistGenerator",
    "Song",
    "load_sample_catalog",
]
