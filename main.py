"""
main.py — CLI entry point for the Calling Agent.

Usage:
    python main.py             # start batch loop
    python main.py --once      # call the next lead once
    python main.py --serve     # run FastAPI server only
"""

from __future__ import annotations

import argparse
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Hindi Calling Agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--once", action="store_true", help="Call the next lead once and exit")
    group.add_argument("--serve", action="store_true", help="Start FastAPI server only")
    group.add_argument("--batch", type=int, metavar="N", help="Call at most N leads")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        from backend.config import settings
        uvicorn.run("backend.server:app", host=settings.server_host, port=settings.server_port, reload=False)

    elif args.once:
        from backend.orchestrator import run_batch
        asyncio.run(run_batch(max_calls=1))

    elif args.batch:
        from backend.orchestrator import run_batch
        asyncio.run(run_batch(max_calls=args.batch))

    else:
        # default: unlimited batch
        from backend.orchestrator import run_batch
        asyncio.run(run_batch())


if __name__ == "__main__":
    main()
