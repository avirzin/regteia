"""regteia: query the local graph from the terminal. A thin adapter: argument parsing and formatting only."""

import argparse
import sys
from collections.abc import Callable
from datetime import date

from pydantic import BaseModel

from .db import Leitor
from .estatisticas import estatisticas
from .modelos import (
    DispositivoDetalhe,
    Estatisticas,
    EventoVigencia,
    NormaDetalhe,
    NormaResumo,
    ResultadoBusca,
    Subgrafo,
    Vigencia,
)
from .normas import NormaNaoEncontrada, buscar, dispositivo, norma, panorama
from .relacoes import PROFUNDIDADE_MAX, TODOS, relacoes
from .vigencia import vigencia_em

ROTULO_RELACAO = {
    ("saida", "REVOGA"): "Revoga",
    ("saida", "REVOGA_PARCIAL"): "Revoga parcialmente",
    ("saida", "ALTERA"): "Altera",
    ("saida", "CITA"): "Cita",
    ("saida", "REGULAMENTA"): "Fundamenta-se em / regulamenta",
    ("saida", "CONJUNTA"): "Norma conjunta com",
    ("entrada", "REVOGA"): "Revogada por",
    ("entrada", "REVOGA_PARCIAL"): "Revogada parcialmente por",
    ("entrada", "ALTERA"): "Alterada por",
    ("entrada", "CITA"): "Citada por",
    ("entrada", "REGULAMENTA"): "Regulamentada por / base legal de",
    ("entrada", "CONJUNTA"): "Norma conjunta com",
}


def _linha(n: NormaResumo, extra: str = "") -> str:
    data = f" ({n.data:%d/%m/%Y})" if n.data else ""
    sufixo = f"  {n.id}" if n.titulo else ""
    return f"[{n.situacao}] {n.rotulo}{data}{extra}{sufixo}"


def _links(n: NormaResumo) -> list[str]:
    out = []
    if n.fonte_url:
        out.append(f"  Fonte oficial: {n.fonte_url}")
    if n.url_arquivo:
        out.append(f"  Arquivo (versão exata): {n.url_arquivo}")
    if n.url_externa:
        out.append(f"  Onde está: {n.url_externa}")
    return out


def fmt_norma(r: NormaDetalhe) -> str:
    n = r.norma
    out = [_linha(n), *_links(n)]
    if n.ementa:
        out.append(f"  Ementa: {n.ementa}")
    out += [f"  ! {nota}" for nota in r.notas]
    for g in r.relacoes:
        out.append(f"\n{ROTULO_RELACAO.get((g.direcao, g.tipo), g.tipo)} ({g.total}):")
        for v in g.itens:
            desde = f", a partir de {v.desde:%d/%m/%Y}" if v.desde else ""
            out.append(f"  {_linha(v.norma, desde)}")
        if g.total > len(g.itens):
            out.append(f"  ... e mais {g.total - len(g.itens)} (use `regteia relacoes`)")
    for c in r.citacoes_texto:
        titulo = "Cita no texto dos artigos" if c.direcao == "saida" else "Citada no texto dos artigos de"
        out.append(f"\n{titulo} ({c.total}):")
        for x in c.itens:
            onde = ", ".join(d.rotulo for d in x.dispositivos) + (" ..." if x.total > len(x.dispositivos) else "")
            out.append(f"  {_linha(x.norma)}  [{x.total}: {onde}]")
        if c.total > len(c.itens):
            out.append(f"  ... e mais {c.total - len(c.itens)}")
    if r.sumario:
        artigos = [d for d in r.sumario if d.tipo == "artigo"]
        revogados = sum(d.revogado for d in r.sumario)
        resumo = f"{len(artigos)} artigo(s)" if artigos else f"divisão: {r.divisao}"
        out.append(f"\nDispositivos ({len(r.sumario)}; {resumo}{f', {revogados} revogado(s)' if revogados else ''}):")
        out.append("  " + ", ".join(d.rotulo + (" [revogado]" if d.revogado else "") for d in r.sumario[:40]))
        if len(r.sumario) > 40:
            out.append(f'  ... e mais {len(r.sumario) - 40} (use `regteia dispositivo "<norma>, art. N"`)')
    return "\n".join(out)


def fmt_dispositivo(r: DispositivoDetalhe) -> str:
    d = r.dispositivo
    situacao = "REVOGADO" if d.revogado else r.norma.situacao
    out = [f"[{situacao}] {r.norma.rotulo}, {d.rotulo}  {d.id}", *_links(r.norma)]
    if d.contexto:
        out.append(f"  {d.contexto}")
    out += [f"  ! {nota}" for nota in r.notas]
    out += ["", r.texto or "(sem texto: dispositivo revogado)"]
    for i, ant in enumerate(r.redacoes_anteriores, 1):
        out += ["", f"--- Redação anterior {i} (riscada no portal) ---", ant]
    if r.cita:
        out += ["", "Cita:", *(f"  {_linha(c)}" for c in r.cita)]
    nav = [f"anterior: {r.anterior.rotulo}" if r.anterior else "", f"próximo: {r.proximo.rotulo}" if r.proximo else ""]
    if any(nav):
        out += ["", "  ".join(x for x in nav if x)]
    return "\n".join(out)


def fmt_busca(r: ResultadoBusca) -> str:
    out = [f"{len(r.itens)} resultado(s) para {r.consulta!r}:"]
    for i in r.itens:
        out.append(f"  {i.score:6.2f}  {_linha(i.norma)}")
        if i.norma.fonte_url:
            out.append(f"          {i.norma.fonte_url}")
        for t in i.trechos:
            rev = " [REVOGADO]" if t.dispositivo.revogado else ""
            out.append(f"          {t.dispositivo.rotulo}{rev}: {t.trecho}")
    out += [f"  ! {nota}" for nota in r.notas]
    return "\n".join(out)


def fmt_subgrafo(r: Subgrafo) -> str:
    out = [
        f"{len(r.nos) - 1} norma(s) a até {r.profundidade} salto(s) de {r.origem} ({r.direcao}; {', '.join(r.tipos)}):"
    ]
    pai: dict[str, list[str]] = {}
    for a in r.arestas:
        pai.setdefault(a.para if r.direcao == "saida" else a.de, []).append(a.tipo)
    for no in r.nos[1:]:
        tipos = ", ".join(sorted(set(pai.get(no.norma.id, [])))) or "-"
        out.append(f"  {no.distancia}  {tipos:<22} {_linha(no.norma)}")
    if r.truncado:
        out.append("  ! Resultado truncado pelo limite: há mais normas (aumente --limite ou filtre --tipo).")
    return "\n".join(out)


def fmt_estatisticas(r: Estatisticas) -> str:
    out = [
        f"Normas: {r.normas:,}  (vigentes {r.por_estado.get('vigente', 0):,}, alteradas "
        f"{r.por_estado.get('alterada', 0):,}, revogadas {r.por_estado.get('revogada', 0):,}; OCR {r.ocr:,})",
        f"Normas fora do acervo referenciadas: {r.stubs:,}  "
        + ", ".join(f"{k} {v:,}" for k, v in r.stubs_por_prefixo.items()),
        f"Relações: {r.arestas:,}  (com data 'desde': {r.arestas_com_desde:,})",
        "  " + ", ".join(f"{k} {v:,}" for k, v in r.arestas_por_relacao.items()),
        f"Referências não resolvidas (upstream): {r.nao_resolvidos:,}  "
        + ", ".join(f"{c.categoria} {c.n:,}" for c in r.nao_resolvidos_por_categoria),
        f"Citações no texto dos artigos: {r.citacoes_texto:,} em {r.citacoes_texto_dispositivos:,} dispositivos  "
        + ", ".join(f"{k} {v:,}" for k, v in r.citacoes_texto_por_alvo.items())
        + f"; {r.citacoes_texto_pares:,} pares de normas, {r.citacoes_texto_pares_novos:,} sem relação no upstream"
        + f"; {r.citacoes_pendentes:,} a normas do BCB/CVM que o grafo não tem",
        f"Dispositivos: {r.dispositivos:,}  "
        + ", ".join(f"{k} {v:,}" for k, v in r.dispositivos_por_tipo.items())
        + f"; revogados {r.dispositivos_revogados:,}, com redação anterior {r.dispositivos_com_redacao_anterior:,}",
        "  Normas por divisão: " + ", ".join(f"{k} {v:,}" for k, v in r.normas_por_divisao.items()),
        f"Atualizações (entradas): {r.atualizacoes:,}  "
        + ", ".join(f"{k} {v:,}" for k, v in r.atualizacoes_por_resultado.items()),
        f"  Alterações por dispositivo: {r.alteracoes_dispositivo:,}  "
        + ", ".join(f"{k} {v:,}" for k, v in r.alteracoes_por_tipo.items())
        + f"; com data {r.alteracoes_com_data:,}, vigência futura {r.alteracoes_futuras:,}",
        f"  Falhas do parser de atualizações: {r.falhas_atualizacoes:,}",
        "\nPor órgão:",
    ]
    for orgao, c in r.por_orgao.items():
        out.append(f"  {orgao:<40} {sum(c.values()):>7,}  " + ", ".join(f"{k} {v:,}" for k, v in sorted(c.items())))
    out.append("\nPor série:")
    for s in r.por_serie:
        out.append(f"  {s.acervo}:{s.serie:<34} {s.total:>7,}  vig {s.vigente:,} alt {s.alterada:,} rev {s.revogada:,}")
    decadas: dict[int, int] = {}
    for d in r.por_decada:
        decadas[d.decada] = decadas.get(d.decada, 0) + d.n
    out.append("\nPor década:")
    out += [f"  {k}s {v:>7,}" for k, v in sorted(decadas.items())]
    out.append("\nÚltima ingestão:")
    for i in r.ingestoes:
        em = f"{i.em:%Y-%m-%d %H:%M} UTC" if i.em else "-"
        out.append(f"  {i.fonte:<12} {i.sha}  {em}  {i.modo}, {i.arquivos} arquivo(s)")
    return "\n".join(out)


SITUACAO_VIGENCIA = {
    "vigente": "EM VIGOR",
    "revogada": "REVOGADA",
    "nao_vigente": "AINDA NÃO VIGENTE",
    "indeterminada": "INDETERMINADA",
}
TIPO_EVENTO = {"revogacao": "revogação", "nova_redacao": "nova redação", "inclusao": "inclusão"}


def fmt_evento(e: EventoVigencia) -> str:
    quando = f"{e.data:%d/%m/%Y}" if e.data else "sem data"
    if e.origem_data == "data_da_norma":
        quando += " (data da norma)"
    marca = {True: "x", False: " ", None: "?"}[e.aplicado]
    alvo = "a norma" if e.alcance == "norma" else (e.rotulo or e.dispositivo or "")
    if e.detalhe:
        alvo += f", {e.detalhe}"
    if not e.no_texto:
        alvo += " [fora do texto publicado]"
    por = e.por.rotulo if e.por else "?"
    return f"  [{marca}] {quando:<24} {TIPO_EVENTO[e.tipo]}: {alvo} — {por}"


def fmt_vigencia(r: Vigencia) -> str:
    alvo = r.norma.rotulo
    if r.chave:
        alvo += f", {r.rotulo}"
    out = [f"[{SITUACAO_VIGENCIA[r.situacao]} em {r.data:%d/%m/%Y}] {alvo}", f"  {r.motivo}", *_links(r.norma)]
    out.append(f"  Situação hoje: {r.norma.situacao_detalhada}")
    out += [f"  ! {nota}" for nota in r.notas]
    if r.eventos:
        out.append("\nEventos ([x] já valiam na data, [ ] posteriores, [?] sem data):")
        out += [fmt_evento(e) for e in r.eventos]
    if r.texto_na_data == "armazenado" and r.texto:
        out += ["", "Texto (a redação armazenada é a dessa data):", r.texto]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="regteia", description=__doc__)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("norma", help="one norm: status, sources and direct relations")
    sp.add_argument("ref", help='id or name, e.g. "Resolução BCB 520", "bcb:resolucao-bcb:520"')
    sp.add_argument("--limite", type=int, default=10, help="items per relation type")

    sp = sub.add_parser("dispositivo", help="one article (or annex, item): text, notes, earlier wording")
    sp.add_argument("ref", help='e.g. "Resolução BCB 520, art. 88", "bcb:resolucao-bcb:520#art-88"')

    sp = sub.add_parser("buscar", help="full-text search over titles, summaries and article text")
    sp.add_argument("texto")
    sp.add_argument("--limite", type=int, default=20)
    sp.add_argument("--sem-revogadas", action="store_true")
    sp.add_argument("--comunicados", action="store_true", help="do not down-rank comunicados")

    sp = sub.add_parser("panorama", help="norms not revoked on a topic")
    sp.add_argument("tema")
    sp.add_argument("--limite", type=int, default=30)

    sp = sub.add_parser("relacoes", help="multi-hop traversal")
    sp.add_argument("ref")
    sp.add_argument("--tipo", action="append", choices=[t.lower() for t in TODOS], help="repeatable; default all")
    sp.add_argument("--direcao", choices=["saida", "entrada", "ambas"], default="saida")
    sp.add_argument("--profundidade", type=int, default=1, choices=range(1, PROFUNDIDADE_MAX + 1))
    sp.add_argument("--limite", type=int, default=200)
    sp.add_argument("--comunicados", action="store_true")

    sub.add_parser("estatisticas", help="corpus coverage and health")

    sp = sub.add_parser("vigencia", help="was a norm or article in force on a date, and is its text that date's")
    sp.add_argument("ref", help='e.g. "bcb:resolucao-bcb:520#art-88", "Resolução BCB 520, art. 90-A"')
    sp.add_argument("data", type=date.fromisoformat, help="YYYY-MM-DD")

    args = p.parse_args(argv)

    calls: dict[str, tuple[Callable[[Leitor], BaseModel], Callable]] = {
        "norma": (lambda db: norma(db, args.ref, limite=args.limite), fmt_norma),
        "dispositivo": (lambda db: dispositivo(db, args.ref), fmt_dispositivo),
        "buscar": (
            lambda db: buscar(
                db,
                args.texto,
                limite=args.limite,
                incluir_revogadas=not args.sem_revogadas,
                incluir_comunicados=args.comunicados,
            ),
            fmt_busca,
        ),
        "panorama": (lambda db: panorama(db, args.tema, limite=args.limite), fmt_busca),
        "relacoes": (
            lambda db: relacoes(
                db,
                args.ref,
                tipos=args.tipo,
                direcao=args.direcao,
                profundidade=args.profundidade,
                limite=args.limite,
                incluir_comunicados=args.comunicados,
            ),
            fmt_subgrafo,
        ),
        "estatisticas": (estatisticas, fmt_estatisticas),
        "vigencia": (lambda db: vigencia_em(db, args.ref, args.data), fmt_vigencia),
    }
    run, fmt = calls[args.cmd]
    try:
        with Leitor.do_ambiente() as db:
            result = run(db)
    except (NormaNaoEncontrada, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2) if args.json else f"{fmt(result)}\n\n{result.aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
