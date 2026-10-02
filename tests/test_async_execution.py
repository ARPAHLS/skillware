"""Tests for native asynchronous skill execution and SkillContext async parity."""

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from skillware.context import SkillContext
from skillware.core.base_skill import BaseSkill, SkillwareParamValidationError


class MockSyncSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "mock/sync_skill",
            "version": "1.0.0",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
        }

    def execute(self, params: Dict[str, Any]) -> Any:
        return {"result": f"sync:{params['text']}"}


class MockAsyncSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "mock/async_skill",
            "version": "1.0.0",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "delay": {"type": "number"},
                },
                "required": ["text"],
            },
        }

    async def aexecute(self, params: Dict[str, Any]) -> Any:
        delay = float(params.get("delay", 0))
        if delay > 0:
            await asyncio.sleep(delay)
        return {"result": f"async:{params['text']}"}


class MockUnimplementedSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        return {"name": "mock/unimplemented"}


def test_sync_skill_execute():
    skill = MockSyncSkill()
    res = skill.execute({"text": "world"})
    assert res == {"result": "sync:world"}


@pytest.mark.asyncio
async def test_sync_skill_aexecute_default_fallback():
    skill = MockSyncSkill()
    res = await skill.aexecute({"text": "async_call_to_sync"})
    assert res == {"result": "sync:async_call_to_sync"}


@pytest.mark.asyncio
async def test_async_skill_aexecute():
    skill = MockAsyncSkill()
    res = await skill.aexecute({"text": "pure_async"})
    assert res == {"result": "async:pure_async"}


def test_async_skill_execute_bridge_without_running_loop():
    skill = MockAsyncSkill()
    # Runs synchronously in thread without active event loop
    res = skill.execute({"text": "bridge_sync"})
    assert res == {"result": "async:bridge_sync"}


@pytest.mark.asyncio
async def test_async_skill_execute_bridge_inside_running_loop():
    skill = MockAsyncSkill()
    # When executed inside a running loop, executes via isolated thread pool executor
    res = skill.execute({"text": "bridge_inside_loop"})
    assert res == {"result": "async:bridge_inside_loop"}


def test_unimplemented_skill_raises():
    skill = MockUnimplementedSkill()
    with pytest.raises(NotImplementedError, match="must implement execute"):
        skill.execute({})


@pytest.mark.asyncio
async def test_skill_context_aexecute_and_acall():
    ctx = SkillContext(skill="mock/async_skill")
    skill_instance = MockAsyncSkill()

    with patch.object(ctx, "prepare") as mock_prep:
        mock_prep.return_value = MagicMock(
            skill_id="mock/async_skill",
            manifest=skill_instance.manifest,
            bundle={"class": MockAsyncSkill, "manifest": skill_instance.manifest},
        )
        ctx._instances["mock/async_skill"] = skill_instance

        # Test aexecute
        res1 = await ctx.aexecute("mock/async_skill", {"text": "hello"})
        assert res1 == {"result": "async:hello"}

        # Test acall alias
        res2 = await ctx.acall("mock/async_skill", {"text": "world"})
        assert res2 == {"result": "async:world"}


@pytest.mark.asyncio
async def test_skill_context_aexecute_validation_error():
    ctx = SkillContext(skill="mock/async_skill")
    skill_instance = MockAsyncSkill()

    with patch.object(ctx, "prepare") as mock_prep:
        mock_prep.return_value = MagicMock(
            skill_id="mock/async_skill",
            manifest=skill_instance.manifest,
            bundle={"class": MockAsyncSkill, "manifest": skill_instance.manifest},
        )
        ctx._instances["mock/async_skill"] = skill_instance

        with pytest.raises(SkillwareParamValidationError):
            await ctx.aexecute("mock/async_skill", {"invalid_key": 123})


@pytest.mark.asyncio
async def test_skill_context_aexecute_timeout():
    ctx = SkillContext(skill="mock/async_skill")
    skill_instance = MockAsyncSkill()

    with patch.object(ctx, "prepare") as mock_prep:
        mock_prep.return_value = MagicMock(
            skill_id="mock/async_skill",
            manifest=skill_instance.manifest,
            bundle={"class": MockAsyncSkill, "manifest": skill_instance.manifest},
        )
        ctx._instances["mock/async_skill"] = skill_instance

        with pytest.raises(asyncio.TimeoutError):
            await ctx.aexecute(
                "mock/async_skill",
                {"text": "slow", "delay": 0.2},
                timeout=0.05,
            )


@pytest.mark.asyncio
async def test_skill_context_concurrency_throttling():
    ctx = SkillContext(skill="mock/async_skill", max_concurrency=2)
    skill_instance = MockAsyncSkill()

    with patch.object(ctx, "prepare") as mock_prep:
        mock_prep.return_value = MagicMock(
            skill_id="mock/async_skill",
            manifest=skill_instance.manifest,
            bundle={"class": MockAsyncSkill, "manifest": skill_instance.manifest},
        )
        ctx._instances["mock/async_skill"] = skill_instance

        active_count = 0
        max_active_seen = 0

        original_aexecute = skill_instance.aexecute

        async def tracked_aexecute(params: Dict[str, Any]) -> Any:
            nonlocal active_count, max_active_seen
            active_count += 1
            if active_count > max_active_seen:
                max_active_seen = active_count
            await asyncio.sleep(0.05)
            active_count -= 1
            return await original_aexecute(params)

        with patch.object(skill_instance, "aexecute", side_effect=tracked_aexecute):
            tasks = [
                ctx.aexecute("mock/async_skill", {"text": f"job-{i}"}) for i in range(6)
            ]
            results = await asyncio.gather(*tasks)

        assert len(results) == 6
        assert max_active_seen <= 2
