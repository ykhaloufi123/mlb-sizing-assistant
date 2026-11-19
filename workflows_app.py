# Généré par Mistral Craft Table depuis le projet « Mlb sizing ».
# Ne le modifiez pas à la main : relancez `craft export studio` après chaque changement du projet.


"""Workflows du projet, pour Mistral Workflows.

Démarrer le worker : python workflows_app.py (avec MISTRAL_API_KEY).
Validation humaine : envoyez le signal « decision » avec {"step": "<pas>", "approved": true}.
Pas form, confirm et canvas : la conversation (Le Chat, Vibe Work) pose la question à la personne.
Déclencheurs : python triggers_setup.py --apply enregistre webhooks et plannings dans Studio.
"""


from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import craft_support  # noqa: F401  (en premier : adresse de l'instance pour les SDK)
import mistralai.workflows as workflows
from mistralai.workflows import workflow
from pydantic import BaseModel, Field

from craft_support import (_call, _cond, _default, _get, _json, _len, _lower, _matches, _str, _text,
                           _upper, call_handler, event_request, idempotency_key, is_active, parse_json,
                           step_span)


@workflows.activity(start_to_close_timeout=timedelta(minutes=15))
async def agent_assistant(prompt: str, as_json: bool = False, workflow: str = "", step: str = "") -> Any:
    'Exécute l’agent « assistant » avec l’Agents SDK.'
    from agents_app import AGENTS

    with step_span(workflow, step, "agent", 'assistant'):
        result = await AGENTS['assistant'].run(prompt)
    if not as_json:
        return result.text
    output = getattr(result, "output", None)
    if hasattr(output, "model_dump"):
        return output.model_dump(mode="json")
    return parse_json(result.text)


@workflows.activity(start_to_close_timeout=timedelta(minutes=5))
async def tool_compter_mots(args: dict[str, Any], workflow: str = "", step: str = "") -> Any:
    "Skill « compter_mots » : Compte les mots d'un texte et indique s'il dépasse une longueur donnée."
    with step_span(workflow, step, "tool", 'compter_mots'):
        return await asyncio.to_thread(call_handler, 'handlers:compter_mots', args)


class ReponseInput(BaseModel):
    'Entrées du workflow « Réponse à une demande ».'
    demande: str = Field(description='Demande à traiter')


_META_REPONSE = {"brouillon": {"needs": [], "join": "all"}, "longueur": {"needs": ["brouillon"], "join": "all"}, "resultat": {"needs": ["longueur"], "join": "all"}}
_WAVES_REPONSE = [["brouillon"], ["longueur"], ["resultat"]]


class _ReponseSteps:
    'Pas du workflow « Réponse à une demande », partagés par ses points d’entrée.'

    decisions: dict[str, bool]

    async def _run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        steps: dict[str, dict[str, Any]] = {}
        for wave in _WAVES_REPONSE:
            active = [sid for sid in wave if is_active(_META_REPONSE, sid, steps)]
            for sid in wave:
                if sid not in active:
                    steps[sid] = {"status": "skipped", "output": None}
            results = await asyncio.gather(*(getattr(self, "_step_" + sid)(inputs, steps) for sid in active))
            steps.update(zip(active, results))
        return {'resultat': _get(_get(steps, 'resultat'), 'output')}

    async def _step_brouillon(self, inputs: dict[str, Any], steps: dict[str, dict[str, Any]]) -> dict[str, Any]:
        'agent : Brouillon'
        output = await agent_assistant(_text(('Réponds à cette demande : ' + _text(_get(inputs, 'demande')))), False, 'reponse', 'brouillon')
        return {"status": "completed", "output": output}

    async def _step_longueur(self, inputs: dict[str, Any], steps: dict[str, dict[str, Any]]) -> dict[str, Any]:
        'tool : Longueur'
        output = await tool_compter_mots({'texte': _get(_get(steps, 'brouillon'), 'output'), 'maximum': 120}, 'reponse', 'longueur')
        return {"status": "completed", "output": output}

    async def _step_resultat(self, inputs: dict[str, Any], steps: dict[str, dict[str, Any]]) -> dict[str, Any]:
        'transform : Résultat'
        return {"status": "completed", "output": {'reponse': _get(_get(steps, 'brouillon'), 'output'), 'mots': _get(_get(_get(steps, 'longueur'), 'output'), 'mots')}}


@workflows.workflow.define(name='reponse', workflow_display_name='Réponse à une demande')
class ReponseWorkflow(_ReponseSteps):
    'Réponse à une demande'

    def __init__(self) -> None:
        super().__init__()
        self.decisions: dict[str, bool] = {}

    @workflows.workflow.signal(name="decision")
    async def decision(self, payload: dict[str, Any]) -> None:
        """Décision humaine : payload avec step (identifiant du pas) et approved (booléen)."""
        self.decisions[str(payload.get("step"))] = bool(payload.get("approved"))

    @workflows.workflow.entrypoint
    async def run(self, params: ReponseInput) -> dict[str, Any]:
        return await self._run(params.model_dump())


WORKFLOWS = [ReponseWorkflow]


async def main() -> None:
    await workflows.run_worker(WORKFLOWS)


if __name__ == "__main__":
    asyncio.run(main())
