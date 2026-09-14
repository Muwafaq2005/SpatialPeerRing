"""
Redis Turn Mutex Implementation
Provides SETNX-based turn locking for WebSocket coordination
"""

import redis.asyncio as redis
from redis.retry import Retry
from redis.backoff import ExponentialBackoff
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import uuid

from app.config import settings
from app.state.pydantic_state import PeerRingState, TurnLockStatus

logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Redis connection related errors."""
    pass


class TurnLockTimeoutError(Exception):
    """Turn lock acquisition timeout."""
    pass


class RedisTurnMutex:
    """
    Redis-based turn mutex system using SETNX for atomic locking.

    Provides:
    - Atomic turn lock acquisition/release
    - State persistence with JSON serialization
    - Session TTL management
    - Performance optimized for <100ms operations
    """

    def __init__(self):
        """Initialize Redis turn mutex system."""
        self.redis_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        self._connected = False

    async def connect(self) -> None:
        """
        Establish Redis connection with connection pooling.

        Raises:
            RedisConnectionError: If connection fails
        """
        try:
            # Create connection pool for better performance
            self.connection_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )

            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                decode_responses=True,
                retry_on_error=[redis.BusyLoadingError, redis.ConnectionError],
                retry=Retry(ExponentialBackoff(), 3)
            )

            # Test connection
            await self.redis_client.ping()
            self._connected = True

            logger.info("✅ Redis connection established successfully")

        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")

    async def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        if self.redis_client:
            await self.redis_client.aclose()
        if self.connection_pool:
            await self.connection_pool.disconnect()

        self._connected = False
        logger.info("🔌 Redis connection closed")

    def _get_lock_key(self, session_id: str) -> str:
        """Generate Redis key for turn lock."""
        return f"peerring:turn_lock:{session_id}"

    def _get_state_key(self, session_id: str) -> str:
        """Generate Redis key for session state."""
        return f"peerring:state:{session_id}"

    async def acquire_turn_lock(
        self,
        session_id: str,
        owner_id: str,
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Acquire exclusive turn lock using Redis SETNX.

        Args:
            session_id: Session identifier
            owner_id: Lock owner identifier (usually WebSocket connection ID)
            ttl_seconds: Lock TTL in seconds (defaults to config value)

        Returns:
            True if lock acquired, False if already locked

        Raises:
            RedisConnectionError: If Redis connection fails
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        lock_key = self._get_lock_key(session_id)
        ttl = ttl_seconds or settings.REDIS_TURN_LOCK_TTL

        lock_data = {
            "owner": owner_id,
            "acquired_at": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "lock_id": str(uuid.uuid4())
        }

        try:
            # Use SET with NX (only set if not exists) and EX (expire) options
            # This is atomic and equivalent to SETNX + EXPIRE
            result = await self.redis_client.set(
                lock_key,
                json.dumps(lock_data),
                nx=True,  # Only set if key doesn't exist
                ex=ttl    # Set expiration time
            )

            if result:
                logger.info(f"🔒 Turn lock acquired: session={session_id}, owner={owner_id}")
                return True
            else:
                # Lock already exists, get current lock info for logging
                current_lock = await self.redis_client.get(lock_key)
                if current_lock:
                    current_data = json.loads(current_lock)
                    logger.debug(f"🚫 Turn lock blocked: session={session_id}, current_owner={current_data.get('owner')}")
                return False

        except Exception as e:
            logger.error(f"❌ Turn lock acquisition failed: session={session_id}, error={e}")
            raise RedisConnectionError(f"Lock acquisition failed: {e}")

    async def release_turn_lock(self, session_id: str, owner_id: str) -> bool:
        """
        Release turn lock with ownership verification.

        Args:
            session_id: Session identifier
            owner_id: Lock owner identifier (must match current owner)

        Returns:
            True if lock released, False if not owned by caller

        Raises:
            RedisConnectionError: If Redis connection fails
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        lock_key = self._get_lock_key(session_id)

        try:
            # Lua script for atomic check-and-delete
            # This prevents race conditions where lock expires between check and delete
            lua_script = """
            local current = redis.call('GET', KEYS[1])
            if current then
                local data = cjson.decode(current)
                if data.owner == ARGV[1] then
                    return redis.call('DEL', KEYS[1])
                else
                    return 0
                end
            else
                return 0
            end
            """

            result = await self.redis_client.eval(lua_script, 1, lock_key, owner_id)

            if result == 1:
                logger.info(f"🔓 Turn lock released: session={session_id}, owner={owner_id}")
                return True
            else:
                logger.warning(f"🚫 Turn lock release failed: session={session_id}, owner={owner_id} (not owner or already released)")
                return False

        except Exception as e:
            logger.error(f"❌ Turn lock release failed: session={session_id}, error={e}")
            raise RedisConnectionError(f"Lock release failed: {e}")

    async def get_lock_status(self, session_id: str) -> TurnLockStatus:
        """
        Get current turn lock status for a session.

        Args:
            session_id: Session identifier

        Returns:
            TurnLockStatus with current lock state
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        lock_key = self._get_lock_key(session_id)

        try:
            lock_data_str = await self.redis_client.get(lock_key)

            if not lock_data_str:
                return TurnLockStatus(
                    locked=False,
                    lock_owner=None,
                    lock_acquired_at=None,
                    lock_ttl_seconds=settings.REDIS_TURN_LOCK_TTL
                )

            lock_data = json.loads(lock_data_str)
            acquired_at = datetime.fromisoformat(lock_data["acquired_at"])

            # Get remaining TTL
            ttl = await self.redis_client.ttl(lock_key)
            ttl_seconds = ttl if ttl > 0 else 0

            return TurnLockStatus(
                locked=True,
                lock_owner=lock_data["owner"],
                lock_acquired_at=acquired_at,
                lock_ttl_seconds=ttl_seconds
            )

        except Exception as e:
            logger.error(f"❌ Lock status check failed: session={session_id}, error={e}")
            # Return safe default
            return TurnLockStatus(locked=False)

    async def save_state(self, state: PeerRingState) -> None:
        """
        Persist PeerRingState to Redis with JSON serialization.

        Args:
            state: PeerRingState to persist

        Raises:
            RedisConnectionError: If Redis operation fails
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        state_key = self._get_state_key(state.session_id)

        try:
            # Update last_updated timestamp
            state.last_updated = datetime.utcnow()

            # Serialize to JSON
            state_dict = state.model_dump()
            state_json = json.dumps(state_dict, default=str, ensure_ascii=False)

            # Set state with TTL (24 hours default)
            session_ttl = 24 * 60 * 60  # 24 hours
            await self.redis_client.setex(state_key, session_ttl, state_json)

            logger.debug(f"💾 State saved: session={state.session_id}, size={len(state_json)} bytes")

        except Exception as e:
            logger.error(f"❌ State save failed: session={state.session_id}, error={e}")
            raise RedisConnectionError(f"State save failed: {e}")

    async def load_state(self, session_id: str) -> Optional[PeerRingState]:
        """
        Load PeerRingState from Redis.

        Args:
            session_id: Session identifier

        Returns:
            PeerRingState if found, None if not exists

        Raises:
            RedisConnectionError: If Redis operation fails
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        state_key = self._get_state_key(session_id)

        try:
            state_json = await self.redis_client.get(state_key)

            if not state_json:
                logger.debug(f"📭 No state found: session={session_id}")
                return None

            # Deserialize from JSON
            state_dict = json.loads(state_json)
            state = PeerRingState.model_validate(state_dict)

            logger.debug(f"📂 State loaded: session={session_id}, messages={len(state.messages)}")
            return state

        except Exception as e:
            logger.error(f"❌ State load failed: session={session_id}, error={e}")
            raise RedisConnectionError(f"State load failed: {e}")

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete session state and release any locks.

        Args:
            session_id: Session identifier

        Returns:
            True if session deleted, False if not found
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        state_key = self._get_state_key(session_id)
        lock_key = self._get_lock_key(session_id)

        try:
            # Delete both state and lock atomically
            deleted_count = await self.redis_client.delete(state_key, lock_key)

            if deleted_count > 0:
                logger.info(f"🗑️ Session deleted: session={session_id}")
                return True
            else:
                logger.debug(f"🤷 Session not found: session={session_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Session deletion failed: session={session_id}, error={e}")
            raise RedisConnectionError(f"Session deletion failed: {e}")

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions and orphaned locks.

        Returns:
            Number of sessions cleaned up
        """
        if not self._connected:
            raise RedisConnectionError("Redis not connected")

        try:
            # Find all session keys
            state_pattern = "peerring:state:*"
            lock_pattern = "peerring:turn_lock:*"

            state_keys = await self.redis_client.keys(state_pattern)
            lock_keys = await self.redis_client.keys(lock_pattern)

            cleaned_count = 0

            # Check for orphaned locks (locks without corresponding state)
            for lock_key in lock_keys:
                session_id = lock_key.split(":")[-1]  # Extract session ID
                state_key = self._get_state_key(session_id)

                state_exists = await self.redis_client.exists(state_key)
                if not state_exists:
                    await self.redis_client.delete(lock_key)
                    cleaned_count += 1
                    logger.info(f"🧹 Cleaned orphaned lock: {lock_key}")

            logger.info(f"🧹 Cleanup complete: {cleaned_count} orphaned locks removed")
            return cleaned_count

        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return 0

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform Redis health check for monitoring.

        Returns:
            Dictionary with health status and metrics
        """
        health_data = {
            "connected": self._connected,
            "redis_url": settings.REDIS_URL,
            "timestamp": datetime.utcnow().isoformat()
        }

        if not self._connected:
            health_data["status"] = "disconnected"
            return health_data

        try:
            # Test basic operations
            start_time = datetime.utcnow()

            # Ping test
            await self.redis_client.ping()
            ping_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Get Redis info
            info = await self.redis_client.info()

            health_data.update({
                "status": "healthy",
                "ping_ms": round(ping_time, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown"),
                "keyspace": info.get("db0", {})
            })

            return health_data

        except Exception as e:
            health_data.update({
                "status": "error",
                "error": str(e)
            })
            return health_data


# Global Redis mutex instance
redis_mutex = RedisTurnMutex()