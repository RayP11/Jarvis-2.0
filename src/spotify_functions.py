import os
import re
import sys
import time
import hashlib
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError
from new_voice import speak_text

# ---------------------------------------------------------------------------
# 1️⃣  Environment & basic validation
# ---------------------------------------------------------------------------
load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URL")
# Optional: specific device ID from env
preferred_device_id = os.getenv("DEVICE_ID")

if not all([client_id, client_secret, redirect_uri]):
    raise ValueError("Missing Spotify credentials in environment variables.")

# ---------------------------------------------------------------------------
# 2️⃣  Auth helper — unique cache per client‑ID and auto‑refresh
# ---------------------------------------------------------------------------

def _cache_path_for(client: str) -> str:
    """Generate a deterministic cache filename per client ID."""
    digest = hashlib.sha256(client.encode()).hexdigest()[:8]
    return f".cache-spotify-{digest}"

def get_spotify_client(force_reauth: bool = False) -> spotipy.Spotify:
    """Return an authenticated Spotipy client, refreshing or rebuilding cache if needed."""
    cache_path = _cache_path_for(client_id)

    if force_reauth and os.path.exists(cache_path):
        os.remove(cache_path)

    try:
        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state user-modify-playback-state playlist-read-private",
            cache_path=cache_path,
            show_dialog=True,   # always pop dialog if cache/token becomes invalid
            open_browser=True,
        )

        # trigger token fetch so we fail early if creds are wrong
        token_info = auth_manager.get_access_token(as_dict=True)
        if auth_manager.is_token_expired(token_info):
            print("🔁  Token expired – refreshing …")
            token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
            print("✅  Token refreshed.")

        return spotipy.Spotify(auth_manager=auth_manager)

    except SpotifyOauthError as e:
        # Most common cause: credentials changed → old cache invalid
        if os.path.exists(cache_path):
            os.remove(cache_path)
        raise RuntimeError(f"Spotify authentication failed: {e}") from e

# Single global client instance
sp = get_spotify_client()

# ---------------------------------------------------------------------------
# 3️⃣  Device helper
# ---------------------------------------------------------------------------

def _ensure_device(device_id: str | None = None) -> str:
    """Return a usable device ID (falls back to first active device)."""
    devices = sp.devices()["devices"]
    if not devices:
        raise RuntimeError("No active Spotify devices found. Launch Spotify and try again.")

    # Respect requested device if present
    if device_id and any(d["id"] == device_id for d in devices):
        return device_id

    return devices[0]["id"]  # first active device

# ---------------------------------------------------------------------------
# 4️⃣  Playback helpers
# ---------------------------------------------------------------------------

def play_song(track_name: str, device_id: str | None = None, retries: int = 3):
    try:
        results = sp.search(q=track_name, type="track", limit=1)
        tracks = results["tracks"]["items"]
        if not tracks:
            print("No tracks found for the search term.")
            return

        chosen_device = _ensure_device(device_id)
        sp.start_playback(device_id=chosen_device, uris=[tracks[0]["uri"]])
        print(f"▶️  Playing track: {tracks[0]['name']} – {tracks[0]['artists'][0]['name']}")

    except Exception as e:
        print(f"Error playing song: {e}")
        if retries:
            print(f"Retrying ({retries}) …")
            play_song(track_name, device_id, retries - 1)


def play_playlist(playlist_name: str, device_id: str | None = None, retries: int = 3):
    try:
        results = sp.search(q=f"playlist:{playlist_name}", type="playlist", limit=1)
        playlists = results["playlists"]["items"]
        if not playlists:
            print("No playlists found for the search term.")
            return

        chosen_device = _ensure_device(device_id)
        sp.start_playback(device_id=chosen_device, context_uri=playlists[0]["uri"])
        print(f"▶️  Playing playlist: {playlists[0]['name']}")

    except Exception as e:
        print(f"Error playing playlist: {e}")
        if retries:
            print(f"Retrying ({retries}) …")
            play_playlist(playlist_name, device_id, retries - 1)

# ---------------------------------------------------------------------------
# 5️⃣  Natural‑language wrapper
# ---------------------------------------------------------------------------

def play_music(command: str):
    """Interpret a voice/text command and start playback."""
    os.system("spotify")  # ensure client running (Linux-desktops)

    query = command.lower().strip()
    # Remove anything before 'play' or 'put on'
    match = re.search(r"(play|put on)\s+(.*)", query)
    if match:
        query = match.group(2)
    # Remove anything after 'on spotify'
    query = query.split(" on spotify")[0].strip()

    response = f"Playing {query} on Spotify"
    print(f"Friday: {response}")
    speak_text(response)
    time.sleep(1.5)

    if "playlist" in query:
        play_playlist(query.replace("playlist", "").strip(), preferred_device_id)
    else:
        play_song(query, preferred_device_id)

    return response

# ---------------------------------------------------------------------------
# 6️⃣  CLI entry‑point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--reset-auth" in sys.argv:
        get_spotify_client(force_reauth=True)
        print("🧹  Cache cleared. Restart without --reset-auth to authenticate afresh.")
    else:
        # Default demo command
        play_music("ACDC")
