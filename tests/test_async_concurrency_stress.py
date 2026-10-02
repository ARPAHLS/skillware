"""Concurrency stress tests and simulation for async skill execution."""

import asyncio
import random
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from skillware.context import SkillContext
from skillware.core.base_skill import BaseSkill


class FastSyncSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "stress/fast_sync",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        }

    def execute(self, params: Dict[str, Any]) -> Any:
        # Simulate CPU/thread work
        task_id = params["task_id"]
        return {"task_id": task_id, "mode": "sync", "squared": task_id * task_id}


class FastAsyncSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "stress/fast_async",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "sleep_time": {"type": "number"},
                },
                "required": ["task_id"],
            },
        }

    async def aexecute(self, params: Dict[str, Any]) -> Any:
        task_id = params["task_id"]
        sleep_time = float(params.get("sleep_time", 0.005))
        await asyncio.sleep(sleep_time)
        return {"task_id": task_id, "mode": "async", "cubed": task_id**3}


@pytest.mark.asyncio
async def test_high_concurrency_mixed_skills():
    """Execute 60 concurrent tasks mixing sync and async skills through SkillContext."""
    ctx = SkillContext(skill="stress/mixed")
    sync_inst = FastSyncSkill()
    async_inst = FastAsyncSkill()

    def mock_prepare(skill_id: str):
        if skill_id == "stress/fast_sync":
            return MagicMock(
                skill_id=skill_id,
                manifest=sync_inst.manifest,
                bundle={"class": FastSyncSkill, "manifest": sync_inst.manifest},
            )
        return MagicMock(
            skill_id=skill_id,
            manifest=async_inst.manifest,
            bundle={"class": FastAsyncSkill, "manifest": async_inst.manifest},
        )

    ctx.prepare = mock_prepare  # type: ignore
    ctx._instances["stress/fast_sync"] = sync_inst
    ctx._instances["stress/fast_async"] = async_inst

    async def worker(idx: int):
        if idx % 2 == 0:
            res = await ctx.aexecute("stress/fast_sync", {"task_id": idx})
            assert res["task_id"] == idx
            assert res["squared"] == idx * idx
            assert res["mode"] == "sync"
            return res
        else:
            jitter = random.uniform(0.001, 0.01)
            res = await ctx.aexecute(
                "stress/fast_async",
                {"task_id": idx, "sleep_time": jitter},
            )
            assert res["task_id"] == idx
            assert res["cubed"] == idx**3
            assert res["mode"] == "async"
            return res

    results = await asyncio.gather(*(worker(i) for i in range(60)))
    assert len(results) == 60


@pytest.mark.asyncio
async def test_concurrency_stress_throttling_invariants():
    """Verify semaphore invariant holds strictly under 50 concurrent requests."""
    max_concurrency = 4
    ctx = SkillContext(skill="stress/fast_async", max_concurrency=max_concurrency)
    async_inst = FastAsyncSkill()

    ctx.prepare = MagicMock(  # type: ignore
        return_value=MagicMock(
            skill_id="stress/fast_async",
            manifest=async_inst.manifest,
            bundle={"class": FastAsyncSkill, "manifest": async_inst.manifest},
        )
    )
    ctx._instances["stress/fast_async"] = async_inst

    active = 0
    max_seen = 0
    lock = asyncio.Lock()

    orig_aexecute = async_inst.aexecute

    async def instrumented_aexecute(params: Dict[str, Any]) -> Any:
        nonlocal active, max_seen
        async with lock:
            active += 1
            if active > max_seen:
                max_seen = active

        await asyncio.sleep(random.uniform(0.005, 0.015))

        async with lock:
            active -= 1
        return await orig_aexecute(params)

    with patch.object(async_inst, "aexecute", side_effect=instrumented_aexecute):
        tasks = [ctx.aexecute("stress/fast_async", {"task_id": i}) for i in range(50)]
        results = await asyncio.gather(*tasks)

    assert len(results) == 50
    assert max_seen <= max_concurrency
    assert active == 0


@pytest.mark.asyncio
async def test_cancellation_does_not_leak_concurrency():
    """When a coroutine is cancelled, semaphore is released and subsequent calls succeed."""
    ctx = SkillContext(skill="stress/fast_async", max_concurrency=1)
    async_inst = FastAsyncSkill()

    ctx.prepare = MagicMock(  # type: ignore
        return_value=MagicMock(
            skill_id="stress/fast_async",
            manifest=async_inst.manifest,
            bundle={"class": FastAsyncSkill, "manifest": async_inst.manifest},
        )
    )
    ctx._instances["stress/fast_async"] = async_inst

    # Launch task that gets cancelled
    task1 = asyncio.create_task(
        ctx.aexecute("stress/fast_async", {"task_id": 1, "sleep_time": 1.0})
    )
    await asyncio.sleep(0.01)
    task1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task1

    # Ensure subsequent task can immediately acquire semaphore
    res = await ctx.aexecute(
        "stress/fast_async",
        {"task_id": 2, "sleep_time": 0.001},
        timeout=0.5,
    )
    assert res["task_id"] == 2
