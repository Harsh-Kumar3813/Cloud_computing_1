"""Results web service. It reads the vote totals from PostgreSQL."""

import os
import time

from ui import page

import psycopg
from flask import Flask

app = Flask(__name__)
CHOICES = ("Cats", "Dogs")


def connect_to_database():
    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ.get("POSTGRES_DB", "voting"),
        user=os.environ.get("POSTGRES_USER", "voting_app"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )


def ensure_table():
    for _ in range(30):
        try:
            with connect_to_database() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS votes (
                        id BIGSERIAL PRIMARY KEY,
                        choice TEXT NOT NULL CHECK (choice IN ('Cats', 'Dogs')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            return
        except psycopg.OperationalError:
            time.sleep(2)
    raise RuntimeError("PostgreSQL did not become available")


@app.get("/")
def home():
    try:
        with connect_to_database() as connection:
            rows = connection.execute(
                "SELECT choice, COUNT(*) FROM votes GROUP BY choice"
            ).fetchall()
    except psycopg.Error:
        app.logger.exception("Could not read vote totals")
        return "The results database is unavailable. Please retry.", 503

    totals = dict(rows)
    counts = {choice: totals.get(choice, 0) for choice in CHOICES}
    total_votes = sum(counts.values())
    cards = ""
    for choice in CHOICES:
        percentage = counts[choice] * 100 / total_votes if total_votes else 0
        icon = "🐈" if choice == "Cats" else "🐕"
        style = "" if choice == "Cats" else "dog"
        cards += f'<section class="card {style}"><span class="icon" aria-hidden="true">{icon}</span><h2>Team {choice}</h2><div class="count">{percentage:.0f}%</div><div class="track" aria-hidden="true"><div class="bar" style="width:{percentage:.2f}%"></div></div><p>{counts[choice]} votes</p></section>'
    message = "No votes yet. Be the first to choose a side." if not total_votes else f"{total_votes} votes counted. Every choice adds to the story."
    return page("Results", f'<div class="eyebrow">The community verdict</div><h1>Every vote counts.</h1><p>{message}</p><div class="grid">{cards}</div><div class="notice">Results reflect processed votes. <a href="/">Refresh results</a> to see the latest count.</div><a class="action" href="http://localhost:8080">Cast a vote →</a>')


@app.get("/healthz")
def health():
    try:
        with connect_to_database() as connection:
            connection.execute("SELECT 1")
        return "ok", 200
    except psycopg.Error:
        return "PostgreSQL is unavailable", 503


if __name__ == "__main__":
    ensure_table()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
