"""Small voting web service. Votes are queued in Redis for the worker."""

import json
import os

from ui import page

import redis
from flask import Flask, redirect, request

app = Flask(__name__)
votes = redis.Redis.from_url(
    os.environ.get("REDIS_URL", "redis://redis:6379/0"),
    decode_responses=True,
    socket_connect_timeout=2,
)
CHOICES = ("Cats", "Dogs")


@app.get("/")
def home():
    return page("Cast your vote", '''<div class="eyebrow">The great companion debate</div><h1>Small choice.<br>Big personality.</h1><p>Quiet charm or boundless energy? Pick your favourite companion and see where everyone stands.</p><form method="post" action="/vote" class="grid"><button class="card" name="choice" value="Cats"><span class="icon" aria-hidden="true">🐈</span><h2>Team Cats</h2><p>Independent spirits. Expert nappers.</p><span class="action">Vote for Cats →</span></button><button class="card" name="choice" value="Dogs"><span class="icon" aria-hidden="true">🐕</span><h2>Team Dogs</h2><p>Loyal hearts. Everyday adventurers.</p><span class="action">Vote for Dogs →</span></button></form><p class="muted">One click submits your choice. No account needed.</p><a class="secondary" href="http://localhost:8081">See the results →</a>''')


@app.post("/vote")
def submit_vote():
    choice = request.form.get("choice", "")
    if choice not in CHOICES:
        return "Choose Cats or Dogs.", 400
    try:
        votes.rpush("votes", json.dumps({"choice": choice}))
    except redis.RedisError:
        app.logger.exception("Could not queue the vote")
        return "The vote queue is unavailable. Please try again.", 503
    return redirect("/thanks", code=303)


@app.get("/thanks")
def thanks():
    return page("Vote received", '''<div class="eyebrow">Choice received</div><h1>Thanks for weighing in.</h1><p>Your vote is on its way to the results. It may take a moment to appear.</p><a class="action" href="http://localhost:8081">View results →</a><a class="secondary" href="/">Back to voting</a>''')


@app.get("/healthz")
def health():
    try:
        votes.ping()
        return "ok", 200
    except redis.RedisError:
        return "Redis is unavailable", 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
