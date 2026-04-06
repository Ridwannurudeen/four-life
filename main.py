"""FOUR-LIFE entry point."""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - {message}",
    level="INFO",
)
logger.add(
    "data/logs/four-life.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)

# Ensure data dirs exist
Path("data/logs").mkdir(parents=True, exist_ok=True)
Path("data/memory").mkdir(parents=True, exist_ok=True)


async def main():
    from agent.agent import FourLifeAgent

    agent = FourLifeAgent()

    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
