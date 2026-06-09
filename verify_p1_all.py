#!/usr/bin/env python3
"""P1 enhanced strategy research verification."""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.main import app
from app.services.strategy_library import (
    get_strategy,
    save_strategy,
    save_strategy_version,
)
from app.services.strategy_research import (
    compare_strategy_specs,
    generate_candidate_strategies,
    validate_strategy_spec,
)
from app.api.strategy_library import compare_strategy_version, rollback_strategy_version


def check(condition: bool, label: str) -> bool:
    print(("✅" if condition else "❌"), label)
    return condition


async def main() -> int:
    results: list[bool] = []

    paths = {getattr(route, "path", "") for route in app.routes}
    results.append(check("/api/v1/intents/generate-strategies" in paths, "候选策略生成 API"))
    results.append(check("/api/v1/intents/validate-spec" in paths, "策略规格校验 API"))
    results.append(check("/api/v1/strategy-optimizer/batch-backtest" in paths, "批量回测排行 API"))
    results.append(check(
        "/api/v1/strategy-library/{strategy_id}/versions/{version_id}/compare" in paths,
        "版本对比 API",
    ))
    results.append(check(
        "/api/v1/strategy-library/{strategy_id}/versions/{version_id}/rollback" in paths,
        "版本回滚 API",
    ))

    generated = generate_candidate_strategies(
        "中线低回撤策略，排除ST，关注放量和均线趋势",
        count=3,
        use_llm=False,
    )
    results.append(check(generated["total"] >= 3, "生成 3 个以上可执行候选策略"))
    validations = [validate_strategy_spec(item) for item in generated["strategies"]]
    results.append(check(all(item["valid"] for item in validations), "候选策略全部通过本地因子校验"))

    strategy_id = "p1_verify_strategy_tmp"
    base = generated["strategies"][0]
    base["id"] = strategy_id
    base["status"] = "active"
    base["version"] = "1.0.0"
    save_strategy(base)
    candidate = generated["strategies"][1]
    candidate["id"] = strategy_id
    candidate["version"] = "1.1.0"
    version_id = save_strategy_version(
        strategy_id=strategy_id,
        version="1.1.0",
        spec_dict=candidate,
        change_note="p1 verify",
        generated_by="verify",
    )
    diff = compare_strategy_specs(base, candidate)
    results.append(check(bool(diff["entry_conditions"]["added"] or diff["ranking"]["changed"]), "版本差异可解释"))
    compare_payload = await compare_strategy_version(strategy_id, version_id)
    results.append(check(compare_payload["version_id"] == version_id, "版本对比接口返回目标版本"))
    rollback_payload = await rollback_strategy_version(strategy_id, version_id)
    rolled = get_strategy(strategy_id)
    results.append(check(rollback_payload["version"] == "1.1.0", "版本回滚接口返回目标版本"))
    results.append(check((rolled or {}).get("spec", {}).get("version") == "1.1.0", "策略已回滚到目标规格"))

    passed = sum(results)
    total = len(results)
    print(f"\nP1 验证: {passed}/{total} ({passed / total * 100:.1f}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
