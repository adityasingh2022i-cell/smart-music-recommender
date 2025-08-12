import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash TEXT,
        preferred_languages TEXT,  -- comma separated e.g. "hindi,english"
        preferred_artists TEXT      -- comma separated
    )
    """)
    conn.commit()
    conn.close()

def create_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    pw_hash = generate_password_hash(password)
    try:
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pw_hash))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists"
    conn.close()
    return True, "Created"

def validate_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return False
    stored = row[0]
    return check_password_hash(stored, password)

def get_user(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, preferred_languages, preferred_artists FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "username": row[1],
        "preferred_languages": row[2] or "",
        "preferred_artists": row[3] or ""
    }

def update_preferences(username, languages_list, artists_list):
    lang_csv = ",".join([l.strip().lower() for l in languages_list if l.strip()])
    artist_csv = ",".join([a.strip() for a in artists_list if a.strip()])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET preferred_languages=?, preferred_artists=? WHERE username=?",
              (lang_csv, artist_csv, username))
    conn.commit()
    conn.close()
