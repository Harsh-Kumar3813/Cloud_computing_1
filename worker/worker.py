"""Queue consumer: reads Redis votes and stores them in PostgreSQL."""

import json
import logging
import os
import time
import uuid
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
                connection.execute("SELECT pg_advisory_xact_lock(8287)")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS votes (
                        id BIGSERIAL PRIMARY KEY,
                        choice TEXT NOT NULL CHECK (choice IN ('Cats', 'Dogs')),
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                connection.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS event_id UUID")
                connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS votes_event_id_idx ON votes(event_id)")
            logging.info("PostgreSQL is ready")
            return
        except psycopg.OperationalError:
            logging.info("Waiting for PostgreSQL (%s/30)", attempt + 1)
            time.sleep(2)
    raise RuntimeError("PostgreSQL did not become available")


# One in-flight slot preserves the order of legacy list entries, including identical payloads.
# A second worker may replay the slot concurrently. PostgreSQL de-duplicates its claim ID.
CLAIM = """
local current = redis.call('HMGET', KEYS[2], 'id', 'payload')
if current[1] then return current end
local payload = redis.call('LINDEX', KEYS[1], 0)
if not payload then return nil end
redis.call('HSET', KEYS[2], 'id', ARGV[1], 'payload', payload)
redis.call('LPOP', KEYS[1])
return {ARGV[1], payload}
"""
ACK = """
if redis.call('HGET', KEYS[1], 'id') == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""
PENDING = "votes:inflight"
heartbeat = 0.0
ready = False


def store(event_id, raw):
    try:
        payload = json.loads(raw)
        choice = payload.get("choice") if isinstance(payload, dict) else None
    except (ValueError, TypeError):
        choice = None
    if choice not in ("Cats", "Dogs"):
        logging.warning("Discarding an invalid queue message")
        return
    with connect_to_database() as connection:
        inserted = connection.execute(
            "INSERT INTO votes (event_id, choice) VALUES (%s, %s) "
            "ON CONFLICT (event_id) DO NOTHING", (event_id, choice)
        ).rowcount
    logging.info("%s %s vote %s", "Stored" if inserted else "Replayed", choice, event_id)


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        alive = time.monotonic() - heartbeat < 30
        ok = alive if self.path == "/livez" else alive and ready
        self.send_response((200 if ok else 503) if self.path in ("/livez", "/healthz") else 404)
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    global heartbeat, ready
    queue = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"),
                                 decode_responses=True, socket_connect_timeout=2, socket_timeout=3)
    heartbeat = time.monotonic()
    server = ThreadingHTTPServer(("0.0.0.0", 8082), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    ensure_table()
    next_db_check = 0
    logging.info("Worker is listening for votes")
    while True:
        heartbeat = time.monotonic()
        try:
            claimed = queue.eval(CLAIM, 2, "votes", PENDING, str(uuid.uuid4()))
            if claimed:
                event_id, raw = claimed
                store(event_id, raw)
                queue.eval(ACK, 1, PENDING, event_id)
            else:
                if time.monotonic() >= next_db_check:
                    with connect_to_database() as connection:
                        connection.execute("SELECT 1")
                    next_db_check = time.monotonic() + 5
                time.sleep(0.15)
            ready = True
        except (redis.RedisError, psycopg.Error) as error:
            ready = False
            next_db_check = 0
            logging.warning("Dependency unavailable (%s); retaining pending work", type(error).__name__)
            time.sleep(1)


if __name__ == "__main__":
    main()
