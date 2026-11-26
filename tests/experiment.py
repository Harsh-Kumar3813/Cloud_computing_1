"""Compose reliability and HTTP measurements. Supply a dedicated Compose test project."""
import argparse
import concurrent.futures
import csv
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path
from smoke import counts, submit

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
parser.add_argument("--env-file")
parser.add_argument("--override")
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
if not args.project.startswith("votingaudit"):
    parser.error("Use a new, dedicated votingaudit-prefixed Compose project for these interruption tests.")
args.out.mkdir(parents=True, exist_ok=True)
base = [os.getenv("DOCKER_CLI", "docker"), "compose", "-p", args.project]
if args.env_file:
    base += ["--env-file", args.env_file]
base += ["-f", "docker-compose.yml"]
if args.override:
    base += ["-f", args.override]


def compose(*argv, timeout=90):
    return subprocess.run(base + list(argv), capture_output=True, check=True, timeout=timeout,
                          text=True, encoding="utf8", errors="replace").stdout.strip()


def sql(query):
    return compose("exec", "-T", "db", "psql", "-U", "voting_app", "-d", "voting", "-Atc", query)


def queue(*cmd):
    return compose("exec", "-T", "redis", "redis-cli", "--raw", *cmd)


def wait_for(fn, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = fn()
            if result:
                return result
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(0.15)
    raise AssertionError("Expected state was not observed within the deadline")


def database_counts():
    return {s: int(n) for s, n in (line.split("|") for line in
            sql("SELECT choice,count(*) FROM votes GROUP BY choice").splitlines())}


def compare():
    html = counts()
    actual = database_counts()
    assert html == {k: actual.get(k, 0) for k in html}
    return html


def run_recovery():
    baseline = compare()
    compose("stop", "db")
    try:
        assert submit("Cats") == 303
        event = wait_for(lambda: queue("HGET", "votes:inflight", "id"))
        compose("stop", "worker")
        compose("restart", "redis")
        wait_for(lambda: queue("PING") == "PONG")
        assert queue("HGET", "votes:inflight", "id") == event
    finally:
        compose("start", "db", "worker")
    wait_for(lambda: counts()["Cats"] == baseline["Cats"] + 1)
    assert compare()["Dogs"] == baseline["Dogs"]
    print("PASS PostgreSQL outage, pending ID survived Redis restart, worker resumed", flush=True)
    compose("stop", "worker")
    try:
        assert submit("Dogs") == 303
        program = ("import redis,worker,uuid,os; q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True); "
                   "i,raw=q.eval(worker.CLAIM,2,'votes',worker.PENDING,str(uuid.uuid4())); worker.store(i,raw); "
                   "os._exit(23)")
        crash = subprocess.run(base+["run","--rm","--no-deps","-T","worker","python","-c",program],
                               capture_output=True, timeout=60)
        assert crash.returncode == 23, crash.returncode
        pending = queue("HGET", "votes:inflight", "id")
        assert pending
        persisted = sql("SELECT count(*) FROM votes WHERE event_id='" + str(__import__('uuid').UUID(pending)) + "'")
        assert persisted == "1"
    finally:
        compose("start", "worker")
    wait_for(lambda: queue("EXISTS", "votes:inflight") == "0")
    assert compare() == {k: n+1 for k, n in baseline.items()}
    compose("stop","redis")
    try:
        assert submit("Cats") == 503
    finally:
        compose("start","redis")
    wait_for(lambda: queue("PING") == "PONG")
    before = compare()
    compose("restart", "db", "vote", "result", "worker")
    wait_for(lambda: counts() == before)
    assert compare() == before
    return {"before":baseline, "after":before, "retained_claim_id":event, "postcommit_claim_id":pending,
            "exit_after_sql_commit":23,"rows_for_replayed_id":int(persisted),"redis_outage_status":503}


def measure(n, concurrency):
    before = compare()
    def request(i):
        t = time.perf_counter()
        try: ok = submit("Dogs" if i % 2 else "Cats") == 303
        except OSError: ok = False
        return ok, (time.perf_counter()-t)*1000
    t = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        responses = list(pool.map(request, range(n)))
    elapsed = time.perf_counter()-t
    latency = sorted(v for _, v in responses)
    accepted = sum(ok for ok,_ in responses)
    target = sum(before.values())+accepted
    wait_for(lambda: sum(counts().values()) == target,90)
    drained = time.perf_counter()-t-elapsed
    after = compare()
    assert sum(after.values()) == target
    return dict(requests=n,concurrency=concurrency,seconds=round(elapsed,4),successful=accepted,failed=n-accepted,
                requests_per_s=round(n/elapsed,2),mean_ms=round(statistics.mean(latency),2),
                p95_ms=round(latency[math.ceil(.95*n)-1],2),observed_drain_after_http_s=round(drained,4))


if __name__=="__main__":
    result=run_recovery()
    (args.out/"recovery.json").write_text(json.dumps(result,indent=2))
    rows=[]
    for n,c in ((50,1),(100,4)):
        rows.append(measure(n,c))
        print(rows[-1],flush=True)
        with (args.out/"load.csv").open("w",newline="") as handle:
            writer=csv.DictWriter(handle,fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
    (args.out/"sql-verified.json").write_text(json.dumps(compare(),indent=2))
    (args.out/"worker-tail.txt").write_text(compose("logs","--no-color","--tail","12","worker"),encoding="utf8")
    (args.out/"compose-status.txt").write_text(compose("ps"),encoding="utf8")
    (args.out/"queue.txt").write_text("LLEN votes = "+queue("LLEN","votes")+"\nEXISTS votes:inflight = "+queue("EXISTS","votes:inflight"))

