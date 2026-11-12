"""Encode the exported graph as Arrow IPC streams (one for nodes, one for edges). Formatting only."""

import json

import pyarrow as pa
from regteia_query.grafo import ESTADOS, GRUPOS, RELACOES, GrafoExportado
from regteia_schema.env import AVISO


def _ipc(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as w:
        w.write_table(table)
    return sink.getvalue().to_pybytes()


def _meta(g: GrafoExportado) -> dict[bytes, bytes]:
    return {
        b"versao": g.versao.encode(),
        b"grupos": json.dumps(GRUPOS, ensure_ascii=False).encode(),
        b"estados": json.dumps(ESTADOS).encode(),
        b"relacoes": json.dumps(RELACOES).encode(),
        b"aviso": AVISO.encode(),
    }


def nos(g: GrafoExportado) -> bytes:
    t = pa.table(
        {
            "id": pa.array(g.ids, pa.string()),
            "titulo": pa.array(g.titulos, pa.string()),
            "grupo": pa.array(g.grupos, pa.uint8()),
            "estado": pa.array(g.estados, pa.uint8()),
            "ano": pa.array(g.anos, pa.uint16()),
        }
    ).replace_schema_metadata(_meta(g))
    return _ipc(t)


def arestas(g: GrafoExportado) -> bytes:
    t = pa.table(
        {
            "origem": pa.array(g.origens, pa.uint32()),
            "destino": pa.array(g.destinos, pa.uint32()),
            "tipo": pa.array(g.tipos, pa.uint8()),
        }
    ).replace_schema_metadata(_meta(g))
    return _ipc(t)
