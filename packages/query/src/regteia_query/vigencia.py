"""vigencia_em: whether a norm, or one of its Dispositivos, applied on a date, from the events the graph records.

Status over time, not text over time. The stored text is the portal's latest wording; the answer says whether that
wording is the one that applied on the date and, when it isn't, lists what changed after it. It never reconstructs
an earlier wording (CLAUDE.md, domain rules).

Where the dates come from:
- the norm starts on its own date (`Norma.data`; the graph doesn't read "entra em vigor" clauses);
- a revocation of the whole norm is a REVOGA edge: its `desde`, or else the revoking norm's date. With several, the
  earliest counts (later ones revoke what was already revoked). `estado` is authoritative for today;
- an article-level change is an ALTERA edge from `atualizacoes` (or an entry whose target isn't in the text): its
  `a_partir_de`, or else the amending norm's date.
A change with no date at all makes the answer `indeterminada` rather than a guess.
"""

import re
from datetime import date, timedelta

from regteia_schema import FEDERAL_PREFIXES

from .db import Leitor
from .modelos import (
    DispositivoResumo,
    EventoVigencia,
    NormaCitada,
    NormaResumo,
    Vigencia,
    VigenciaDispositivo,
    VigenciaNorma,
)
from .normas import DispositivoNaoEncontrado, _datas_futuras, _proximos, resolver
from .resolver import separar_dispositivo
from .texto import desquebrar

TIPO = {"revogacao": "revogação", "nova_redacao": "nova redação", "inclusao": "inclusão"}
INICIO_RECENTE = timedelta(days=120)  # how close to the norm's date the "start date is the norm's date" caveat shows
_ROMANO = re.compile(r"^[ivxlc]+$")


def _data(d: date | None) -> str:
    return f"{d:%d/%m/%Y}" if d else "data desconhecida"


def _rotulo(chave: str) -> str:
    """'anexo-i/art-2' -> 'Anexo I, art. 2', 'art-90-a' -> 'Art. 90-A' (keys of Dispositivos missing from the text)."""
    partes = []
    for p in chave.split("/"):
        tipo, _, num = p.partition("-")
        num = num.upper() if _ROMANO.match(num) or tipo == "art" else num
        nome = {"art": "art.", "anexo": "Anexo", "item": "Item", "preambulo": "Preâmbulo"}.get(tipo, p)
        partes.append(f"{nome} {num}".strip())
    out = ", ".join(partes)
    return out[0].upper() + out[1:]


def _quando(explicita: date | None, da_norma: date | None) -> tuple[date | None, str]:
    if explicita:
        return explicita, "a_partir_de"
    if da_norma:
        return da_norma, "data_da_norma"
    return None, "desconhecida"


def _evento(em: date, **campos) -> EventoVigencia:
    """An event, marked as in effect or not on `em` (the date asked)."""
    e = EventoVigencia(**campos)
    e.aplicado = None if e.data is None else e.data <= em
    return e


def _revogacoes(rows: list[dict], data: date) -> list[EventoVigencia]:
    out = []
    for r in rows:
        quando, origem = _quando(r["desde"], r["de_data"])
        out.append(
            _evento(
                data,
                tipo="revogacao",
                alcance="norma",
                por=NormaCitada(id=r["de"], titulo=r["titulo"], data=r["de_data"]),
                data=quando,
                origem_data=origem,
                fonte=r["fonte"],
            )
        )
    return out


def _alteracoes(rows: list[dict], data: date) -> list[EventoVigencia]:
    out = []
    for r in rows:
        quando, origem = _quando(r["a_partir_de"], r["de_data"])
        out.append(
            _evento(
                data,
                tipo=r["tipo"],
                alcance="parte" if r["detalhe"] else "dispositivo",
                por=NormaCitada(id=r["de"], titulo=r["titulo"], data=r["de_data"]),
                data=quando,
                origem_data=origem,
                dispositivo=r["dispositivo"],
                rotulo=r["rotulo"],
                detalhe=r["detalhe"],
                entrada=r["entrada"],
                fonte="atualizacoes",
            )
        )
    return out


def _ausentes(rows: list[dict], norma: str, data: date, chave: str | None) -> list[EventoVigencia]:
    """Events for targets the entries name but the portal's text doesn't have (e.g. articles included from a future
    date), stored on the entry as parallel lists."""
    out = []
    for r in rows:
        chaves = r["ausentes"] or []
        tipos = r["ausentes_tipo"] or []
        desdes = r["ausentes_desde"] or [""] * len(chaves)
        detalhes = r["ausentes_detalhe"] or [""] * len(chaves)  # absent before parser version 2
        for k, tipo, desde, detalhe in zip(chaves, tipos, desdes, detalhes, strict=True):
            if chave is not None and k != chave:
                continue
            quando, origem = _quando(date.fromisoformat(desde) if desde else None, r["de_data"])
            out.append(
                _evento(
                    data,
                    tipo=tipo,
                    alcance="parte" if detalhe else "dispositivo",
                    por=NormaCitada(id=r["de"], titulo=r["titulo"], data=r["de_data"]) if r["de"] else None,
                    data=quando,
                    origem_data=origem,
                    dispositivo=f"{norma}#{k}",
                    rotulo=_rotulo(k),
                    detalhe=detalhe or None,
                    no_texto=False,
                    entrada=r["texto"],
                    fonte="atualizacoes",
                )
            )
    return out


def _ordenar(eventos: list[EventoVigencia]) -> list[EventoVigencia]:
    return sorted(eventos, key=lambda e: (e.data is None, e.data or date.min))


def _por(e: EventoVigencia) -> str:
    return e.por.rotulo if e.por else "norma não identificada"


def _norma_em(n: NormaResumo, data: date, hoje: date, revogacoes: list[EventoVigencia]) -> tuple[str, str, list[str]]:
    """(situacao, motivo, notas) of the norm itself on `data`."""
    notas: list[str] = []
    if n.data and data < n.data:
        return "nao_vigente", f"A norma é de {_data(n.data)}: ainda não existia em {_data(data)}.", notas
    if n.estado == "sem_informacao":
        return "indeterminada", "A fonte (ctresb/leis) não informa se este ato está em vigor.", notas
    if n.data and data - n.data < INICIO_RECENTE:
        notas.append(
            f"O início da vigência considerado é a data da norma ({_data(n.data)}); o grafo não lê a cláusula de "
            "vigência (“entra em vigor…”), que pode fixar outra data."
        )
    incoerentes = [e for e in revogacoes if e.data and n.data and e.data < n.data]
    for e in incoerentes:
        notas.append(
            f"A revogação por {_por(e)} tem data ({_data(e.data)}) anterior à própria norma: inconsistência na fonte, "
            "tratada como sem data."
        )
    datadas = [e for e in revogacoes if e.data and e not in incoerentes]
    sem_data = [e for e in revogacoes if not e.data] + incoerentes
    primeira = min(datadas, key=lambda e: e.data) if datadas else None

    if n.estado == "revogada":
        if primeira and data >= primeira.data:
            return "revogada", f"Revogada por {_por(primeira)} a partir de {_data(primeira.data)}.", notas
        if data >= hoje:
            if n.estado_motivo and not n.estado_motivo.lower().startswith("revogad"):
                return "revogada", f"Fora de vigor segundo a fonte: {n.estado_motivo}.", notas
            return "revogada", "A fonte mostra a norma revogada.", notas
        if primeira and not sem_data:
            return (
                "vigente",
                f"Em vigor nessa data; foi revogada depois, por {_por(primeira)}, a partir de {_data(primeira.data)}.",
                notas,
            )
        if primeira:
            nomes = ", ".join(_por(e) for e in sem_data)
            return (
                "indeterminada",
                f"Revogada; a revogação datada mais antiga é de {_data(primeira.data)} ({_por(primeira)}), mas o grafo "
                f"não tem a data da revogação por {nomes}, que pode ser anterior.",
                notas,
            )
        return "indeterminada", "Revogada, mas o grafo não registra desde quando.", notas

    passadas = [e for e in datadas if e.data <= hoje]
    futuras = [e for e in datadas if e.data > hoje]
    for e in passadas + sem_data:
        notas.append(
            f"O grafo registra revogação por {_por(e)} ({_data(e.data)}), mas o portal mostra esta norma em vigor: "
            "confira na fonte oficial."
        )
    if futuras:
        f = min(futuras, key=lambda e: e.data)
        if data >= f.data:
            return "revogada", f"Revogada por {_por(f)} a partir de {_data(f.data)} (revogação com data futura).", notas
        notas.append(f"Será revogada por {_por(f)} a partir de {_data(f.data)}.")
    desde = f" desde {_data(n.data)}" if n.data else ""
    return "vigente", f"Em vigor{desde}.", notas


def _dispositivo_em(
    situacao_norma: tuple[str, str],
    d: dict | None,
    data: date,
    hoje: date,
    eventos: list[EventoVigencia],
) -> tuple[str, str]:
    """(situacao, motivo) of one Dispositivo, given its events (all of them about it) and the norm's own status."""
    if situacao_norma[0] != "vigente":
        return situacao_norma
    inteiros = [e for e in eventos if e.alcance == "dispositivo" and e.tipo in ("inclusao", "revogacao")]
    sem_data = [e for e in inteiros if e.data is None]
    if sem_data:
        e = sem_data[0]
        acao = "incluído" if e.tipo == "inclusao" else "revogado"
        return "indeterminada", f"O histórico diz que foi {acao} por {_por(e)}, mas sem data."
    inclusoes = sorted((e for e in inteiros if e.tipo == "inclusao"), key=lambda e: e.data)
    estado, ultimo = ("inexistente" if inclusoes else "vigente"), None
    for e in sorted(inteiros, key=lambda e: e.data):
        if e.data <= data:
            estado, ultimo = ("vigente" if e.tipo == "inclusao" else "revogado"), e
    if estado == "inexistente":
        e = inclusoes[0]
        return "nao_vigente", f"Incluído por {_por(e)} a partir de {_data(e.data)}: ainda não existia em {_data(data)}."
    if estado == "revogado":
        return "revogada", f"Revogado por {_por(ultimo)} a partir de {_data(ultimo.data)}."
    revogado_hoje = d is not None and d["revogado"]
    if revogado_hoje and not any(e.tipo == "revogacao" for e in inteiros):
        if data >= hoje:
            return "revogada", "O portal mostra o dispositivo revogado."
        return "indeterminada", "O portal mostra o dispositivo revogado, mas o histórico não diz desde quando."
    if ultimo and ultimo.tipo == "inclusao":
        return "vigente", f"Em vigor: incluído por {_por(ultimo)} a partir de {_data(ultimo.data)}."
    aplicadas = [e for e in eventos if e.aplicado]
    if aplicadas:
        e = aplicadas[-1]
        return "vigente", (
            f"Em vigor; última alteração registrada até essa data: {TIPO[e.tipo]} por {_por(e)}, a partir de "
            f"{_data(e.data)}."
        )
    return "vigente", situacao_norma[1]


def _texto_na_data(situacao: str, no_texto: bool, eventos: list[EventoVigencia]) -> str:
    """armazenado: the stored wording is the one of the date; desconhecido: something about it changes later."""
    if situacao != "vigente" or not no_texto:
        return "sem_texto"
    return "desconhecido" if any(not e.aplicado for e in eventos) else "armazenado"


def _sem_historico(n: NormaResumo, data: date, hoje: date) -> str | None:
    """Why a federal act's stored text may not be the wording of `data`, or None when it is. The graph has no
    amendment history for federal acts (ctresb/leis has none): a compiled text is that date's only from the day it
    was downloaded to today; an original text is the act as published, with no later amendment (ADR 0005)."""
    if n.acervo not in FEDERAL_PREFIXES:
        return None
    versao = n.versao_texto or "?"
    if versao.startswith("compilada"):
        if n.baixado_em and n.baixado_em <= data <= hoje:
            return None
        quando = f" em {_data(n.baixado_em)}" if n.baixado_em else ""
        return (
            f"Texto compilado obtido{quando}; o grafo não tem o histórico de alterações deste ato, então não sabe "
            f"se a redação de {_data(data)} era a mesma."
        )
    return (
        f"Texto “{versao}”: o ato como publicado, sem as alterações posteriores, que o grafo não tem. Não o trate "
        f"como a redação de {_data(data)}."
    )


def _nao_lidas(rows: list[dict], data: date) -> list[str]:
    """A note when entries of the norm's history that weren't read down to the article may postdate `data`."""
    duvidosas = [
        r
        for r in rows
        # parcial without a motivo only has targets missing from the text: those are read (see _ausentes)
        if (
            r["resultado"] == "falha"
            or (r["resultado"] == "parcial" and r["motivo"])
            or (r["resultado"] == "norma" and r["motivo"] != "revogação total")
        )
        and (r["de_data"] is None or r["de_data"] > data)
    ]
    if not duvidosas:
        return []
    return [
        f"{len(duvidosas)} entrada(s) do histórico desta norma, de depois dessa data ou sem data, não foram lidas "
        "até o artigo; pode haver alterações que esta resposta não considera. Primeira: "
        f"“{duvidosas[0]['texto']}”."
    ]


def vigencia_em(db: Leitor, ref: str, data: date, *, hoje: date | None = None) -> Vigencia:
    """Was the norm or Dispositivo `ref` in force on `data`, and is its stored text the wording of that date?

    `ref` is a norm ("Resolução BCB 520", "bcb:resolucao-bcb:520") or a Dispositivo ("Resolução BCB 520, art. 88",
    "bcb:resolucao-bcb:520#art-90-a"), including one the entries name but the portal's text doesn't have yet."""
    hoje = hoje or date.today()
    ref_norma, chave = separar_dispositivo(ref)
    n = resolver(db, ref_norma if chave else ref)
    if n.externo:
        return Vigencia(
            ref=ref,
            data=data,
            norma=n,
            chave=chave,
            rotulo=_rotulo(chave) if chave else None,
            situacao="indeterminada",
            motivo="Norma fora dos acervos carregados: o grafo não tem a situação nem o histórico dela.",
            eventos=[],
            notas=[],
        )
    dispositivo_id = f"{n.id}#{chave}" if chave else None
    consultas = [
        ("vigencia_revogacoes", {"id": n.id}),
        ("vigencia_alteracoes", {"norma": n.id, "dispositivo": dispositivo_id}),
        ("vigencia_entradas", {"norma": n.id}),
    ]
    if chave:
        consultas.append(("dispositivo", {"norma": n.id, "id": dispositivo_id}))
    rows = db.ler_varios(consultas)
    revogacoes = _revogacoes(rows[0], data)
    alteracoes = _alteracoes(rows[1], data)
    entradas = rows[2]
    ausentes = _ausentes(entradas, n.id, data, chave)
    situacao, motivo, notas = _norma_em(n, data, hoje, revogacoes)
    notas += _nao_lidas(entradas, data)

    if chave is None:
        return Vigencia(
            ref=ref,
            data=data,
            norma=n,
            situacao=situacao,
            motivo=motivo,
            eventos=_ordenar(revogacoes + alteracoes + ausentes),
            notas=notas,
        )

    d = rows[3][0]["d"] if rows[3] else None
    if d is None and not ausentes:
        sumario = db.ler("norma_sumario", id=n.id)
        itens = sumario[0]["sumario"] if sumario else []
        raise DispositivoNaoEncontrado(dispositivo_id, _proximos(chave, itens))
    proprios = alteracoes + ausentes
    situacao, motivo = _dispositivo_em((situacao, motivo), d, data, hoje, proprios)
    eventos = _ordenar(revogacoes + proprios)

    texto = None
    texto_na_data = _texto_na_data(situacao, d is not None, proprios)
    federal = _sem_historico(n, data, hoje) if texto_na_data == "armazenado" else None
    if federal:
        texto_na_data = "desconhecido"
        notas.insert(0, federal)
    elif situacao == "vigente" and d is None:
        notas.append(
            "O histórico registra este dispositivo, mas o texto publicado no portal ainda não o traz: o grafo não tem "
            "a redação dele."
        )
    elif situacao == "vigente":
        depois = [e for e in proprios if not e.aplicado]
        if depois:
            mudancas = "; ".join(
                f"{TIPO[e.tipo]}{f' ({e.detalhe})' if e.detalhe else ''} por {_por(e)}, "
                f"{'a partir de ' + _data(e.data) if e.data else 'sem data'}"
                for e in depois
            )
            notas.insert(
                0,
                f"O texto armazenado já traz mudanças posteriores a {_data(data)} ({mudancas}). O grafo não guarda "
                "a redação dessa data, e ela não deve ser reconstruída.",
            )
        else:
            texto = desquebrar(d["texto"])
            if n.estado == "alterada" and data < hoje:
                notas.append(
                    "Nenhuma alteração deste dispositivo depois dessa data consta do histórico; o texto é o "
                    "consolidado atual do portal."
                )
            for quando in _datas_futuras(d["texto"], data):
                notas.append(
                    f"O texto menciona “a partir de {_data(quando)}”, depois dessa data: confira se trata de uma "
                    "redação ainda não vigente."
                )
    return Vigencia(
        ref=ref,
        data=data,
        norma=n,
        dispositivo=DispositivoResumo.model_validate(d) if d else None,
        chave=chave,
        rotulo=d["rotulo"] if d else _rotulo(chave),
        situacao=situacao,
        motivo=motivo,
        texto_na_data=texto_na_data,
        texto=texto,
        eventos=eventos,
        notas=notas,
    )


def _base(chave: str) -> str:
    """'art-90-a' -> 'art-90': where a Dispositivo missing from the text goes in reading order."""
    return re.sub(r"-[a-z]$", "", chave)


def _em_ordem(sumario: list[dict], ausentes: list[str]) -> list[tuple[str, dict | None]]:
    """(key, Dispositivo or None) in reading order: each missing key right after its base article and siblings."""
    out: list[tuple[str, dict | None]] = [(d["id"].split("#", 1)[1], d) for d in sumario]
    for k in ausentes:
        base = _base(k)
        pos = len(out)
        for i, (c, _) in enumerate(out):
            if c == base or (c.startswith(base + "-") and c < k):
                pos = i + 1
        out.insert(pos, (k, None))
    return out


def vigencia_dispositivos(db: Leitor, ref: str, data: date, *, hoje: date | None = None) -> VigenciaNorma:
    """`vigencia_em` for a norm and every one of its Dispositivos on `data`, in reading order, in one read. Also lists
    the Dispositivos the history names but the portal's text doesn't have (e.g. included from a future date)."""
    hoje = hoje or date.today()
    n = resolver(db, separar_dispositivo(ref)[0])
    if n.externo:
        return VigenciaNorma(
            ref=ref,
            data=data,
            norma=n,
            situacao="indeterminada",
            motivo="Norma fora dos acervos carregados: o grafo não tem a situação nem o histórico dela.",
            eventos=[],
            dispositivos=[],
            notas=[],
        )
    rev, alt, entradas, sumario = db.ler_varios(
        [
            ("vigencia_revogacoes", {"id": n.id}),
            ("vigencia_alteracoes", {"norma": n.id, "dispositivo": None}),
            ("vigencia_entradas", {"norma": n.id}),
            ("norma_sumario", {"id": n.id}),
        ]
    )
    revogacoes = _revogacoes(rev, data)
    alteracoes = _alteracoes(alt, data)
    ausentes = _ausentes(entradas, n.id, data, None)
    situacao, motivo, notas = _norma_em(n, data, hoje, revogacoes)
    notas += _nao_lidas(entradas, data)
    por_dispositivo: dict[str, list[EventoVigencia]] = {}
    for e in alteracoes + ausentes:
        por_dispositivo.setdefault(e.dispositivo, []).append(e)
    itens = sumario[0]["sumario"] if sumario else []
    existentes = {d["id"] for d in itens}
    faltando = list(dict.fromkeys(e.dispositivo.split("#", 1)[1] for e in ausentes if e.dispositivo not in existentes))
    federal = _sem_historico(n, data, hoje) if situacao == "vigente" else None
    if federal:
        notas.insert(0, federal)
    dispositivos = []
    for chave, d in _em_ordem(itens, faltando):
        did = f"{n.id}#{chave}"
        evs = por_dispositivo.get(did, [])
        sit, mot = _dispositivo_em((situacao, motivo), d, data, hoje, evs)
        dispositivos.append(
            VigenciaDispositivo(
                id=did,
                chave=chave,
                rotulo=d["rotulo"] if d else _rotulo(chave),
                tipo=d["tipo"] if d else None,
                no_texto=d is not None,
                revogado_hoje=bool(d and d["revogado"]),
                situacao=sit,
                motivo=mot,
                texto_na_data=(
                    "desconhecido"
                    if federal and sit == "vigente" and d is not None
                    else _texto_na_data(sit, d is not None, evs)
                ),
                eventos=len(evs),
                posteriores=sum(1 for e in evs if not e.aplicado),
            )
        )
    return VigenciaNorma(
        ref=ref,
        data=data,
        norma=n,
        situacao=situacao,
        motivo=motivo,
        eventos=_ordenar(revogacoes + alteracoes + ausentes),
        dispositivos=dispositivos,
        notas=notas,
    )
