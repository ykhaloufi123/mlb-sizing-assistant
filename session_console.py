"""Console de session pour un agent servi (agents serve) ou déployé (agents deploy).

    uv run python session_console.py <agent>

Chaque ligne envoie un message. Pendant qu'un tour tourne : /steer <texte> le réoriente, /stop l'interrompt.
/fin annule la session. Les noms d'API suivent la documentation de l'Agents SDK (préversion) : à vérifier.
"""
from __future__ import annotations

import asyncio
import inspect
import sys

import craft_support  # noqa: F401  (en premier : adresse de l'instance pour le SDK)
from mistralai import agents


async def _maybe(value):
    return await value if inspect.isawaitable(value) else value


async def main(name: str) -> None:
    agent = await _maybe(agents.Agent.load_from(agent_name=name))
    session = await _maybe(agent.start_session())
    loop = asyncio.get_running_loop()
    print(f"Session ouverte avec {name}. /fin pour terminer.")
    while True:
        line = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
        if not line:
            continue
        if line == "/fin":
            await _maybe(session.cancel())
            break
        turn = await _maybe(session.run(line))
        waiting = asyncio.ensure_future(_maybe(turn.result()))
        while not waiting.done():
            command = asyncio.ensure_future(loop.run_in_executor(None, sys.stdin.readline))
            done, _ = await asyncio.wait({waiting, command}, return_when=asyncio.FIRST_COMPLETED)
            if command in done:
                text = command.result().strip()
                if text.startswith("/steer "):
                    await _maybe(turn.steer(text[7:]))
                elif text == "/stop":
                    await _maybe(turn.interrupt())
            else:
                command.cancel()
        result = waiting.result()
        print(getattr(result, "text", result))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage : python session_console.py <agent>")
    asyncio.run(main(sys.argv[1]))
