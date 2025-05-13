from langchain_core.tools import tool
from spotify_functions import play_song, play_playlist

@tool
def play_song_tool(track_name: str) -> str:
    """Play a song by its name on Spotify."""
    play_song(track_name)
    return f"Playing {track_name}"

@tool
def play_playlist_tool(playlist_name: str) -> str:
    """Play a playlist by its name on Spotify."""
    play_playlist(playlist_name)
    return f"Playing playlist {playlist_name}"

# Export tools list
spotify_tools = [play_song_tool, play_playlist_tool]