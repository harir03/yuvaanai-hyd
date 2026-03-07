"""
T0.5 — Redis Client Tests (using in-memory fallback)

Tests:
1. Initialize in memory mode
2. Cache set and get
3. Cache TTL expiration
4. Cache delete
5. Cache exists
6. Stage worker output
7. Get all staged outputs
8. Clear staging
9. Session state save/load
10. Cache namespacing (keys don't collide)
"""

import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.storage.redis_client import RedisClient, reset_redis_client

PASSED = 0
FAILED = 0


def report(name: str, ok: bool, detail: str = ""):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name}  —  {detail}")


# ──────────────────────────────────────────────
# Test 1: Initialize memory mode
# ──────────────────────────────────────────────
def test_init_memory():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()
            ok = rc.is_initialized and rc.backend == "memory"
            await rc.close()
            return ok

        ok = asyncio.run(_run())
        report("Initialize in memory mode", ok)
    except Exception as e:
        report("Initialize in memory mode", False, str(e))


# ──────────────────────────────────────────────
# Test 2: Cache set/get
# ──────────────────────────────────────────────
def test_cache_set_get():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            await rc.cache_set("scraper:mca21:CIN123", {"directors": ["A", "B"]}, ttl=300)
            result = await rc.cache_get("scraper:mca21:CIN123")
            await rc.close()
            return result

        result = asyncio.run(_run())
        ok = result is not None and result["directors"] == ["A", "B"]
        report("Cache set and get", ok)
    except Exception as e:
        report("Cache set and get", False, str(e))


# ──────────────────────────────────────────────
# Test 3: Cache TTL expiration
# ──────────────────────────────────────────────
def test_cache_ttl():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            # Set with 1-second TTL
            await rc.cache_set("ttl-test", "value", ttl=1)
            before = await rc.cache_get("ttl-test")

            # Wait for expiry
            await asyncio.sleep(1.1)
            after = await rc.cache_get("ttl-test")

            await rc.close()
            return before, after

        before, after = asyncio.run(_run())
        ok = before == "value" and after is None
        report("Cache TTL expiration", ok, f"before={before}, after={after}")
    except Exception as e:
        report("Cache TTL expiration", False, str(e))


# ──────────────────────────────────────────────
# Test 4: Cache delete
# ──────────────────────────────────────────────
def test_cache_delete():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            await rc.cache_set("del-test", "temp")
            before = await rc.cache_get("del-test")
            deleted = await rc.cache_delete("del-test")
            after = await rc.cache_get("del-test")
            await rc.close()
            return before, deleted, after

        before, deleted, after = asyncio.run(_run())
        ok = before == "temp" and deleted is True and after is None
        report("Cache delete", ok)
    except Exception as e:
        report("Cache delete", False, str(e))


# ──────────────────────────────────────────────
# Test 5: Cache exists
# ──────────────────────────────────────────────
def test_cache_exists():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            await rc.cache_set("exists-test", "yes")
            exists_yes = await rc.cache_exists("exists-test")
            exists_no = await rc.cache_exists("nope-doesnt-exist")
            await rc.close()
            return exists_yes, exists_no

        yes, no = asyncio.run(_run())
        ok = yes is True and no is False
        report("Cache exists", ok)
    except Exception as e:
        report("Cache exists", False, str(e))


# ──────────────────────────────────────────────
# Test 6: Stage worker output
# ──────────────────────────────────────────────
def test_stage_worker():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            sid = "staging-test-001"
            await rc.stage_worker_output(sid, "W1", {
                "worker_id": "W1",
                "document_type": "ANNUAL_REPORT",
                "revenue": 142_30_00_000,
            })
            await rc.stage_worker_output(sid, "W2", {
                "worker_id": "W2",
                "document_type": "BANK_STATEMENT",
                "monthly_inflows": [10, 12, 15],
            })

            w1 = await rc.get_staged_output(sid, "W1")
            count = await rc.get_staged_worker_count(sid)
            await rc.close()
            return w1, count

        w1, count = asyncio.run(_run())
        ok = w1 is not None and w1["worker_id"] == "W1" and count == 2
        report("Stage worker output", ok)
    except Exception as e:
        report("Stage worker output", False, str(e))


# ──────────────────────────────────────────────
# Test 7: Get all staged outputs
# ──────────────────────────────────────────────
def test_get_all_staged():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            sid = "staging-all-001"
            await rc.stage_worker_output(sid, "W1", {"data": "ar"})
            await rc.stage_worker_output(sid, "W3", {"data": "gst"})
            await rc.stage_worker_output(sid, "W4", {"data": "itr"})

            all_outputs = await rc.get_all_staged_outputs(sid)
            await rc.close()
            return all_outputs

        outputs = asyncio.run(_run())
        ok = (
            len(outputs) == 3
            and "W1" in outputs
            and "W3" in outputs
            and outputs["W3"]["data"] == "gst"
        )
        report("Get all staged outputs", ok, f"Got {len(outputs)} outputs")
    except Exception as e:
        report("Get all staged outputs", False, str(e))


# ──────────────────────────────────────────────
# Test 8: Clear staging
# ──────────────────────────────────────────────
def test_clear_staging():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            sid = "staging-clear-001"
            await rc.stage_worker_output(sid, "W1", {"data": "test"})
            count_before = await rc.get_staged_worker_count(sid)
            await rc.clear_staging(sid)
            count_after = await rc.get_staged_worker_count(sid)
            await rc.close()
            return count_before, count_after

        before, after = asyncio.run(_run())
        ok = before == 1 and after == 0
        report("Clear staging", ok)
    except Exception as e:
        report("Clear staging", False, str(e))


# ──────────────────────────────────────────────
# Test 9: Session state
# ──────────────────────────────────────────────
def test_session_state():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            state = {
                "session_id": "state-test-001",
                "current_stage": "RESEARCH",
                "score": None,
                "workers_completed": 5,
            }
            await rc.set_session_state("state-test-001", state)
            loaded = await rc.get_session_state("state-test-001")
            await rc.close()
            return loaded

        loaded = asyncio.run(_run())
        ok = (
            loaded is not None
            and loaded["session_id"] == "state-test-001"
            and loaded["current_stage"] == "RESEARCH"
            and loaded["workers_completed"] == 5
        )
        report("Session state save/load", ok)
    except Exception as e:
        report("Session state save/load", False, str(e))


# ──────────────────────────────────────────────
# Test 10: Namespace isolation
# ──────────────────────────────────────────────
def test_namespace_isolation():
    try:
        async def _run():
            rc = RedisClient()
            await rc.initialize()

            await rc.cache_set("same-key", "cache-value", namespace="cache")
            await rc.cache_set("same-key", "state-value", namespace="state")

            cache_val = await rc.cache_get("same-key", namespace="cache")
            state_val = await rc.cache_get("same-key", namespace="state")
            await rc.close()
            return cache_val, state_val

        cache_val, state_val = asyncio.run(_run())
        ok = cache_val == "cache-value" and state_val == "state-value"
        report("Namespace isolation", ok, f"cache={cache_val}, state={state_val}")
    except Exception as e:
        report("Namespace isolation", False, str(e))


# ──────────────────────────────────────────────
# Run all tests
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  T0.5 — Redis Client Tests")
    print("=" * 55 + "\n")

    test_init_memory()
    test_cache_set_get()
    test_cache_ttl()
    test_cache_delete()
    test_cache_exists()
    test_stage_worker()
    test_get_all_staged()
    test_clear_staging()
    test_session_state()
    test_namespace_isolation()

    print(f"\n{'=' * 55}")
    print(f"  Results: {PASSED} passed, {FAILED} failed, {PASSED + FAILED} total")
    print(f"{'=' * 55}\n")

    sys.exit(0 if FAILED == 0 else 1)
