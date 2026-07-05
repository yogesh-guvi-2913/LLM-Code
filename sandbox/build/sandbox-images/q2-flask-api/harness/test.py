# test.py — exercises the candidate's Flask todo API over loopback and emits the
# exact score JSON on stdout: {"score":N,"max_score":M,"test_results":[...]}
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:3000"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=3) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = None
        return e.code, parsed
    except Exception:
        return 0, None


def case_get():
    s, b = req("GET", "/todos")
    assert s == 200, f"status {s}"
    assert isinstance(b, list), "not an array"


def case_post():
    s, b = req("POST", "/todos", {"title": "buy milk"})
    assert s == 201, f"status {s}"
    assert b and b.get("title") == "buy milk", "title not echoed"
    assert b.get("id") is not None, "no id"


def case_get_id():
    s, b = req("POST", "/todos", {"title": "walk dog"})
    assert s == 201 and b.get("id") is not None, "create failed"
    s2, b2 = req("GET", f"/todos/{b['id']}")
    assert s2 == 200, f"status {s2}"
    assert b2 and b2.get("title") == "walk dog", "wrong todo"


CASES = [
    ("GET /todos returns 200 array", 25, case_get),
    ("POST /todos creates (201)", 35, case_post),
    ("GET /todos/<id> returns created", 40, case_get_id),
]


def main():
    score = 0
    results = []
    for name, weight, fn in CASES:
        start = time.time()
        try:
            fn()
            score += weight
            results.append({"name": name, "passed": True,
                            "duration_ms": int((time.time() - start) * 1000)})
        except Exception as e:
            results.append({"name": name, "passed": False, "error": str(e),
                            "duration_ms": int((time.time() - start) * 1000)})
    print(json.dumps({"score": score, "max_score": 100, "test_results": results}))


if __name__ == "__main__":
    main()
