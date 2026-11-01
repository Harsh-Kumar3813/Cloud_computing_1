"""Queue consumer: reads Redis votes and stores them in PostgreSQL."""

import json
import logging
import os
import time

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
            logging.info("PostgreSQL is ready")
            return
        except psycopg.OperationalError:
            logging.info("Waiting for PostgreSQL (%s/30)", attempt + 1)
            time.sleep(2)
    raise RuntimeError("PostgreSQL did not become available")


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
            message = queue.blpop("votes", timeout=5)
            if message is None:
                continue
            payload = json.loads(message[1])
            choice = payload.get("choice")
            if choice not in ("Cats", "Dogs"):
                logging.warning("Discarding an invalid vote message")
                continue
            with connect_to_database() as connection:
                connection.execute(
                    "INSERT INTO votes (choice) VALUES (%s)",
                    (choice,),
                )
            logging.info("Stored one %s vote", choice)
        except (redis.RedisError, psycopg.Error, json.JSONDecodeError):
            logging.exception("Could not process the next vote; retrying shortly")
            time.sleep(2)


if __name__ == "__main__":
    main()
