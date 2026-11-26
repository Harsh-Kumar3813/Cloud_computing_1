"""Run against an isolated, otherwise idle Compose project. Uses only the standard library."""
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

VOTE = os.getenv("TEST_VOTE_URL", "http://127.0.0.1:8080")
RESULT = os.getenv("TEST_RESULT_URL", "http://127.0.0.1:8081")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def submit(choice):
    request = urllib.request.Request(VOTE + "/vote", urllib.parse.urlencode({"choice": choice}).encode())
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=6) as reply:
            return reply.status
    except urllib.error.HTTPError as error:
        return error.code


def counts():
    with urllib.request.urlopen(RESULT, timeout=6) as reply:
        cards = re.findall(r"Team (Cats|Dogs)</h2>.*?<p>(\d+) votes</p>", reply.read().decode(), re.S)
        return {choice: int(count) for choice, count in cards}


def main():
    before = counts()
    assert set(before) == {"Cats", "Dogs"}, before
    for endpoint in (VOTE, RESULT):
        with urllib.request.urlopen(endpoint + "/healthz", timeout=5) as reply:
            assert reply.status == 200
    for choice in before:
        assert submit(choice) == 303
    assert submit("Birds") == 400
    expected = {c: n + 1 for c, n in before.items()}
    for _ in range(100):
        if counts() == expected:
            break
        time.sleep(0.1)
    assert counts() == expected
    print("PASS HTTP health, two accepted ballots, invalid ballot rejection and processed HTML counts", expected)


if __name__ == "__main__":
    main()
