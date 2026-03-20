"""E2E smoke test for DevTeam Agent.

Starts the agent using the production DevTeamAgent class and sends a basic
question to validate core functionality.

Usage: uv run python -m tests.e2e_smoke
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env before importing agent modules
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

from src.main import DevTeamAgent  # noqa: E402 — must load .env first


SMOKE_QUESTION = "你是谁？你能做什么？"

# Keywords that must appear in a valid response
EXPECTED_KEYWORDS = ["DevTeam", "周报", "团队"]


async def run_smoke_test() -> bool:
    """Run a basic smoke test. Returns True if passed."""
    print("=" * 50)
    print("DevTeam Agent - E2E Smoke Test")
    print("=" * 50)

    agent = DevTeamAgent()

    print(f"\n📤 发送问题: {SMOKE_QUESTION}")
    response = await agent.query_once(SMOKE_QUESTION)

    print(f"\n📥 Agent 回复:\n{response}\n")
    print("-" * 50)

    if not response.strip():
        print("❌ FAIL: Agent 没有返回任何文字内容")
        return False

    missing = [kw for kw in EXPECTED_KEYWORDS if kw not in response]
    if missing:
        print(f"❌ FAIL: 回答中缺少预期关键词: {missing}")
        return False

    print(f"✅ PASS: 回答包含所有预期关键词 {EXPECTED_KEYWORDS}")
    return True


async def main():
    try:
        passed = await run_smoke_test()
    except Exception as e:
        print(f"\n💥 测试抛出异常: {type(e).__name__}: {e}")
        passed = False

    print("\n" + "=" * 50)
    if passed:
        print("🎉 Smoke Test PASSED")
        sys.exit(0)
    else:
        print("💔 Smoke Test FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
