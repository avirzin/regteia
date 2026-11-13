"""Cut a short excerpt of a Dispositivo's text around where a search matched. Pure string work: the full-text index
says *that* a text matched, not *where*, so this finds the densest window of query-term prefixes (the index stems
Portuguese words, so "custodiante" also matches "custódia": prefixes approximate that)."""

import re

JANELA = 320
_SEM_ACENTO = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC"
)
_PALAVRA = re.compile(r"[a-z0-9]+")
_VAZIAS = {
    "a", "o", "as", "os", "e", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "ao", "aos", "um",
    "uma", "que", "para", "por", "com", "sem", "se", "ou", "and", "or", "not",
}  # fmt: skip


def sem_acento(texto: str) -> str:
    """Lower case without accents, same length as `texto` (so positions map back)."""
    return texto.translate(_SEM_ACENTO).lower()


def prefixos(consulta: str) -> list[str]:
    out = []
    for p in _PALAVRA.findall(sem_acento(consulta)):
        if p in _VAZIAS or len(p) < 3:
            continue
        pref = p if len(p) <= 4 else p[: max(4, len(p) - 2)]
        if pref not in out:
            out.append(pref)
    return out


def trecho(texto: str, consulta: str, janela: int = JANELA) -> str:
    """The `janela`-character window of `texto` holding the most distinct query terms, cut at word boundaries."""
    plano = sem_acento(texto)
    termos = prefixos(consulta)
    hits: list[tuple[int, int]] = []  # (position, term index)
    for k, t in enumerate(termos):
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(t)}", plano):
            hits.append((m.start(), k))
            if len(hits) > 400:
                break
    hits.sort()
    inicio = 0
    if hits:
        melhor = -1
        for i, (pos, _) in enumerate(hits):
            dentro = {k for p, k in hits[i:] if p < pos + janela - 60}
            if len(dentro) > melhor:
                melhor, inicio = len(dentro), max(0, pos - 60)
    fim = min(len(texto), inicio + janela)
    if inicio > 0:
        espaco = texto.find(" ", inicio)
        inicio = espaco + 1 if 0 <= espaco < inicio + 30 else inicio
    if fim < len(texto):
        espaco = texto.rfind(" ", inicio, fim)
        fim = espaco if espaco > inicio + janela // 2 else fim
    corte = re.sub(r"\s+", " ", texto[inicio:fim]).strip()
    return f"{'… ' if inicio > 0 else ''}{corte}{' …' if fim < len(texto) else ''}"
