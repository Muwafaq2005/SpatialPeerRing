"""
Test Suite for Redis Turn Mutex System
Tests Redis integration, turn locking, and state persistence
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.state.redis_mutex import (
    RedisTurnMutex,
    RedisConnectionError,
    TurnLockTimeoutError
)
from app.state.pydantic_state import (
    PeerRingState,
    DialogueMessage,
    MessageRole,
    TurnLockStatus
)


class TestRedisTurnMutex:
    """Test Redis turn mutex functionality."""

    @pytest.fixture
    async def redis_mutex(self):
        """Create RedisTurnMutex instance for testing."""
        mutex = RedisTurnMutex()

        # Mock Redis client for testing
        mock_redis = AsyncMock()
        mutex.redis_client = mock_redis
        mutex._connected = True

        return mutex, mock_redis

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test successful Redis connection."""
        mutex = RedisTurnMutex()

        with patch('app.state.redis_mutex.redis') as mock_redis_module:
            mock_pool = AsyncMock()
            mock_client = AsyncMock()

            mock_redis_module.ConnectionPool.from_url.return_value = mock_pool
            mock_redis_module.Redis.return_value = mock_client
            mock_client.ping.return_value = True

            await mutex.connect()

            assert mutex._connected is True
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test Redis connection failure handling."""
        mutex = RedisTurnMutex()

        with patch('app.state.redis_mutex.redis') as mock_redis_module:
            mock_redis_module.ConnectionPool.from_url.side_effect = Exception("Connection failed")

            with pytest.raises(RedisConnectionError):
                await mutex.connect()

            assert mutex._connected is False

    @pytest.mark.asyncio
    async def test_acquire_turn_lock_success(self, redis_mutex):
        """Test successful turn lock acquisition."""
        mutex, mock_redis = redis_mutex

        # Mock successful SETNX
        mock_redis.set.return_value = True

        result = await mutex.acquire_turn_lock("test-session", "owner-123")

        assert result is True
        mock_redis.set.assert_called_once()

        # Verify SET call with correct parameters
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "peerring:turn_lock:test-session"
        assert call_args[1]['nx'] is True  # Only set if not exists
        assert call_args[1]['ex'] == 30    # TTL from settings

    @pytest.mark.asyncio
    async def test_acquire_turn_lock_already_locked(self, redis_mutex):
        """Test turn lock acquisition when already locked."""
        mutex, mock_redis = redis_mutex

        # Mock failed SETNX (key already exists)
        mock_redis.set.return_value = False
        mock_redis.get.return_value = json.dumps({
            "owner": "other-owner",
            "acquired_at": datetime.utcnow().isoformat(),
            "session_id": "test-session"
        })

        result = await mutex.acquire_turn_lock("test-session", "owner-123")

        assert result is False
        mock_redis.set.assert_called_once()
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_turn_lock_success(self, redis_mutex):
        """Test successful turn lock release."""
        mutex, mock_redis = redis_mutex

        # Mock successful ownership verification and deletion
        mock_redis.eval.return_value = 1  # Lock deleted

        result = await mutex.release_turn_lock("test-session", "owner-123")

        assert result is True
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_turn_lock_not_owner(self, redis_mutex):
        """Test turn lock release by non-owner."""
        mutex, mock_redis = redis_mutex

        # Mock failed ownership verification
        mock_redis.eval.return_value = 0  # Not owner or already released

        result = await mutex.release_turn_lock("test-session", "wrong-owner")

        assert result is False
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_lock_status_locked(self, redis_mutex):
        """Test getting lock status when session is locked."""
        mutex, mock_redis = redis_mutex

        acquired_time = datetime.utcnow()
        lock_data = {
            "owner": "owner-123",
            "acquired_at": acquired_time.isoformat(),
            "session_id": "test-session"
        }

        mock_redis.get.return_value = json.dumps(lock_data)
        mock_redis.ttl.return_value = 25  # 25 seconds remaining

        status = await mutex.get_lock_status("test-session")

        assert status.locked is True
        assert status.lock_owner == "owner-123"
        assert status.lock_ttl_seconds == 25
        assert isinstance(status.lock_acquired_at, datetime)

    @pytest.mark.asyncio
    async def test_get_lock_status_unlocked(self, redis_mutex):
        """Test getting lock status when session is not locked."""
        mutex, mock_redis = redis_mutex

        mock_redis.get.return_value = None  # No lock exists

        status = await mutex.get_lock_status("test-session")

        assert status.locked is False
        assert status.lock_owner is None
        assert status.lock_acquired_at is None

    @pytest.mark.asyncio
    async def test_save_state_success(self, redis_mutex):
        """Test successful state persistence to Redis."""
        mutex, mock_redis = redis_mutex

        # Create test state
        state = PeerRingState(session_id="test-session")
        state.add_message(DialogueMessage(
            role=MessageRole.USER,
            content="Test message"
        ))

        mock_redis.setex.return_value = True

        await mutex.save_state(state)

        mock_redis.setex.assert_called_once()

        # Verify call parameters
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "peerring:state:test-session"
        assert call_args[0][1] == 24 * 60 * 60  # 24 hour TTL

        # Verify JSON serialization
        saved_json = call_args[0][2]
        parsed_state = json.loads(saved_json)
        assert parsed_state["session_id"] == "test-session"
        assert len(parsed_state["messages"]) == 1

    @pytest.mark.asyncio
    async def test_load_state_success(self, redis_mutex):
        """Test successful state loading from Redis."""
        mutex, mock_redis = redis_mutex

        # Create test state data
        state = PeerRingState(session_id="test-session")
        state.add_message(DialogueMessage(
            role=MessageRole.USER,
            content="Test message"
        ))

        state_json = json.dumps(state.model_dump(), default=str)
        mock_redis.get.return_value = state_json

        loaded_state = await mutex.load_state("test-session")

        assert loaded_state is not None
        assert loaded_state.session_id == "test-session"
        assert len(loaded_state.messages) == 1
        assert loaded_state.messages[0].content == "Test message"

        mock_redis.get.assert_called_once_with("peerring:state:test-session")

    @pytest.mark.asyncio
    async def test_load_state_not_found(self, redis_mutex):
        """Test state loading when state doesn't exist."""
        mutex, mock_redis = redis_mutex

        mock_redis.get.return_value = None

        loaded_state = await mutex.load_state("nonexistent-session")

        assert loaded_state is None
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_success(self, redis_mutex):
        """Test successful session deletion."""
        mutex, mock_redis = redis_mutex

        mock_redis.delete.return_value = 2  # Both state and lock deleted

        result = await mutex.delete_session("test-session")

        assert result is True
        mock_redis.delete.assert_called_once_with(
            "peerring:state:test-session",
            "peerring:turn_lock:test-session"
        )

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, redis_mutex):
        """Test session deletion when session doesn't exist."""
        mutex, mock_redis = redis_mutex

        mock_redis.delete.return_value = 0  # Nothing deleted

        result = await mutex.delete_session("nonexistent-session")

        assert result is False
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, redis_mutex):
        """Test cleanup of orphaned locks."""
        mutex, mock_redis = redis_mutex

        # Mock keys returns
        mock_redis.keys.side_effect = [
            ["peerring:state:session1", "peerring:state:session2"],  # State keys
            ["peerring:turn_lock:session1", "peerring:turn_lock:session3"]  # Lock keys
        ]

        # Mock exists check - session3 has lock but no state (orphaned)
        def mock_exists(key):
            if key == "peerring:state:session3":
                return False  # No state for session3
            return True

        mock_redis.exists.side_effect = mock_exists
        mock_redis.delete.return_value = 1

        cleaned_count = await mutex.cleanup_expired_sessions()

        assert cleaned_count == 1  # One orphaned lock cleaned
        mock_redis.delete.assert_called_once_with("peerring:turn_lock:session3")

    @pytest.mark.asyncio
    async def test_health_check_success(self, redis_mutex):
        """Test Redis health check when healthy."""
        mutex, mock_redis = redis_mutex

        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.2M",
            "redis_version": "7.2.0",
            "db0": {"keys": 10, "expires": 2}
        }

        health = await mutex.health_check()

        assert health["connected"] is True
        assert health["status"] == "healthy"
        assert "ping_ms" in health
        assert health["redis_version"] == "7.2.0"
        assert health["connected_clients"] == 5

    @pytest.mark.asyncio
    async def test_health_check_disconnected(self):
        """Test health check when Redis is disconnected."""
        mutex = RedisTurnMutex()
        mutex._connected = False

        health = await mutex.health_check()

        assert health["connected"] is False
        assert health["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, redis_mutex):
        """Test that Redis connection errors are properly handled."""
        mutex, mock_redis = redis_mutex

        # Simulate Redis connection error
        mock_redis.set.side_effect = Exception("Redis connection lost")

        with pytest.raises(RedisConnectionError):
            await mutex.acquire_turn_lock("test-session", "owner-123")

    def test_key_generation(self):
        """Test Redis key generation methods."""
        mutex = RedisTurnMutex()

        lock_key = mutex._get_lock_key("test-session")
        state_key = mutex._get_state_key("test-session")

        assert lock_key == "peerring:turn_lock:test-session"
        assert state_key == "peerring:state:test-session"

    @pytest.mark.asyncio
    async def test_concurrent_lock_acquisition(self, redis_mutex):
        """Test behavior under concurrent lock acquisition attempts."""
        mutex, mock_redis = redis_mutex

        # First call succeeds, second fails
        mock_redis.set.side_effect = [True, False]
        mock_redis.get.return_value = json.dumps({
            "owner": "owner-1",
            "acquired_at": datetime.utcnow().isoformat(),
            "session_id": "test-session"
        })

        # Simulate concurrent attempts
        result1 = await mutex.acquire_turn_lock("test-session", "owner-1")
        result2 = await mutex.acquire_turn_lock("test-session", "owner-2")

        assert result1 is True   # First succeeds
        assert result2 is False  # Second fails
        assert mock_redis.set.call_count == 2


class TestRedisIntegration:
    """Integration tests for Redis mutex with WebSocket coordination."""

    @pytest.mark.asyncio
    async def test_complete_turn_flow(self):
        """Test complete turn flow: acquire lock -> process -> save state -> release lock."""

        # This would be an integration test with actual Redis
        # For now, we'll test the flow with mocks

        mutex = RedisTurnMutex()
        mock_redis = AsyncMock()
        mutex.redis_client = mock_redis
        mutex._connected = True

        # Mock successful flow
        mock_redis.set.return_value = True      # Lock acquired
        mock_redis.setex.return_value = True    # State saved
        mock_redis.eval.return_value = 1        # Lock released

        session_id = "integration-test-session"
        owner_id = "ws-connection-123"

        # Step 1: Acquire lock
        lock_acquired = await mutex.acquire_turn_lock(session_id, owner_id)
        assert lock_acquired is True

        # Step 2: Save state (simulating agent processing)
        state = PeerRingState(session_id=session_id)
        state.add_message(DialogueMessage(
            role=MessageRole.USER,
            content="Integration test message"
        ))
        await mutex.save_state(state)

        # Step 3: Release lock
        lock_released = await mutex.release_turn_lock(session_id, owner_id)
        assert lock_released is True

        # Verify all operations were called
        assert mock_redis.set.called
        assert mock_redis.setex.called
        assert mock_redis.eval.called

    @pytest.mark.asyncio
    async def test_lock_timeout_handling(self, redis_mutex):
        """Test automatic lock timeout via Redis TTL."""
        mutex, mock_redis = redis_mutex

        # Simulate lock expiration
        mock_redis.get.side_effect = [
            json.dumps({  # Lock exists initially
                "owner": "expired-owner",
                "acquired_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                "session_id": "test-session"
            }),
            None  # Lock expired and removed by Redis TTL
        ]
        mock_redis.ttl.side_effect = [0, -2]  # TTL expired

        # First check shows expired lock
        status1 = await mutex.get_lock_status("test-session")
        assert status1.locked is True
        assert status1.lock_ttl_seconds == 0

        # Second check shows lock is gone
        status2 = await mutex.get_lock_status("test-session")
        assert status2.locked is False

    def test_redis_mutex_singleton_pattern(self):
        """Test that redis_mutex is properly configured as singleton."""
        from app.state.redis_mutex import redis_mutex

        assert isinstance(redis_mutex, RedisTurnMutex)
        assert redis_mutex._connected is False  # Initially not connected