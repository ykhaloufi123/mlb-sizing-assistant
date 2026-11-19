# Généré par Mistral Craft Table depuis le projet « Mlb sizing ».
# Ne le modifiez pas à la main : relancez `craft export studio` après chaque changement du projet.


"""Agents du projet, pour l'Agents SDK de Mistral (préversion publique).

Exécution locale : python agents_app.py <agent> "message"
Déploiement : voir README.md (agents chat / agents serve / agents deploy).
"""


from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

import craft_support  # noqa: F401  (en premier : adresse de l'instance pour le SDK)
from mistralai import agents
from pydantic import BaseModel, Field

from craft_support import (_call, _cond, _default, _get, _json, _len, _lower, _matches, _str, _text, _upper,
                           blocks_text, call_handler, idempotency_key, library_search, moderation_flags,
                           parse_json_or_none, tool_matches)

SKILLS = Path(__file__).with_name("skills")


@agents.tool
def compter_mots(texte: Annotated[str, Field(description='Texte à analyser')], maximum: Annotated[int | None, Field(description='Nombre de mots à ne pas dépasser')] = None) -> Any:
    "Compte les mots d'un texte et indique s'il dépasse une longueur donnée."
    return call_handler('handlers:compter_mots', {'texte': texte, 'maximum': maximum})


assistant = agents.Agent(
    name='assistant',
    description='Rédige des réponses courtes en suivant le ton de la maison.',
    instructions="""\
Tu aides les équipes à répondre aux demandes. Charge le skill ton-maison avant d'écrire.
Vérifie la longueur de ta réponse avec compter_mots : 120 mots au maximum.
""",
    model='mistral-small-latest',  # alias « small »
    tools=[compter_mots],
    skills=[agents.RegistrySkill(id=UUID('01a1f2eb-9892-73a9-a1e5-7bddde165d14'), version=2)],
    environment=agents.MistralSandbox(),
)


AGENTS = {
    'assistant': assistant,
}


async def _main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in AGENTS:
        print('usage : python agents_app.py <agent> "message"')
        print('agents :', ', '.join(AGENTS))
        return 1
    result = await AGENTS[argv[1]].run(' '.join(argv[2:]))
    print(result.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv)))
