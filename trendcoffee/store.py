"""SQLite persistence; each operation owns its connection and transaction."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS working (
                    session TEXT PRIMARY KEY REFERENCES sessions(id), data TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS memory (
                    session TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                    key TEXT, value TEXT, PRIMARY KEY(session, key));
                CREATE TABLE IF NOT EXISTS knowledge (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL, approved INTEGER, expires REAL);
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(id UNINDEXED, body);
                CREATE TABLE IF NOT EXISTS menu (id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS menu_categories (
                    id TEXT PRIMARY KEY, position INTEGER NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY, session TEXT REFERENCES sessions(id),
                    token TEXT NOT NULL, data TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY, quote TEXT UNIQUE REFERENCES quotes(id),
                    session TEXT REFERENCES sessions(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS handoffs (
                    id TEXT PRIMARY KEY, session TEXT REFERENCES sessions(id), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT REFERENCES sessions(id),
                    entity TEXT, type TEXT, created_at TEXT);
                CREATE TABLE IF NOT EXISTS print_jobs (
                    order_id TEXT PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
                    merchant_order_id TEXT NOT NULL, invoice_id TEXT UNIQUE,
                    state TEXT NOT NULL DEFAULT 'waiting', job_id TEXT,
                    title TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                    updated REAL NOT NULL, next_check REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS print_job_states ON print_jobs(state,next_check);
                CREATE UNIQUE INDEX IF NOT EXISTS print_merchant_order ON print_jobs(merchant_order_id);
                CREATE INDEX IF NOT EXISTS order_sessions ON orders(session);
                CREATE INDEX IF NOT EXISTS event_sessions ON events(session, id);
            """)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
