# Playlist Generator

Generate playlists using **real songs** by chaining cover versions. Starting from a seed song, each subsequent track is a cover by a different artist, creating unique playlists that explore how songs evolve through reinterpretation.

## Two Options

### Option 1: MusicBrainz (Recommended - No API Key!)
✓ **No registration needed** - just run it  
✓ **Free forever** - community-maintained  
✓ **Cover relationships** - built into the database  
⚠ Rate limited to 1 request/second  

### Option 2: Spotify API
✓ **Richer metadata** - accurate popularity scores  
✓ **Larger catalog** - more covers available  
⚠ Requires API credentials (2 min signup)

## Features

✓ **Real Spotify songs only** - searches actual Spotify catalog
✓ **Cover discovery** - finds authentic cover versions by different artists
✓ **No artist repetition** - each artist appears only once
✓ **Spotify URLs** - every song includes a playable link
✓ **Album metadata** - shows album name and release date
✓ **Smart chaining** - favors more popular covers to extend playlists

## Quick Start

### MusicBrainz (No Setup Required!)

```bash
pip install musicbrainzngs
python musicbrainz_generator.py
```

That's it! No API keys, no registration.

### Spotify (Requires Credentials)

#### 1. Get Spotify Credentials (2 minutes)

1. Go to **https://developer.spotify.com/dashboard**
2. Log in with your Spotify account (free account works)
3. Click **"Create app"**
   - App name: "Playlist Generator"
   - Redirect URI: `http://localhost:8888/callback`
4. Copy your **Client ID** and **Client Secret**

See [SPOTIFY_SETUP.md](SPOTIFY_SETUP.md) for detailed instructions.

### 2. Set Credentials

```bash
export SPOTIFY_CLIENT_ID='your_client_id_here'
export SPOTIFY_CLIENT_SECRET='your_client_secret_here'
```

### 3. Run the Generator

```bash
python real_spotify_generator.py
```

## How It Works

The generator:
1. Searches Spotify for your seed song
2. Finds cover versions by different artists
3. Selects the most popular cover (to extend the chain)
4. Repeats from the new artist's catalog
5. Ensures no artist appears twice

## Example Output

```
Seed: Nina Simone - Feeling Good

1. Nina Simone – Feeling Good (popularity 80)
   🔗 https://open.spotify.com/track/...
   💿 I Put A Spell On You (1965)

2. Muse – Feeling Good (popularity 73)
   🔗 https://open.spotify.com/track/...
   💿 Hullabaloo Soundtrack (2002)
   — cover of Nina Simone – Feeling Good

3. [Next artist's cover of a Muse song...]
```

## Best Seed Songs

Songs with many real covers on Spotify:

- **The Beatles** - "Yesterday"
- **Leonard Cohen** - "Hallelujah"
- **Johnny Cash** - "Hurt"
- **Nina Simone** - "Feeling Good"
- **Bill Withers** - "Ain't No Sunshine"
- **Simon & Garfunkel** - "The Sound of Silence"
- **Jeff Buckley** - "Hallelujah"

## API Usage

Free tier: 1,000 requests/day (plenty for playlist generation)

Results are cached to minimize API calls.

## Troubleshooting

**"401 Unauthorized"**
- Check your credentials are correct
- Try creating a new app in the Spotify dashboard

**"No covers found"**
- Try a more popular seed song
- Some songs don't have many covers on Spotify
- Use songs from the "Best Seed Songs" list above

**"429 Too Many Requests"**
- Rate limit reached
- Wait a few minutes and try again

## Files

- `musicbrainz_generator.py` - MusicBrainz version (no API key)
- `real_spotify_generator.py` - Spotify version (requires API key)
- `SPOTIFY_SETUP.md` - Detailed Spotify setup guide
- `tests/` - Test suite (14 tests, all passing)
- `README.md` - This file

## Requirements

- Python 3.12+

**For MusicBrainz (no API key):**
- `musicbrainzngs`: `pip install musicbrainzngs`

**For Spotify:**
- `spotipy`: `pip install spotipy`
- Spotify API credentials (free, 2 min setup)

## Example Use Case

Create unique playlists that:
- Explore how classic songs are reinterpreted
- Discover new artists through covers
- Build thematic playlists around iconic songs
- Show the evolution of popular music through covers
