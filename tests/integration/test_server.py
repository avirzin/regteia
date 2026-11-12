"""regteia-server over the real fixture graph: JSON endpoints, Arrow export, ETag revalidation."""

import json

import pyarrow as pa
import pytest
from fastapi.testclient import TestClient
from regteia_schema.env import AVISO
from regteia_server.app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(leitor, tmp_path_factory):
    app = create_app(leitor=lambda: leitor, web_dist=tmp_path_factory.mktemp("sem-web"))
    with TestClient(app) as c:
        yield c


def test_saude_e_estatisticas(client):
    assert client.get("/api/saude").json()["status"] == "ok"
    e = client.get("/api/estatisticas").json()
    assert e["normas"] == 20 and e["aviso"] == AVISO


def test_norma(client):
    r = client.get("/api/normas/Resolu%C3%A7%C3%A3o%20BCB%20520")
    assert r.status_code == 200
    assert r.json()["norma"]["id"] == "bcb:resolucao-bcb:520"
    r = client.get("/api/normas/bcb%3Aresolucao-bcb%3A520")
    assert r.json()["norma"]["estado"] == "alterada"
    r = client.get("/api/normas/Resolu%C3%A7%C3%A3o%20BCB%2099999")
    assert r.status_code == 404 and "sugestoes" in r.json()["detail"]


def test_buscar_relacoes_validation(client):
    assert client.get("/api/buscar", params={"q": "ativos virtuais"}).json()["itens"]
    r = client.get("/api/relacoes", params={"ref": "bcb:resolucao-bcb:589", "tipo": ["altera"]})
    assert [n["norma"]["id"] for n in r.json()["nos"]] == ["bcb:resolucao-bcb:589", "bcb:resolucao-bcb:520"]
    assert client.get("/api/relacoes", params={"ref": "bcb:resolucao-bcb:589", "tipo": ["x"]}).status_code == 422
    assert client.get("/api/relacoes", params={"ref": "bcb:resolucao-bcb:589", "profundidade": 9}).status_code == 422


def test_grafo_arrow_and_etag(client):
    r_nos = client.get("/api/grafo.arrow")
    r_are = client.get("/api/grafo.arrow", params={"tabela": "arestas"})
    assert r_nos.headers["content-type"] == "application/vnd.apache.arrow.stream"
    nos = pa.ipc.open_stream(r_nos.content).read_all()
    arestas = pa.ipc.open_stream(r_are.content).read_all()
    meta = nos.schema.metadata
    assert meta[b"versao"] == arestas.schema.metadata[b"versao"]
    assert json.loads(meta[b"grupos"]) == ["CMN", "BCB", "CVM", "Lei federal", "Outros"]
    assert nos.column_names == ["id", "titulo", "grupo", "estado", "ano"]
    assert max(arestas.column("origem").to_pylist() + arestas.column("destino").to_pylist()) < nos.num_rows
    etag = r_nos.headers["etag"]
    assert client.get("/api/grafo.arrow", headers={"If-None-Match": etag}).status_code == 304
    com = pa.ipc.open_stream(client.get("/api/grafo.arrow", params={"comunicados": "true"}).content).read_all()
    assert com.num_rows == nos.num_rows + 1  # the one comunicado in the fixtures


def test_dispositivo_and_buscar_trechos(client):
    r = client.get("/api/dispositivos/bcb:resolucao-bcb:520%23art-91")
    assert r.status_code == 200
    j = r.json()
    assert j["dispositivo"]["rotulo"] == "Art. 91" and j["redacoes_anteriores"] and j["aviso"] == AVISO
    assert client.get("/api/dispositivos/Resolução BCB 520, art. 91").json()["texto"] == j["texto"]
    r = client.get("/api/dispositivos/Resolução BCB 520, art. 95")
    assert r.status_code == 404 and r.json()["detail"]["sugestoes"][0]["id"] == "bcb:resolucao-bcb:520#art-92"
    assert client.get("/api/dispositivos/Resolução BCB 520").status_code == 422
    b = client.get("/api/buscar", params={"q": "embaralhadores"}).json()
    assert b["itens"][0]["trechos"][0]["dispositivo"]["id"] == "bcb:resolucao-bcb:520#art-90"
