# Généré par Mistral Craft Table depuis le projet « Mlb sizing ».
# Ne le modifiez pas à la main : relancez `craft export studio` après chaque changement du projet.
"""Point d'entrée de la CLI agents : l'agent servi par `agents serve` ou déployé par `agents deploy`.

Pour un autre agent : craft deploy --agent <id>, ou remplacez l'identifiant ci-dessous.
"""
from agents_app import AGENTS

agent = AGENTS['assistant']
