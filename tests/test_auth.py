import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4, UUID
import pytest
from httpx import AsyncClient, ASGITransport
from src.auth.password import verify_password, get_password_hash, validate_password_strength
from src.auth.jwt import create_access_token, create_refresh_token, verify_token
from src.auth.service import (
    create_user,
    authenticate_user,
    store_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    get_user_by_id,
)
from src.database.models import hash_email
from src.database.connection import Database
import asyncpg


@pytest.fixture(scope="function")
async def db_connection():
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        yield conn


@pytest.fixture(scope="function")
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def test_user_data():
    return {
        "email": f"test_{uuid4().hex[:8]}@example.com",
        "password": "TestPass123!",
        "name": "Test User"
    }


class TestPasswordUtilities:
    def test_verify_password_correct(self):
        password = "TestPass123!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        password = "TestPass123!"
        hashed = get_password_hash(password)
        assert verify_password("WrongPass123!", hashed) is False
    
    def test_password_hashing_different_hashes(self):
        password = "TestPass123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2
    
    @pytest.mark.parametrize("password,expected_valid", [
        ("Short1!", False),
        ("nouppercase123!", False),
        ("NOLOWERCASE123!", False),
        ("NoNumbers!", False),
        ("NoSpecial123", False),
        ("ValidPass123!", True),
        ("Another1@Valid", True),
    ])
    def test_validate_password_strength(self, password, expected_valid):
        is_valid, _ = validate_password_strength(password)
        assert is_valid == expected_valid


class TestJWTUtilities:
    def test_create_access_token(self):
        data = {"sub": "user-123", "jti": "jti-123"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_refresh_token(self):
        data = {"sub": "user-123"}
        token = create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_access_token_valid(self):
        data = {"sub": "user-123", "jti": "jti-123"}
        token = create_access_token(data)
        payload = verify_token(token, "access")
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"
    
    def test_verify_refresh_token_valid(self):
        data = {"sub": "user-123"}
        token = create_refresh_token(data)
        payload = verify_token(token, "refresh")
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["type"] == "refresh"
    
    def test_verify_token_wrong_type(self):
        data = {"sub": "user-123"}
        token = create_refresh_token(data)
        payload = verify_token(token, "access")
        assert payload is None
    
    def test_verify_token_invalid(self):
        invalid_token = "invalid.token.here"
        payload = verify_token(invalid_token)
        assert payload is None


class TestEmailHashing:
    def test_hash_email_consistent(self):
        email = "test@example.com"
        hash1 = hash_email(email)
        hash2 = hash_email(email)
        assert hash1 == hash2
    
    def test_hash_email_case_insensitive(self):
        hash1 = hash_email("Test@Example.com")
        hash2 = hash_email("test@example.com")
        assert hash1 == hash2
    
    def test_hash_email_different_emails(self):
        hash1 = hash_email("test1@example.com")
        hash2 = hash_email("test2@example.com")
        assert hash1 != hash2


class TestAuthService:
    @pytest.mark.asyncio
    async def test_create_user_success(self, db_connection, test_user_data):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        assert user["email"] == test_user_data["email"].lower()
        assert user["name"] == test_user_data["name"]
        assert user["is_verified"] is False
        assert "id" in user
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, db_connection, test_user_data):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        with pytest.raises(ValueError, match="Email already registered"):
            await create_user(
                db_connection,
                test_user_data["email"],
                test_user_data["password"],
                test_user_data["name"]
            )
    
    @pytest.mark.asyncio
    async def test_create_user_weak_password(self, db_connection, test_user_data):
        with pytest.raises(ValueError):
            await create_user(
                db_connection,
                test_user_data["email"],
                "weak",
                test_user_data["name"]
            )
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, db_connection, test_user_data):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        user = await authenticate_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"]
        )
        
        assert user is not None
        assert user["email"] == test_user_data["email"].lower()
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, db_connection, test_user_data):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        user = await authenticate_user(
            db_connection,
            test_user_data["email"],
            "WrongPassword123!"
        )
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent(self, db_connection):
        user = await authenticate_user(
            db_connection,
            "nonexistent@example.com",
            "SomePass123!"
        )
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_store_refresh_token(self, db_connection, test_user_data):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        token_hash = await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        
        assert token_hash is not None
        
        record = await db_connection.fetchrow(
            "SELECT token_hash FROM refresh_tokens WHERE token_hash = $1",
            token_hash
        )
        
        assert record is not None
    
    @pytest.mark.asyncio
    async def test_verify_refresh_token_valid(self, db_connection, test_user_data):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        
        token_data = await verify_refresh_token(db_connection, refresh_token)
        
        assert token_data is not None
        assert token_data["user_id"] == user["id"]
    
    @pytest.mark.asyncio
    async def test_verify_refresh_token_revoked(self, db_connection, test_user_data):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        await revoke_refresh_token(db_connection, refresh_token)
        
        token_data = await verify_refresh_token(db_connection, refresh_token)
        
        assert token_data is None
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_exists(self, db_connection, test_user_data):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        found_user = await get_user_by_id(db_connection, UUID(user["id"]))
        
        assert found_user is not None
        assert found_user["email"] == test_user_data["email"].lower()
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_nonexistent(self, db_connection):
        fake_id = UUID("00000000-0000-0000-0000-000000000000")
        found_user = await get_user_by_id(db_connection, fake_id)
        
        assert found_user is None


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_signup_success(self, client, test_user_data):
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == test_user_data["email"].lower()
    
    @pytest.mark.asyncio
    async def test_signup_duplicate_email(self, client, test_user_data):
        await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_signup_weak_password(self, client, test_user_data):
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": "weak",
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_signup_invalid_email(self, client, test_user_data):
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": "invalid-email",
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, test_user_data, db_connection):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, test_user_data, db_connection):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": "WrongPassword123!"
            }
        )
        
        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePass123!"
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client):
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_refresh_token_revoked(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        await revoke_refresh_token(db_connection, refresh_token)
        
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_logout_success(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        access_token = create_access_token({"sub": user["id"]})
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 204
        
        token_data = await verify_refresh_token(db_connection, refresh_token)
        assert token_data is None
    
    @pytest.mark.asyncio
    async def test_logout_without_auth(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token)
        
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_logout_all_success(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        refresh_token1 = create_refresh_token({"sub": user["id"]})
        refresh_token2 = create_refresh_token({"sub": user["id"]})
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token1)
        await store_refresh_token(db_connection, UUID(user["id"]), refresh_token2)
        
        access_token = create_access_token({"sub": user["id"]})
        
        response = await client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 204
        
        token_data1 = await verify_refresh_token(db_connection, refresh_token1)
        token_data2 = await verify_refresh_token(db_connection, refresh_token2)
        assert token_data1 is None
        assert token_data2 is None
    
    @pytest.mark.asyncio
    async def test_get_me_success(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        access_token = create_access_token({"sub": user["id"]})
        
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"].lower()
        assert data["id"] == user["id"]
    
    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client):
        response = await client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )
        
        assert response.status_code == 401


class TestAuthSecurity:
    @pytest.mark.asyncio
    async def test_token_expiration(self, client, test_user_data, db_connection):
        from src.config import config
        from unittest.mock import patch
        
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        with patch.object(config, "jwt_access_token_expire_minutes", 0):
            access_token = create_access_token({"sub": user["id"]})
            
            await asyncio.sleep(1)
            
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_password_not_in_response(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        access_token = create_access_token({"sub": user["id"]})
        
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        data = response.json()
        assert "password" not in data
        assert "password_hash" not in data
    
    @pytest.mark.asyncio
    async def test_email_case_insensitive_login(self, client, test_user_data, db_connection):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"].upper(),
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_email_case_insensitive_signup(self, client, test_user_data):
        response1 = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response1.status_code == 201
        
        response2 = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"].upper(),
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response2.status_code == 400


class TestAuthIntegration:
    @pytest.mark.asyncio
    async def test_full_auth_flow(self, client, test_user_data, db_connection):
        signup_response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert signup_response.status_code == 201
        signup_data = signup_response.json()
        access_token = signup_data["access_token"]
        refresh_token = signup_data["refresh_token"]
        
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        assert me_response.status_code == 200
        assert me_response.json()["email"] == test_user_data["email"].lower()
        
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["access_token"]
        
        me_response2 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"}
        )
        
        assert me_response2.status_code == 200
        
        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {new_access_token}"}
        )
        
        assert logout_response.status_code == 204
    
    @pytest.mark.asyncio
    async def test_multiple_sessions(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        login1 = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        login2 = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert login1.status_code == 200
        assert login2.status_code == 200
        
        token1 = login1.json()["access_token"]
        token2 = login2.json()["access_token"]
        
        assert token1 != token2
        
        me1 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token1}"}
        )
        
        me2 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token2}"}
        )
        
        assert me1.status_code == 200
        assert me2.status_code == 200
        assert me1.json()["id"] == me2.json()["id"]


class TestAuthEdgeCases:
    @pytest.mark.asyncio
    async def test_signup_empty_name(self, client, test_user_data):
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        
        assert response.status_code == 201
        assert response.json()["user"]["name"] is None
    
    @pytest.mark.asyncio
    async def test_signup_very_long_email(self, client, test_user_data):
        long_email = "a" * 200 + "@example.com"
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": long_email,
                "password": test_user_data["password"],
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code in [201, 400, 422]
    
    @pytest.mark.asyncio
    async def test_signup_very_long_password(self, client, test_user_data):
        long_password = "A" * 1000 + "1!"
        response = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": test_user_data["email"],
                "password": long_password,
                "name": test_user_data["name"]
            }
        )
        
        assert response.status_code in [201, 400]
    
    @pytest.mark.asyncio
    async def test_login_empty_password(self, client, test_user_data, db_connection):
        await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user_data["email"],
                "password": ""
            }
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_refresh_with_access_token(self, client, test_user_data, db_connection):
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        access_token = create_access_token({"sub": user["id"]})
        
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token}
        )
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_get_me_expired_token(self, client, test_user_data, db_connection):
        from src.config import config
        from unittest.mock import patch
        
        user = await create_user(
            db_connection,
            test_user_data["email"],
            test_user_data["password"],
            test_user_data["name"]
        )
        
        with patch.object(config, "jwt_access_token_expire_minutes", -1):
            expired_token = create_access_token({"sub": user["id"]})
            
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"}
            )
            
            assert response.status_code == 401
