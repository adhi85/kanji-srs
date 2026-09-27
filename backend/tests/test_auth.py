import time
import pytest
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.models import User
from fastapi import HTTPException


def test_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_decode_token(db):
    user = User(username="testuser", password_hash=hash_password("pw"), created_at=time.time())
    db.add(user)
    db.commit()
    token = create_access_token(user.id, user.username)
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3


def test_get_current_user_valid_token(db):
    user = User(username="testuser", password_hash=hash_password("pw"), created_at=time.time())
    db.add(user)
    db.commit()
    token = create_access_token(user.id, user.username)
    result = get_current_user(token=token, db=db)
    assert result.id == user.id
    assert result.username == "testuser"


def test_get_current_user_invalid_token(db):
    with pytest.raises(HTTPException) as exc:
        get_current_user(token="invalid.token.here", db=db)
    assert exc.value.status_code == 401


def test_get_current_user_nonexistent_user(db):
    token = create_access_token(9999, "ghost")
    with pytest.raises(HTTPException) as exc:
        get_current_user(token=token, db=db)
    assert exc.value.status_code == 401
