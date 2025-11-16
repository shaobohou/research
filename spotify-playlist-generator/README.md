# Spotify Playlist Generator

This project experiments with algorithmic playlist sequencing focused on spotlighting cover songs. Starting from a seed song, every subsequent selection must be a less-famous cover of a well-known song by the artist of the current track. The work includes:

- A lightweight catalog model describing songs, artists, and cover relationships
- A deterministic playlist generator that enforces the "less-famous cover" rule
- Tests demonstrating the chaining logic across a curated sample catalog
- Notes capturing implementation details and future ideas

## Objectives

1. Represent a small but expressive dataset that encodes popular originals alongside modestly performing cover versions.
2. Implement a playlist generator that chains together songs by hopping from an artist to a cover of that artist's well-known material.
3. Provide usage examples and automated tests so that the behavior is reproducible.

## Usage

```python
from data import load_sample_catalog
from playlist import PlaylistGenerator

catalog = load_sample_catalog()
generator = PlaylistGenerator(catalog)
playlist = generator.generate(seed_song_id="aria-north-city-lights", length=5)
for song in playlist:
    print(f"{song.artist} – {song.title} ({song.popularity})")
```

## Example Playlist Starting with "I Put a Spell on You"

The CLI helper can either pick a random seed (via `--seed`) or start from a
specific song using `--seed-song`. The command below generates a deterministic
playlist that opens on "I Put a Spell on You" before following the required
chain of increasingly niche covers:

```bash
cd spotify-playlist-generator
python -m examples --length 5 \
  --seed-song screamin-jay-hawkins-i-put-a-spell-on-you
```

Sample output:

```
1. Screamin' Jay Hawkins – I Put a Spell on You (popularity 96)
2. Nina Simone – Little Demon (Nina Simone cover) (popularity 80) — cover of Screamin' Jay Hawkins – Little Demon
3. Muse – Feeling Good (Muse cover) (popularity 75) — cover of Nina Simone – Feeling Good
4. Velvet Echo – Supermassive Black Hole (Velvet Echo cover) (popularity 68) — cover of Muse – Supermassive Black Hole
5. Hollow Pines – Midnight Script (Hollow Pines cover) (popularity 55) — cover of Velvet Echo – Midnight Script
```

## Real Spotify Example Playlist

To hear how the concept translates to real recordings, jump into Spotify's
editorial [Rock Covers](https://open.spotify.com/playlist/37i9dQZF1DX2S9rTKTX6JP)
playlist. As of **16 Nov 2025** the first five entries are:

1. "Changes (Live From Villa Park) Back To The Beginning (feat. Nuno Bettencourt, Frank Bello, Adam Wakeman, II)" — YUNGBLUD, Nuno Bettencourt, Frank Bello, Adam Wakeman, II
2. "Miss Murder - From The “American Psycho” Comic Series Soundtrack" — Charlotte Sands
3. "We Didn’t Start The Fire" — Fall Out Boy
4. "Burning Down the House" — Paramore
5. "Karma Police" — Pierce The Veil

This curated queue offers a real-world reference for the sound the generator
targets—each entry is a reinterpretation of a recognizable hit performed by a
different, often less-famous artist.

## Key Findings

- A structured catalog with explicit cover relationships is essential; popularity comparisons alone are insufficient without identifying the original artist.
- Deterministic tie-breaking (favoring the largest popularity gap) helps the playlist feel intentional instead of random.
- The chaining requirement quickly stalls when an artist lacks covered material, so the dataset must be curated with overlapping cover networks.

## Next Steps

- Integrate a real Spotify API client and fetch live popularity metrics.
- Replace the static dataset with queries to crowd-sourced cover databases.
- Explore probabilistic or mood-aware transitions layered atop the cover-chain constraint.

## Tooling Notes

- The playlist generator directory now includes its own `pyproject.toml`, so you can install pytest, ruff, and pyright without modifying the shared repository toolchain.
- Run `pyright` from the repository root to type-check the playlist generator; the tool is expected to be installed globally rather than declared in the shared `pyproject.toml`.
- The playlist generator's regression tests live under `spotify-playlist-generator/tests/` so the shared `tests/` directory stays reserved for other investigations.
