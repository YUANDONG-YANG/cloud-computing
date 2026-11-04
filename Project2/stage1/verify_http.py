"""Verify a running Functions host and save real HTTP evidence.

Run `func start` first, then `python verify_http.py` from this folder.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    base = "http://localhost:7071/api"
    cases = [
        ("health", 200), ("insights", 200),
        ("recipes?diet_type=keto&search=chicken&page=1&limit=5", 200),
        ("recipes?diet_type=keto&search=chicken&page=2&limit=5", 200),
        ("recipes?search=stage1-no-match-000000", 200),
        ("clusters?k=3", 200), ("clusters?k=0", 400),
        ("clusters?k=11", 400), ("recipes?page=0", 400),
        ("recipes?diet_type=nonexistent", 404),
    ]
    evidence = {"captured_at": datetime.now(timezone.utc).isoformat(),
                "base_url": base, "requests": []}
    for route, expected in cases:
        request = Request(f"{base}/{route}", headers={"Origin": "http://localhost:5500"})
        try:
            response = urlopen(request, timeout=60)
        except HTTPError as exc:
            response = exc
        with response:
            status = response.status
            headers = dict(response.headers.items())
            payload = json.loads(response.read())
        assert status == expected, (route, status, payload)
        assert "application/json" in next(
            v for k, v in headers.items() if k.lower() == "content-type"
        )
        evidence["requests"].append({"url": f"{base}/{route}", "status": status,
                                     "headers": headers, "body": payload})
        print(f"PASS {status} GET /api/{route}")
    bodies = [item["body"] for item in evidence["requests"]]
    assert bodies[0]["status"] == "healthy"
    assert bodies[1]["summary"]["total_recipes"] == 7806
    assert len(bodies[1]["correlation"]) == 3
    for payload in bodies[2:4]:
        assert len(payload["recipes"]) == 5
        assert all(row["Diet_type"] == "keto" for row in payload["recipes"])
        assert all("chicken" in row["Recipe_name"].lower() for row in payload["recipes"])
    assert bodies[2]["recipes"] != bodies[3]["recipes"]
    assert bodies[4]["total"] == 0 and bodies[4]["recipes"] == []
    assert len(bodies[5]["points"]) == 7806
    assert sum(bodies[5]["cluster_counts"].values()) == 7806
    cors = {k.lower(): v for k, v in evidence["requests"][1]["headers"].items()}
    assert cors["access-control-allow-origin"] == "http://localhost:5500"
    target = Path(__file__).parent / "docs" / "http-results.json"
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("PASS payload assertions and local CORS; evidence: docs/http-results.json")


if __name__ == "__main__":
    main()
