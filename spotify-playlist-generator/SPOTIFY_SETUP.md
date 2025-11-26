# Spotify API Setup Guide

## Quick Setup (5 minutes)

### Step 1: Get Spotify Credentials

1. Go to **https://developer.spotify.com/dashboard**
2. Log in with your Spotify account (free account works)
3. Click **"Create app"**
4. Fill in:
   - **App name**: "Playlist Generator" (or any name)
   - **App description**: "Generate cover song playlists"
   - **Redirect URI**: `http://localhost:8888/callback` (required but not used for this app)
   - Check the box to agree to terms
5. Click **"Save"**
6. Click **"Settings"** button
7. Copy your **Client ID** and **Client Secret**

### Step 2: Set Environment Variables

**Linux/Mac:**
```bash
export SPOTIFY_CLIENT_ID='your_client_id_here'
export SPOTIFY_CLIENT_SECRET='your_client_secret_here'
```

**Windows (PowerShell):**
```powershell
$env:SPOTIFY_CLIENT_ID='your_client_id_here'
$env:SPOTIFY_CLIENT_SECRET='your_client_secret_here'
```

**Windows (Command Prompt):**
```cmd
set SPOTIFY_CLIENT_ID=your_client_id_here
set SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

### Step 3: Run the Real Playlist Generator

```bash
cd /home/user/research/spotify-playlist-generator
python real_spotify_generator.py
```

## What It Does

The `real_spotify_generator.py` script:

1. ✓ Searches Spotify for real songs only (no fictional data)
2. ✓ Finds actual cover versions from different artists
3. ✓ Builds playlists with verified Spotify tracks
4. ✓ Ensures no artist repetition
5. ✓ Provides Spotify URLs for every song
6. ✓ Shows album info and release dates

## Example Seeds (Songs with Many Covers)

Good starting points that have many real covers on Spotify:

- **The Beatles** - "Yesterday"
- **Leonard Cohen** - "Hallelujah"
- **Johnny Cash** - "Hurt"
- **Nina Simone** - "Feeling Good"
- **Bill Withers** - "Ain't No Sunshine"
- **The Velvet Underground** - "Pale Blue Eyes"
- **Simon & Garfunkel** - "The Sound of Silence"

## API Limits

- Free tier: 1000 requests per day
- This should be plenty for generating playlists
- Results are cached to minimize API calls

## Troubleshooting

**"401 Unauthorized"**
- Check your credentials are correct
- Make sure you copied both Client ID and Secret
- Try creating a new app in the dashboard

**"429 Too Many Requests"**
- You've hit the rate limit
- Wait a few minutes and try again

**"No covers found"**
- Try a more popular seed song
- Some songs don't have many covers on Spotify
- Try songs from the "Example Seeds" list above
