"""Fonctions d'appui du code généré par Mistral Craft Table."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import inspect
import json
import os
import re
import urllib.request
from fnmatch import fnmatchcase
from typing import Any

_METHODS = {
    str: {"lower", "upper", "strip", "lstrip", "rstrip", "startswith", "endswith", "split", "replace", "title",
          "capitalize", "count", "find", "join", "zfill"},
    dict: {"get", "keys", "values", "items"},
    list: {"count", "index"},
}


def call_handler(spec: str, args: dict[str, Any], idempotency_key: str | None = None) -> Any:
    """Appelle l'implémentation d'un skill, désignée par « module:fonction »."""
    module_name, _, func_name = spec.partition(":")
    func = getattr(importlib.import_module(module_name), func_name)
    kwargs = {k: v for k, v in args.items() if v is not None}
    if idempotency_key is not None:
        params = inspect.signature(func).parameters
        if "idempotency_key" in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            kwargs["idempotency_key"] = idempotency_key
    return func(**kwargs)


def idempotency_key(skill_id: str, args: dict[str, Any]) -> str:
    """Même outil et mêmes arguments : même clé (le système appelé ignore la seconde demande)."""
    payload = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{skill_id}|{payload}".encode()).hexdigest()[:32]


def tool_matches(tool: str, patterns: list[str]) -> bool:
    return not patterns or any(fnmatchcase(tool, p) for p in patterns)


def blocks_text(blocks: Any) -> str:
    """Texte de blocs de contenu de l'Agents SDK."""
    if isinstance(blocks, str):
        return blocks
    parts = []
    for block in blocks or []:
        text = getattr(block, "text", None) if not isinstance(block, dict) else block.get("text")
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def parse_json_or_none(text: str) -> Any:
    try:
        return parse_json(text)
    except ValueError:
        return None


# Adresse de l'API Mistral, sous l'un de ces noms : MISTRAL_API_URL (lu par l'Agents SDK), MISTRAL_BASE_URL
# (format de Craft) ou SERVER_URL (lu par le worker Workflows). Aucun : API publique.
ENDPOINT_VARS = ("MISTRAL_API_URL", "MISTRAL_BASE_URL", "SERVER_URL")


def api_root(url: str | None = None) -> str:
    """Racine de l'API, sans /v1 : `url`, sinon l'environnement, sinon https://api.mistral.ai."""
    if url is None:
        url = next((os.environ[name] for name in ENDPOINT_VARS if os.environ.get(name, "").strip()),
                   "https://api.mistral.ai")
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = "https://" + url
    return url[:-3] if url.endswith("/v1") else url


def align_endpoint() -> None:
    """Une seule instance pour tous les SDK. Appelée à l'import de ce module, avant ceux des SDK : l'adresse
    donnée sous l'un des noms est recopiée dans MISTRAL_API_URL et SERVER_URL s'ils manquent, et mise en forme."""
    for name in ENDPOINT_VARS:
        if name in os.environ and not os.environ[name].strip():
            del os.environ[name]  # ligne vide d'un .env : comme absente, plutôt qu'une adresse vide
    if any(name in os.environ for name in ENDPOINT_VARS):
        root = api_root()
        for name in ("MISTRAL_API_URL", "SERVER_URL"):
            os.environ[name] = api_root(os.environ.get(name, root))


align_endpoint()


def mistral_post(path: str, payload: dict[str, Any], timeout: float = 120) -> Any:
    """POST JSON sur l'API Mistral (clé MISTRAL_API_KEY)."""
    request = urllib.request.Request(api_root() + path, data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": "Bearer " + os.environ.get("MISTRAL_API_KEY", ""), "Content-Type": "application/json",
        "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read() or b"null")


def moderation_flags(text: str, categories: list[str], threshold: float, model: str = "mistral-moderation-latest",
                     block_on_error: bool = False) -> list[str]:
    """Catégories signalées par le modèle de modération de Mistral (liste vide : rien à signaler)."""
    try:
        result = (mistral_post("/v1/moderations", {"model": model, "input": [text]}).get("results") or [{}])[0]
    except Exception:
        return ["modération indisponible"] if block_on_error else []
    scores = result.get("category_scores") or {}
    flags = result.get("categories") or {}
    names = categories or sorted(set(scores) | set(flags))
    return [c for c in names if float(scores.get(c, 1.0 if flags.get(c) else 0.0)) >= threshold]


def library_search(library_ids: list[str], query: str, model: str = "mistral-medium-latest") -> Any:
    """Interroge des bibliothèques Studio avec l'outil document_library (API Conversations)."""
    data = mistral_post("/v1/conversations", {"model": model, "inputs": query, "store": False,
                                               "tools": [{"type": "document_library", "library_ids": library_ids}]})
    outputs = (data or {}).get("outputs") or []
    content = outputs[-1].get("content") if outputs else ""
    if isinstance(content, list):
        content = "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return {"reponse": content}


@contextlib.contextmanager
def step_span(workflow: str, step: str, kind: str, target: str = ""):
    """Span OpenTelemetry d'un pas (attributs craft.*), pour relire l'exécution dans l'atelier Craft."""
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return
    tracer = trace.get_tracer("mistral-craft")
    with tracer.start_as_current_span(f"craft.step {step}") as span:
        span.set_attribute("craft.workflow", workflow)
        span.set_attribute("craft.step", step)
        span.set_attribute("craft.step.type", kind)
        if target:
            span.set_attribute("craft.target", target)
        yield span


def event_request(event: Any) -> dict[str, Any]:
    """Événement d'un déclencheur (TriggerEvent) sous forme de dictionnaire : body, headers, event_type."""
    if isinstance(event, dict):
        request = dict(event)
    else:
        body: Any = None
        for name in ("body", "json"):
            value = getattr(event, name, None)
            if value is not None:
                body = value() if callable(value) else value
                break
        if body is None and hasattr(event, "raw_body"):
            try:
                body = json.loads(event.raw_body)
            except (TypeError, ValueError):
                body = event.raw_body
        request = {"body": body, "headers": dict(getattr(event, "headers", None) or {})}
    body = request.get("body")
    if isinstance(body, (str, bytes)):
        try:
            request["body"] = body = json.loads(body)
        except ValueError:
            pass
    if isinstance(body, dict):
        request.setdefault("event_type", body.get("event_type") or body.get("type") or body.get("action"))
    return request


def parse_json(text: str) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else ""
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except ValueError:
        start, end = raw.find("{"), raw.rfind("}")
        if 0 <= start < end:
            return json.loads(raw[start:end + 1])
        raise


def _get(obj: Any, key: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    if isinstance(obj, (list, tuple, str)) and isinstance(key, int) and not isinstance(key, bool):
        return obj[key] if -len(obj) <= key < len(obj) else None
    return None


def _call(obj: Any, name: str, *args: Any) -> Any:
    if obj is None:
        return None
    allowed = next((m for kind, m in _METHODS.items() if isinstance(obj, kind)), set())
    if name not in allowed:
        raise ValueError(f"méthode non autorisée : {name}")
    result = getattr(obj, name)(*args)
    return list(result) if name in ("keys", "values", "items") else result


def _len(value: Any) -> int:
    return 0 if value is None else len(value)


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _lower(value: Any) -> str:
    return _str(value).lower()


def _upper(value: Any) -> str:
    return _str(value).upper()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _matches(value: Any, pattern: Any) -> bool:
    text = value if isinstance(value, str) else ("" if value is None else json.dumps(value, ensure_ascii=False))
    return re.search(str(pattern), text) is not None


def _default(value: Any, fallback: Any = None) -> Any:
    return fallback if value in (None, "", [], {}) else value


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _cond(test: Any) -> bool:
    """Évalue une condition ; une donnée absente ou incomparable rend la condition fausse."""
    try:
        return bool(test())
    except (TypeError, ValueError, ZeroDivisionError, IndexError, KeyError):
        return False


def is_active(meta: dict[str, dict[str, Any]], sid: str, steps: dict[str, dict[str, Any]]) -> bool:
    """Même règle que le moteur Craft : parents terminés, voie de condition choisie, join all ou any."""
    parents = meta[sid]["needs"]
    if not parents:
        return True

    def parent_ok(parent: str) -> bool:
        state = steps.get(parent) or {}
        if state.get("status") != "completed":
            return False
        targets = meta[parent].get("targets") or []
        if sid in targets:
            return state.get("output") == sid
        return True

    results = [parent_ok(p) for p in parents]
    return all(results) if meta[sid]["join"] == "all" else any(results)
