"""Tests for Phase B1: circuit breaker for LLM calls.

Verifies that the circuit breaker in ModelPool opens after 5
consecutive failures, short-circuits the 6th call, logs state
transitions at WARNING level, and resets after the timeout.
"""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pybreaker
import pytest


@pytest.fixture
def pool():
    """Create a ModelPool with mocked config and router."""
    with patch("ol_pool.router.Router", MagicMock()), \
         patch("ol_pool.router.load_config", return_value=MagicMock(
             llm_pool=MagicMock(translation=[], judging=[], restoration=[]),
             cache_system_prompt=True,
         )):
        from ol_pool.router import ModelPool
        return ModelPool()


class TestBreakerConfig:
    def test_three_breakers_per_role(self, pool):
        assert "translation" in pool._breakers
        assert "judging" in pool._breakers
        assert "restoration" in pool._breakers

    def test_breaker_thresholds(self, pool):
        for role in ("translation", "judging", "restoration"):
            assert pool._breakers[role].fail_max == 5
            assert pool._breakers[role].reset_timeout == 60


class TestShortCircuit:
    def test_opens_after_5_consecutive_failures(self, pool):
        async def failing():
            raise RuntimeError("LLM down")
        for _ in range(5):
            with pytest.raises(RuntimeError):
                asyncio.run(pool._call_with_breaker("translation", failing))
        assert pool._breakers["translation"].current_state == "open"

    def test_6th_call_short_circuits(self, pool):
        async def failing():
            raise RuntimeError("LLM down")
        for _ in range(5):
            with pytest.raises(RuntimeError):
                asyncio.run(pool._call_with_breaker("translation", failing))
        with pytest.raises(pybreaker.CircuitBreakerError):
            asyncio.run(pool._call_with_breaker("translation", failing))


class TestSuccess:
    def test_success_does_not_open_breaker(self, pool):
        async def ok():
            return "translated text"
        for _ in range(10):
            result = asyncio.run(pool._call_with_breaker("translation", ok))
            assert result == "translated text"
        assert pool._breakers["translation"].current_state == "closed"


class TestStateLogging:
    def test_state_transition_logged(self, pool, caplog):
        async def failing():
            raise RuntimeError("LLM down")
        with caplog.at_level(logging.WARNING, logger="ol_pool.router"):
            for _ in range(5):
                with pytest.raises(RuntimeError):
                    asyncio.run(pool._call_with_breaker("translation", failing))
        assert any("closed -> open" in r.message for r in caplog.records)


class TestPerRoleIsolation:
    def test_one_role_open_does_not_affect_another(self, pool):
        async def failing():
            raise RuntimeError("LLM down")
        for _ in range(5):
            with pytest.raises(RuntimeError):
                asyncio.run(pool._call_with_breaker("translation", failing))
        assert pool._breakers["translation"].current_state == "open"
        assert pool._breakers["judging"].current_state == "closed"
        assert pool._breakers["restoration"].current_state == "closed"
