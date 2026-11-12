"""regteia: query the local graph from the terminal. A thin adapter: argument parsing and formatting only."""

import argparse
import sys
from collections.abc import Callable

from pydantic import BaseModel

from .db import Leitor
from .estatisticas import estatisticas
from .modelos import Estatisticas, NormaDetalhe, NormaResumo, ResultadoBusca, Subgrafo
from .normas import NormaNaoEncontrada, buscar, norma, panorama
from .relacoes import PROFUNDIDADE_MAX, TODOS, relacoes

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
    return "\n".join(out)


def fmt_busca(r: ResultadoBusca) -> str:
    out = [f"{len(r.itens)} resultado(s) para {r.consulta!r}:"]
    for i in r.itens:
        out.append(f"  {i.score:6.2f}  {_linha(i.norma)}")
        if i.norma.fonte_url:
            out.append(f"          {i.norma.fonte_url}")
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
        f"Referências não resolvidas: {r.nao_resolvidos:,}",
        "Falhas do parser de atualizações: "
        + ("ainda não implementado" if r.falhas_atualizacoes is None else f"{r.falhas_atualizacoes:,}"),
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="regteia", description=__doc__)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("norma", help="one norm: status, sources and direct relations")
    sp.add_argument("ref", help='id or name, e.g. "Resolução BCB 520", "bcb:resolucao-bcb:520"')
    sp.add_argument("--limite", type=int, default=10, help="items per relation type")

    sp = sub.add_parser("buscar", help="full-text search (titles and summaries for now)")
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

    sp = sub.add_parser("vigencia", help="in force on a date (roadmap step 7)")
    sp.add_argument("ref")
    sp.add_argument("data")

    args = p.parse_args(argv)
    if args.cmd == "vigencia":
        print("vigencia_em ainda não existe: chega com o parser de atualizações (roadmap, passo 7).", file=sys.stderr)
        return 2

    calls: dict[str, tuple[Callable[[Leitor], BaseModel], Callable]] = {
        "norma": (lambda db: norma(db, args.ref, limite=args.limite), fmt_norma),
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
