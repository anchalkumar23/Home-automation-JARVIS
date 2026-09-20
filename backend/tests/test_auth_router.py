import time

from app.routers import auth as auth_router


def test_rate_limited_allows_attempts_under_the_limit():
    auth_router._login_attempts.clear()
    ip = "1.2.3.4"
    for _ in range(4):
        assert auth_router._rate_limited(ip) is False
        auth_router._login_attempts[ip].append(time.time())


def test_rate_limited_blocks_after_five_attempts():
    auth_router._login_attempts.clear()
    ip = "1.2.3.4"
    auth_router._login_attempts[ip] = [time.time()] * 5

    assert auth_router._rate_limited(ip) is True


def test_rate_limited_resets_after_the_window_passes():
    auth_router._login_attempts.clear()
    ip = "1.2.3.4"
    old_timestamp = time.time() - auth_router._RATE_LIMIT_WINDOW_SECONDS - 1
    auth_router._login_attempts[ip] = [old_timestamp] * 5

    assert auth_router._rate_limited(ip) is False
