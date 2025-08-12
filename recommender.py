import os
import pandas as pd
import webbrowser
import random
from datetime import datetime

# Paths (robust to being imported from other modules)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SONGS_CSV = os.path.join(BASE_DIR, "songs.csv")
LOG_PATH = os.path.join(BASE_DIR, "logs.txt")


def log_event(event: str):
    """Append an event to logs.txt with timestamp."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {event}\n")
    except Exception as e:
        print("Logging failed:", e)


def load_songs():
    """Load the songs CSV into a DataFrame, handling errors."""
    if not os.path.exists(SONGS_CSV):
        raise FileNotFoundError(f"{SONGS_CSV} does not exist.")
    return pd.read_csv(SONGS_CSV)


def filter_songs(mood: str, languages=None, artists=None) -> pd.DataFrame:
    """
    Filter songs by mood, optional languages, and optional artists.
    - mood: dominant emotion/mood string
    - languages: list of language strings (e.g., ['hindi', 'english'])
    - artists: list of artist names (case-insensitive)
    Returns a DataFrame of matching songs.
    """
    try:
        df = load_songs()
    except Exception as e:
        log_event(f"Failed to load songs.csv: {e}")
        return pd.DataFrame()  # empty

    mood_lower = mood.lower()
    filtered = df[df['mood'].str.lower().str.contains(mood_lower, na=False)]

    if languages:
        langs = [l.strip().lower() for l in languages if l and l.strip()]
        if langs:
            filtered = filtered[filtered['language'].str.lower().isin(langs)]

    if artists:
        arts = [a.strip().lower() for a in artists if a and a.strip()]
        if arts:
            filtered = filtered[filtered['artist'].str.lower().isin(arts)]

    return filtered


def suggest_music(mood: str, languages=None, artists=None, num: int = 1):
    """
    Suggest up to `num` songs based on mood and optional filters.
    Opens each suggested song's URL in the default browser and returns a list of dicts.
    """
    filtered = filter_songs(mood, languages=languages, artists=artists)

    if filtered.empty:
        print(f"No songs found for mood='{mood}'"
              f"{' with languages=' + str(languages) if languages else ''}"
              f"{' and artists=' + str(artists) if artists else ''}.")
        log_event(f"No songs found for mood='{mood}' languages={languages} artists={artists}")
        return []

    # sample up to num unique songs
    sample_n = min(num, len(filtered))
    sampled = filtered.sample(n=sample_n)

    suggestions = []
    for _, row in sampled.iterrows():
        title = row.get('title', 'Unknown')
        artist = row.get('artist', 'Unknown')
        language = row.get('language', 'Unknown')
        url = row.get('url', None)
        mood_tag = row.get('mood', mood)

        suggestions.append({
            "title": title,
            "artist": artist,
            "language": language,
            "mood": mood_tag,
            "url": url
        })

        log_event(f"Suggested ({mood}) [{language}] by {artist}: {title}")
        if url and isinstance(url, str) and url.strip():
            try:
                webbrowser.open(url)
            except Exception as e:
                log_event(f"Failed to open URL {url}: {e}")

    return suggestions
