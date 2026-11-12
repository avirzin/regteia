"""Splitting norm bodies into Dispositivos. Real fixture files first; the small synthetic bodies reproduce shapes
found in the corpus (each names the norm it comes from)."""

from regteia_ingest.parse.dispositivos import dividir
from regteia_ingest.parse.frontmatter import read_norma

from tests.conftest import FIXTURES

BCB = FIXTURES / "normas-bcb"
CVM = FIXTURES / "normas-cvm"


def _dividir(path, norma_id="bcb:resolucao-bcb:1"):
    _, corpo = read_norma(path)
    return dividir(norma_id, corpo)


def _chaves(d):
    return [x.id.split("#", 1)[1] for x in d.dispositivos]


def test_res_bcb_520_articles_sections_annex_and_struck_wording():
    d = _dividir(BCB / "resolucoes-bcb/2025/resolucao-bcb-0520.md", "bcb:resolucao-bcb:520")
    assert d.metodo == "artigos"
    chaves = _chaves(d)
    assert chaves[0] == "preambulo"
    assert chaves[1:93] == [f"art-{n}" for n in range(1, 93)]
    assert chaves[-1] == "anexo"
    por_id = {x.id: x for x in d.dispositivos}
    a2 = por_id["bcb:resolucao-bcb:520#art-2"]
    assert a2.rotulo == "Art. 2" and a2.norma == "bcb:resolucao-bcb:520"
    assert a2.contexto == "CAPÍTULO II · DAS DEFINIÇÕES"
    assert "I - *airdrop*" in a2.texto  # incisos stay inside the article
    a6 = por_id["bcb:resolucao-bcb:520#art-6"]
    assert a6.contexto.endswith("› Seção I · Das intermediárias de ativos virtuais")
    # art. 91: the portal struck the old wording and added the new one (Res. BCB 589)
    a91 = por_id["bcb:resolucao-bcb:520#art-91"]
    assert not a91.revogado
    assert "6 de novembro de 2026" in a91.texto and "30 de outubro de 2026" not in a91.texto
    assert len(a91.redacoes_anteriores) == 1 and "30 de outubro de 2026" in a91.redacoes_anteriores[0]
    assert "~~" not in a91.texto
    assert all(x.ordem == i for i, x in enumerate(d.dispositivos))


def test_amending_norm_keeps_quoted_articles_inside_its_own():
    # Res. BCB 589 quotes the new wording of articles of Res. BCB 520: they are not articles of 589
    d = _dividir(BCB / "resolucoes-bcb/2026/resolucao-bcb-0589.md")
    assert _chaves(d) == ["preambulo", "art-1", "art-2"]
    assert "Art. 91" in d.dispositivos[1].texto


def test_hard_wrapped_text_and_numbered_annexes():
    d = _dividir(BCB / "instrucoes-normativas-bcb/2026/instrucao-normativa-bcb-0704.md")
    assert d.metodo == "artigos"
    assert "art-1" in _chaves(d) and d.dispositivos[1].texto.startswith("Art. 1º")
    assert d.dispositivos[1].contexto == "CAPÍTULO I · DO OBJETO E DO ÂMBITO DE APLICAÇÃO"  # title over two lines
    d = _dividir(BCB / "instrucoes-normativas-bcb/2025/instrucao-normativa-bcb-0693.md")
    assert _chaves(d)[-3:] == ["anexo-i", "anexo-ii", "anexo-iii"]
    assert d.dispositivos[-1].rotulo == "Anexo III"


def test_old_norms_split_by_roman_items():
    d = _dividir(BCB / "resolucoes-cmn/1968/resolucao-cmn-0102.md")
    assert d.metodo == "itens"
    assert _chaves(d) == ["preambulo", "item-i", "item-ii", "item-iii"]
    assert d.dispositivos[1].rotulo == "Item I"


def test_unstructured_and_empty_bodies():
    d = _dividir(BCB / "comunicados/2002/comunicado-10000.md")
    assert d.metodo == "texto" and _chaves(d) == ["texto"]
    # mid-paragraph "Anexo 3 à Instrução CVM nº 480/09, devem ser..." lines are prose, not annex headings
    d = _dividir(CVM / "oficios-circulares/2022/oc-anual-sep-2022.md")
    assert _chaves(d) == ["texto"]
    # upstream's placeholder when the portal has no text
    assert _dividir(BCB / "cartas-circulares/2008/carta-circular-3365.md").metodo == "vazio"


def test_heading_forms():
    corpo = "\n\n".join(
        [
            "# Resolução X",
            "Art. 1º - O Banco Central divulgará a taxa.",  # "- O" is not a suffix (Circular 3.042)
            "Art. 2ºOs testes em produção.",  # no space (IN BCB 725)
            "Art. 3~~º~~  O direito de obter certidão.",  # struck ordinal (Res. CVM 57)
            "Art.\n4º  Esta Resolução entra em vigor.",  # heading broken by hard wrapping (2,937 cases)
            "Art. 4º-A  Incluído depois.",
            "art. 5º da Lei nº 4.595 não é cabeçalho.",  # lower case: wrapped citation
        ]
    )
    d = dividir("bcb:resolucao-bcb:1", corpo)
    assert _chaves(d) == ["art-1", "art-2", "art-3", "art-4", "art-4-a"]
    assert "art. 5º da Lei" in d.dispositivos[-1].texto


def test_sequence_rejects_unquoted_articles_of_another_norm():
    # IN BCB 177 / Res. BCB 407: the amended norm's articles appear without opening quotes
    corpo = "\n\n".join(
        [
            "Art. 1º  A Instrução Normativa nº 99 passa a vigorar acrescida do seguinte art. 37-A:",
            "Art. 37-A.  Para efeitos do disposto...",
            "Art. 17.  [(Revogado pela Resolução Conjunta nº 14.)]",
            "Art. 20.  [(Revogado)]",
            "Art. 2º  Esta Instrução Normativa entra em vigor na data de sua publicação.",
        ]
    )
    d = dividir("bcb:resolucao-bcb:1", corpo)
    assert _chaves(d) == ["art-1", "art-2"]
    assert "Art. 37-A" in d.dispositivos[0].texto


def test_quoted_blocks_are_not_headings():
    corpo = "\n\n".join(
        [
            "Art. 1º  A Resolução nº 1 passa a vigorar com as seguintes alterações:",
            "“Art. 2º  Nova redação do artigo 2 da outra norma.",
            "Parágrafo único.  Continua citado.” (NR)",
            "Art. 2º  Esta Resolução entra em vigor na data de sua publicação.",
        ]
    )
    d = dividir("bcb:resolucao-bcb:1", corpo)
    assert _chaves(d) == ["art-1", "art-2"]
    assert "Nova redação" in d.dispositivos[0].texto
    assert d.dispositivos[1].texto.startswith("Art. 2º  Esta Resolução")


def test_struck_articles_revoked_or_kept_in_place():
    corpo = "\n\n".join(
        [
            "Art. 1º  Primeiro.",
            "~~Art. 2º  Revogado sem nova redação.~~",
            "Art. 3º  Terceiro, com ~~palavra antiga~~ palavra nova.",
            "Art. 4º  A Resolução nº 9 passa a vigorar:",
            "~~Art. 22-A.  Artigo citado de outra norma, riscado.~~",
            "Art. 5º  (Revogado pela Resolução nº 10.)",
        ]
    )
    d = dividir("bcb:resolucao-bcb:1", corpo)
    por = {x.id.split("#")[1]: x for x in d.dispositivos}
    assert list(por) == ["art-1", "art-2", "art-3", "art-4", "art-5"]
    assert por["art-2"].revogado and por["art-2"].texto == ""
    assert por["art-2"].redacoes_anteriores == ("Art. 2º  Revogado sem nova redação.",)
    assert por["art-3"].texto == "Art. 3º  Terceiro, com  palavra nova." and not por["art-3"].revogado
    assert por["art-3"].redacoes_anteriores == ("palavra antiga",)
    # 22-A does not fit between 4 and 5: it stays as earlier wording inside art. 4, not a new article
    assert por["art-4"].redacoes_anteriores[0].startswith("Art. 22-A")
    assert por["art-5"].revogado


def test_roman_items_with_restart_are_kept_whole():
    corpo = "R E S O L V E:\n\nI - Primeiro item:\n\nI - subitem aninhado;\n\nII - outro subitem.\n\nII - Segundo."
    assert dividir("bcb:resolucao-bcb:1", corpo).metodo == "texto"
