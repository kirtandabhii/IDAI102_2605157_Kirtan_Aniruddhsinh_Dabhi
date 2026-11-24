"""SQLite persistence.

Every shopper has an anonymous id (a private link in the Streamlit app, a
cookie in the web edition), so several people can use one deployment without
seeing each other's purchases. No account is needed.

Each purchase stores the £ value, CO2 and exchange rate *at the moment it was
logged*, so later rate updates never change history.
"""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DEFAULT_SETTINGS = {
    "name": "",
    "country": None,       # picking one sets the currency; brands are the same everywhere
    "currency": "GBP",
    "co2_budget": 200,     # kg CO2e per month
    "spend_budget": 600,   # in the chosen currency per month
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sid          TEXT NOT NULL,
    product_type TEXT NOT NULL,
    brand        TEXT NOT NULL DEFAULT '',
    price        REAL NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'GBP',
    date         TEXT NOT NULL,
    note         TEXT NOT NULL DEFAULT '',
    swapped_from TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_purchases_sid ON purchases (sid, date);
CREATE TABLE IF NOT EXISTS settings (
    sid  TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS awards (
    sid       TEXT NOT NULL,
    badge_id  TEXT NOT NULL,
    month     TEXT NOT NULL,
    earned_at TEXT NOT NULL,
    PRIMARY KEY (sid, badge_id, month)
);
CREATE TABLE IF NOT EXISTS month_budgets (
    sid              TEXT NOT NULL,
    month            TEXT NOT NULL,
    co2_budget       REAL NOT NULL,
    spend_budget_gbp REAL NOT NULL,
    PRIMARY KEY (sid, month)
);
"""

# Columns added after the first release (migrated in place).
_MIGRATIONS = {"price_gbp": "REAL", "co2": "REAL", "rate": "REAL"}

PURCHASE_FIELDS = ("id", "product_type", "brand", "price", "currency", "date", "note",
                   "swapped_from", "price_gbp", "co2", "rate", "created_at")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)
            have = {row["name"] for row in db.execute("PRAGMA table_info(purchases)")}
            for column, kind in _MIGRATIONS.items():
                if column not in have:
                    db.execute(f"ALTER TABLE purchases ADD COLUMN {column} {kind}")
            db.commit()

    def _connect(self):
        """A connection that is committed *and closed* when the block ends."""
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return _Session(db)

    # -- purchases -----------------------------------------------------------
    def purchases(self, sid):
        """All purchases for one shopper as a list of dictionaries."""
        with self._connect() as db:
            rows = db.execute(
                f"SELECT {', '.join(PURCHASE_FIELDS)} FROM purchases WHERE sid = ? ORDER BY date, id",
                (sid,)).fetchall()
        return [dict(row) for row in rows]

    def get(self, sid, purchase_id):
        with self._connect() as db:
            row = db.execute(f"SELECT {', '.join(PURCHASE_FIELDS)} FROM purchases WHERE sid = ? AND id = ?",
                             (sid, purchase_id)).fetchone()
        return dict(row) if row else None

    def add(self, sid, purchase):
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO purchases (sid, product_type, brand, price, currency, date, note, swapped_from,"
                " price_gbp, co2, rate, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, purchase["product_type"], purchase.get("brand", ""), purchase["price"],
                 purchase.get("currency", "GBP"), purchase["date"], purchase.get("note", ""),
                 purchase.get("swapped_from"), purchase.get("price_gbp"), purchase.get("co2"),
                 purchase.get("rate"), purchase.get("created_at") or _now()))
            new_id = cur.lastrowid
        return self.get(sid, new_id)

    def add_many(self, sid, purchases):
        for p in purchases:
            self.add(sid, p)

    def update_type(self, sid, purchase_id, product_type, swapped_from, co2, brand=None):
        with self._connect() as db:
            if brand is None:
                db.execute("UPDATE purchases SET product_type = ?, swapped_from = ?, co2 = ? WHERE sid = ? AND id = ?",
                           (product_type, swapped_from, co2, sid, purchase_id))
            else:
                db.execute("UPDATE purchases SET product_type = ?, swapped_from = ?, co2 = ?, brand = ? "
                           "WHERE sid = ? AND id = ?", (product_type, swapped_from, co2, brand, sid, purchase_id))
        return self.get(sid, purchase_id)

    def freeze_missing(self, sid, freeze):
        """Give older rows (logged before values were frozen) a fixed £ value and CO2."""
        with self._connect() as db:
            rows = db.execute("SELECT id, product_type, price, currency FROM purchases "
                              "WHERE sid = ? AND (price_gbp IS NULL OR co2 IS NULL)", (sid,)).fetchall()
            for row in rows:
                price_gbp, co2, rate = freeze(dict(row))
                db.execute("UPDATE purchases SET price_gbp = ?, co2 = ?, rate = ? WHERE id = ?",
                           (price_gbp, co2, rate, row["id"]))

    def delete(self, sid, purchase_id):
        with self._connect() as db:
            db.execute("DELETE FROM purchases WHERE sid = ? AND id = ?", (sid, purchase_id))

    def clear(self, sid):
        with self._connect() as db:
            db.execute("DELETE FROM purchases WHERE sid = ?", (sid,))
            db.execute("DELETE FROM awards WHERE sid = ?", (sid,))
            db.execute("DELETE FROM month_budgets WHERE sid = ?", (sid,))

    # -- settings ------------------------------------------------------------
    def settings(self, sid):
        with self._connect() as db:
            row = db.execute("SELECT data FROM settings WHERE sid = ?", (sid,)).fetchone()
        data = dict(DEFAULT_SETTINGS)
        if row:
            data.update(json.loads(row["data"]))
        return data

    def save_settings(self, sid, values):
        data = self.settings(sid)
        data.update(values)
        with self._connect() as db:
            db.execute("INSERT INTO settings (sid, data) VALUES (?, ?) "
                       "ON CONFLICT(sid) DO UPDATE SET data = excluded.data", (sid, json.dumps(data)))
        return data

    # -- month budgets (each month keeps the budget it was planned with) -----
    def month_budget(self, sid, month):
        with self._connect() as db:
            row = db.execute("SELECT co2_budget, spend_budget_gbp FROM month_budgets WHERE sid = ? AND month = ?",
                             (sid, month)).fetchone()
        return dict(row) if row else None

    def month_budgets(self, sid):
        with self._connect() as db:
            rows = db.execute("SELECT month, co2_budget, spend_budget_gbp FROM month_budgets WHERE sid = ?",
                              (sid,)).fetchall()
        return {row["month"]: {"co2_budget": row["co2_budget"], "spend_budget_gbp": row["spend_budget_gbp"]}
                for row in rows}

    def set_month_budget(self, sid, month, co2_budget, spend_budget_gbp, overwrite=False):
        verb = "INSERT OR REPLACE" if overwrite else "INSERT OR IGNORE"
        with self._connect() as db:
            db.execute(f"{verb} INTO month_budgets (sid, month, co2_budget, spend_budget_gbp) VALUES (?, ?, ?, ?)",
                       (sid, month, co2_budget, spend_budget_gbp))

    # -- awards (remember which badges were already celebrated) --------------
    def awarded(self, sid, month):
        with self._connect() as db:
            rows = db.execute("SELECT badge_id FROM awards WHERE sid = ? AND month = ?", (sid, month)).fetchall()
        return {row["badge_id"] for row in rows}

    def award(self, sid, badge_ids, month):
        with self._connect() as db:
            db.executemany("INSERT OR IGNORE INTO awards (sid, badge_id, month, earned_at) VALUES (?, ?, ?, ?)",
                           [(sid, b, month, _now()) for b in badge_ids])


class _Session:
    """Context manager: commit on success, roll back on error, always close."""

    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc, tb):
        with closing(self.db):
            if exc_type is None:
                self.db.commit()
            else:
                self.db.rollback()
        return False
