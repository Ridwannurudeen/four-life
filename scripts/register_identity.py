"""Register FOUR-LIFE as an ERC-8004 agent on BNB Chain."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent.identity.registry import AgentIdentity


async def main():
    identity = AgentIdentity()
    print(f"Wallet: {identity.account.address}")

    # Check if already registered
    agent_id = await identity.get_agent_id()
    if agent_id:
        print(f"Already registered: Agent ID {agent_id}")
        return

    # Register
    print("Registering on BRC8004 IdentityRegistry...")
    agent_id = await identity.register(
        "https://four-life.gudman.xyz/.well-known/agent-registration.json"
    )
    print(f"Registered! Agent ID: {agent_id}")


asyncio.run(main())
