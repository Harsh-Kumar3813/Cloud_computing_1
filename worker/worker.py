"""Queue consumer: reads Redis votes and stores them in PostgreSQL."""

import json
import logging
import os
import time
import uuid

import psycopg
import redis

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)


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
    for attempt in range(30):
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
                connection.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS event_id UUID UNIQUE")
            logging.info("PostgreSQL is ready")
            return
        except psycopg.OperationalError:
            logging.info("Waiting for PostgreSQL (%s/30)", attempt + 1)
            time.sleep(2)
    raise RuntimeError("PostgreSQL did not become available")


# Keep one reservation across worker restarts. Scale the web tier independently.
RESERVE = """
local current = redis.call('LINDEX', KEYS[2], 0)
if current then return current end
local raw = redis.call('LPOP', KEYS[1])
if not raw then return nil end
local envelope = ARGV[1] .. '|' .. raw
redis.call('RPUSH', KEYS[2], envelope)
return envelope
"""


def main():
    queue = redis.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=10,
    )
    ensure_table()
    logging.info("Worker is listening for votes")

    while True:
        try:
            # Reserve one durable envelope. Legacy list entries receive a stable ID
            # inside the same atomic operation that removes them from the input.
            envelope = queue.eval(RESERVE, 2, "votes", "votes:processing", str(uuid.uuid4()))
            if envelope is None:
                time.sleep(0.1)
                continue
            reservation_id, raw = envelope.split("|", 1)
            try:
                payload = json.loads(raw)
                choice = payload["choice"]
                event_id = str(uuid.UUID(payload.get("id", reservation_id)))
                if choice not in ("Cats", "Dogs"):
                    raise ValueError("unknown choice")
            except (ValueError, TypeError, KeyError, AttributeError):
                logging.warning("Discarding malformed queue entry")
                queue.lrem("votes:processing", 1, envelope)
                continue
            with connect_to_database() as connection:
                inserted = connection.execute(
                    "INSERT INTO votes (choice, event_id) VALUES (%s, %s) "
                    "ON CONFLICT (event_id) DO NOTHING", (choice, event_id)
                ).rowcount
            queue.lrem("votes:processing", 1, envelope)
            logging.info("Stored one %s vote" if inserted else "Recovered duplicate %s delivery", choice)
        except (redis.RedisError, psycopg.Error, json.JSONDecodeError):
            logging.exception("Could not process the next vote; retrying shortly")
            time.sleep(2)


if __name__ == "__main__":
    main()
