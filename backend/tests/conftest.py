"""
Pytest configuration for PeerRing Backend tests
"""

import pytest
import asyncio
from typing import Generator

# Configure asyncio for pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_session_id() -> str:
    """Provide a standard test session ID."""
    return "test-session-12345"


@pytest.fixture
def mock_timestamp():
    """Provide a fixed timestamp for consistent testing."""
    from datetime import datetime
    return datetime(2026, 9, 14, 12, 30, 0)


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "contracts: mark test as contract validation"
    )


# Async test configuration
@pytest.fixture(scope="function")
async def mock_state():
    """Provide a clean PeerRingState for each test."""
    from app.state.pydantic_state import PeerRingState
    return PeerRingState(session_id="test-session-fixture")


@pytest.fixture
def mock_registry():
    """Provide a MockAgentRegistry instance."""
    from app.contracts.mock_registry import MockAgentRegistry
    return MockAgentRegistry()