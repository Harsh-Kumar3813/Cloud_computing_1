"""Run ONLY on a disposable Compose project. Stops its worker, DB and Redis."""
import argparse
import concurrent.futures
import json
import math
import statistics
import subprocess
import time
import uuid
from http.client import HTTPConnection
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--project", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if not args.project.startswith("courseaudit"):
    parser.error("Use a separate courseaudit-prefixed project")
def dc(*args_):
    return subprocess.check_output(["docker","compose","-p",args.project,*args_],text=True).strip()
def sql(q):
    return dc("exec","-T","db","psql","-U","voting_app","-d","voting","-Atc",q)
def redis(*cmd):
    return dc("exec","-T","redis","redis-cli","--raw",*cmd)
def http(port,path="/",choice=None):
    c=HTTPConnection("127.0.0.1",port,timeout=8)
    try:
        c.request("GET" if choice is None else "POST",path,None if choice is None else "choice="+choice,{"Content-Type":"application/x-www-form-urlencoded"})
        r=c.getresponse()
        return r.status,r.read().decode()
    finally: c.close()
def until(fn,limit=45):
    deadline=time.monotonic()+limit
    while time.monotonic()<deadline:
        try:
            if fn(): return
        except (ConnectionError, TimeoutError, subprocess.CalledProcessError):
            pass
        time.sleep(.2)
    raise AssertionError("timed out")
def count():return int(sql("select count(*) from votes"))
out=args.output
out.mkdir(parents=True,exist_ok=True)
record={}
def passed(name,observed):
    record[name]=observed
    (out/"acceptance.json").write_text(json.dumps(record,indent=2))
    print(name, observed,flush=True)
baseline=count()
for service, port in (("vote", 8080), ("result", 8081)):
    if dc("port", service, "8080") != f"127.0.0.1:{port}":
        raise RuntimeError(f"Expected {service} in the test project on local port {port}")
assert http(8080,"/vote","Other")[0]==400 and count()==baseline
passed("invalid",{"status":400,"rows_before_and_after":baseline})
dc("stop","db")
assert http(8080,"/vote","Cats")[0]==303
until(lambda:redis("LLEN","votes:processing")=="1")
assert http(8081,"/healthz")[0]==503 and http(8081,"/livez")[0]==200
dc("kill","-s","SIGKILL","worker")
dc("start","db")
dc("up","-d","--wait","worker")
until(lambda:count()==baseline+1)
passed("database_outage_and_worker_kill",{"before":baseline,"after":count(),"observed_reserved":1})
event=sql("select event_id from votes where event_id is not null order by id desc limit 1")
dc("stop","worker")
redis("RPUSH","votes",json.dumps({"id":event,"choice":"Cats"}))
redis("RPUSH","votes",json.dumps({"choice":"Dogs"}))
dc("restart","redis")
until(lambda:redis("PING")=="PONG")
assert redis("LLEN","votes")=="2"
dc("start","worker")
until(lambda:count()==baseline+2 and redis("LLEN","votes")=="0" and redis("LLEN","votes:processing")=="0")
passed("replay_and_legacy",{"pending_after_redis_restart":2,"additional_rows":1})
dc("stop","redis")
assert http(8080,"/vote","Dogs")[0]==503
dc("start","redis")
until(lambda:http(8080,"/healthz")[0]==200)
passed("redis_outage",{"vote_status":503,"recovered_health":200})
dc("restart","db","worker","result","vote")
until(lambda:http(8081,"/healthz")[0]==200)
assert count()==baseline+2
passed("database_restart",{"rows":count()})
runs=[]
for n in (50,100):
    before=count()
    def vote(i):
        t=time.perf_counter()
        status=http(8080,"/vote","Cats" if i%2==0 else "Dogs")[0]
        return status,(time.perf_counter()-t)*1000
    t=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        replies=list(pool.map(vote,range(n)))
    elapsed=time.perf_counter()-t
    ok=sum(s==303 for s,_ in replies)
    until(lambda:count()==before+ok)
    l=sorted(v for _,v in replies)
    runs.append(dict(requests=n,concurrency=4,success=ok,failed=n-ok,seconds=round(elapsed,3),requests_per_s=round(n/elapsed,2),mean_ms=round(statistics.mean(l),2),p95_ms=round(l[math.ceil(.95*n)-1],2),drain_check_s=round(time.perf_counter()-t-elapsed,3)))
    assert ok==n
(out/"load.json").write_text(json.dumps(runs,indent=2))
rows=dict(x.split("|") for x in sql("select choice,count(*) from votes group by choice order by choice").splitlines())
body=http(8081)[1]
for choice,value in rows.items():
    assert ("Team "+choice) in body and (value+" votes</p>") in body.split("Team "+choice,1)[1].split("</section>",1)[0]
passed("sql_and_results",rows)

