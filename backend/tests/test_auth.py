from app.services.auth import hash_password, verify_password


def test_verify_password_accepts_correct_password():
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored) is True


def test_verify_password_rejects_wrong_password():
    stored = hash_password("correct horse battery staple")
    assert verify_password("wrong password", stored) is False


def test_verify_password_rejects_empty_stored_hash():
    assert verify_password("anything", "") is False


def test_verify_password_rejects_malformed_stored_hash():
    assert verify_password("anything", "not-a-valid-hash") is False


def test_hash_password_uses_a_random_salt_each_time():
    first = hash_password("same password")
    second = hash_password("same password")
    assert first != second
    assert verify_password("same password", first) is True
    assert verify_password("same password", second) is True
