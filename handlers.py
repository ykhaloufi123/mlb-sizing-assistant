"""Implémentations Python des skills de type function (handler: handlers:<fonction>)."""


def compter_mots(texte: str, maximum: int | None = None) -> dict:
    mots = len((texte or "").split())
    return {"mots": mots, "depasse": bool(maximum) and mots > maximum}
