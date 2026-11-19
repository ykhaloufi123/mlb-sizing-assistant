# Mlb sizing — code Mistral Studio

Généré par Mistral Craft Table. Relancez `craft export studio` après chaque modification du projet.

## Contenu

- `agents_app.py` : les agents, pour l'Agents SDK (`mistralai-agents`, préversion publique) : outils, skills
  (dossiers locaux ou registre Studio), sous-agents, politique de permissions et garde-fous (hooks) ;
- `workflows_app.py` : les workflows, pour Mistral Workflows (`mistralai-workflows`), avec les pas conversationnels
  (formulaire, choix, canvas) et un point d'entrée par webhook ;
- `triggers_setup.py` : enregistre webhooks, déclencheurs et plannings dans Studio (si le projet en a) ;
- `evals_app.py` : les suites d'évaluation pour le SDK d'évaluation (organisations Enterprise) ;
- `main.py`, `Dockerfile` : point d'entrée et image pour `agents serve` / `agents deploy` ;
- `session_console.py` : discuter avec un agent déployé, réorienter ou interrompre un tour ;
- `skills/` : un dossier par skill d'instructions (`SKILL.md`) ;
- `craft_support.py` : fonctions d'appui du code généré ;
- les modules Python des skills de type function (handlers), copiés depuis le projet.

Agents :
- `assistant` : Rédige des réponses courtes en suivant le ton de la maison.

Workflows :
- `reponse` : Réponse à une demande

## Lancer

```bash
uv sync
cp .env.example .env   # puis renseignez MISTRAL_API_KEY (et MISTRAL_API_URL pour une instance dédiée)
uv run --env-file .env python agents_app.py <agent> "votre message"   # un agent, en local
uv run --env-file .env python workflows_app.py                         # le worker des workflows
uv run --env-file .env agents serve . --name <agent>                   # agent servi depuis vos serveurs
uv run --env-file .env agents deploy                                   # agent géré par Mistral (main.py)
uv run --env-file .env python triggers_setup.py                        # aperçu des déclencheurs
```

Les validations humaines des workflows attendent le signal `decision` :
`{"step": "<identifiant du pas>", "approved": true}`. Les pas form, confirm et canvas posent leur question
dans la conversation (Le Chat, Vibe Work).

Les outils à effet de bord reçoivent une clé d'idempotence (`idempotency_key`) : transmettez-la au système
appelé pour qu'une nouvelle tentative ne refasse pas l'action.

Les pas exécutés émettent des spans OpenTelemetry (`craft.step`) : `craft trace import --execution <id>`
rejoue une exécution Studio sur le canevas de l'atelier.

Les API de Mistral Studio évoluent vite : vérifiez le code généré avec la documentation en vigueur.
