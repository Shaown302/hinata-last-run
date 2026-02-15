import sqlite3
import json
import os
import time


DB_FILE = "bot.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        full_name TEXT,
        username TEXT,
        joined_at TEXT,
        last_active_at TEXT,
        message_count INTEGER DEFAULT 0,
        is_premium INTEGER DEFAULT 0,
        language_code TEXT
    )''')
    
    # Groups Table
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY,
        title TEXT,
        type TEXT,
        added_at TEXT,
        last_active_at TEXT,
        member_count INTEGER DEFAULT 0
    )''')
    
    # Broadcasts Table
    c.execute('''CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        target TEXT,
        sent_count INTEGER,
        failed_count INTEGER,
        timestamp TEXT,
        message_ids TEXT -- JSON string of {chat_id: message_id}
    )''')
    
    conn.commit()
    conn.close()
    
    # Run migration if needed
    if is_db_empty():
        migrate_from_json()

def is_db_empty():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    user_count = c.fetchone()[0]
    conn.close()
    return user_count == 0

def migrate_from_json():
    print("Migrating data from JSON to SQLite...")
    conn = get_connection()
    c = conn.cursor()
    
    # Migrate Users
    if os.path.exists("users.json"):
        try:
            with open("users.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    users = json.loads(content)
                    for u in users:
                        if isinstance(u, dict):
                            uid = u.get("id")
                            name = u.get("name")
                            username = u.get("username")
                            joined = u.get("joined_at", time.strftime("%Y-%m-%d %H:%M:%S"))
                            c.execute("INSERT OR IGNORE INTO users (id, full_name, username, joined_at) VALUES (?, ?, ?, ?)",
                                      (uid, name, username, joined))
                        else:
                            # Legacy list of IDs
                            c.execute("INSERT OR IGNORE INTO users (id, full_name, username, joined_at) VALUES (?, ?, ?, ?)",
                                      (u, "Legacy User", "unknown", time.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception as e:
            print(f"Error migrating users: {e}")

    # Migrate Groups
    if os.path.exists("groups.json"):
        try:
            with open("groups.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    groups = json.loads(content)
                    for g in groups:
                        if isinstance(g, dict):
                            gid = g.get("id")
                            title = g.get("title")
                            gtype = g.get("type", "supergroup")
                            added = g.get("added_at", time.strftime("%Y-%m-%d %H:%M:%S"))
                            c.execute("INSERT OR IGNORE INTO groups (id, title, type, added_at) VALUES (?, ?, ?, ?)",
                                      (gid, title, gtype, added))
                        else:
                            c.execute("INSERT OR IGNORE INTO groups (id, title, type, added_at) VALUES (?, ?, ?, ?)",
                                      (g, "Legacy Group", "supergroup", time.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception as e:
            print(f"Error migrating groups: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

# --- User Operations ---

def add_user(user_id, full_name, username):
    conn = get_connection()
    c = conn.cursor()
    
    # Upsert logic
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if exists
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = c.fetchone()
    
    if exists:
        # Update
        c.execute("UPDATE users SET full_name = ?, username = ?, last_active_at = ? WHERE id = ?",
                  (full_name, username, now, user_id))
    else:
        # Insert
        c.execute("INSERT INTO users (id, full_name, username, joined_at, last_active_at) VALUES (?, ?, ?, ?, ?)",
                  (user_id, full_name, username, now, now))
        
    conn.commit()
    conn.close()
    return not exists # Returns True if new user

def get_all_users():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY joined_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Group Operations ---

def add_group(chat_id, title, chat_type):
    conn = get_connection()
    c = conn.cursor()
    
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute("SELECT id FROM groups WHERE id = ?", (chat_id,))
    exists = c.fetchone()
    
    if exists:
        c.execute("UPDATE groups SET title = ?, last_active_at = ? WHERE id = ?", (title, now, chat_id))
    else:
        c.execute("INSERT INTO groups (id, title, type, added_at, last_active_at) VALUES (?, ?, ?, ?, ?)",
                  (chat_id, title, chat_type, now, now))
                  
    conn.commit()
    conn.close()

def get_all_groups():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM groups ORDER BY added_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_group(chat_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

# --- Broadcast Operations ---

def add_broadcast(text, target, sent, failed, message_ids_map):
    conn = get_connection()
    c = conn.cursor()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO broadcasts (text, target, sent_count, failed_count, timestamp, message_ids) VALUES (?, ?, ?, ?, ?, ?)",
              (text, target, sent, failed, now, json.dumps(message_ids_map)))
    conn.commit()
    conn.close()

def get_all_broadcasts():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM broadcasts ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_broadcast(b_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM broadcasts WHERE id = ?", (b_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_broadcast_record(b_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM broadcasts WHERE id = ?", (b_id,))
    conn.commit()
    conn.close()
