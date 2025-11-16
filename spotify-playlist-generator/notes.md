# Notes

## Session Summary
- Created a dedicated project directory with documentation and logging per repository guidelines.
- Modeled songs, artists, and cover relationships with dataclasses and a catalog abstraction.
- Implemented a deterministic playlist generator that enforces the "less-famous cover" rule.
- Authored a curated dataset that forms a loop of artists covering one another so playlists can continue chaining.
- Added unit tests to validate the rule and failure cases when no valid cover exists.
- Ran formatter, linter, type checker, and pytest to ensure code quality.
- Refocused the documentation on the playlist generator investigation so every deliverable speaks directly to the cover-chain experiment.
- Reverted the repository-level `pyright` dev dependency so tooling changes remain scoped to this project directory.
- Relocated the playlist generator tests under `spotify-playlist-generator/tests/` to keep the shared `tests/` directory untouched.
- Added a project-scoped `pyproject.toml` so pytest/ruff/pyright can be installed locally without editing the root configuration.
- Rebasing on the latest `main` snapshot ensured the playlist generator branch incorporates upstream fixes without merge commits.
- Added `generate_random_playlist` helper plus CLI wiring to produce reproducible random-seed playlists, and documented a sample output flow in the README.
- Added the missing `origin` remote pointing at the GitHub repository, fetched the latest `main`, and successfully rebased the investigation branch to keep it aligned without merge commits.
- Documented a snapshot of Spotify's "Rock Covers" playlist (including a direct link and song list) so readers can stream a real-world example of the cover-chain aesthetic.
- Updated the README's randomized example to use a more popular seed song so the first track better reflects the "well-known original" starting point.
- Expanded the sample catalog with the "I Put a Spell on You" lineage, taught the CLI to accept explicit seed song ids, and refreshed the README/test fixtures to demonstrate the new playlist flow.
- Enforced a "no repeated compositions" rule by tracking canonical song identities, expanded the dataset so every artist has alternate well-known material to cover, and refreshed the README/tests to prove the stricter behavior.
- Moved the playlist generator modules directly into the `spotify-playlist-generator/` directory so every tracked file lives within the investigation folder and updated imports/README/tests accordingly.
- Added a `dev` optional dependency group so the shared pre-commit hook can install tooling with `uv run --extra dev` and then ran the pre-commit checks locally.
- Fixed the candidate sorter to include song ids as tie-breakers so equal-gap, equal-popularity covers do not crash playlist generation, and added a regression test for the scenario.

## Ideas for Later
- Enrich the dataset with real metadata (release year, genre, energy) for more nuanced sequencing.
- Integrate external APIs (Spotify, CoverMe) with caching to hydrate the catalog dynamically.
- Experiment with stochastic selection that still honors the cover constraint but adds variety.
