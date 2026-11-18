"""desquebrar: joins the line-width wrapping inside paragraphs and keeps structure. Cases from real stored texts."""

import re

from regteia_query.texto import desquebrar
from regteia_schema import nome_federal


def _letras(s: str) -> str:
    return re.sub(r"[\s-]", "", s)


def test_joins_wrapped_lines_of_a_paragraph():
    # Resolução BCB 520, art. 91
    t = (
        "Art. 91.  É\nvedado, a partir de 6 de novembro de 2026, às\ninstituições financeiras, às instituições de "
        "pagamento\n\nParágrafo único.  A vedação"
    )
    assert desquebrar(t) == (
        "Art. 91. É vedado, a partir de 6 de novembro de 2026, às instituições financeiras, às instituições de "
        "pagamento\n\nParágrafo único. A vedação"
    )


def test_keeps_structure_typed_without_blank_lines():
    t = "considera-se:\nI - ativo financeiro:\na) dinheiro;\nb) instrumento\npatrimonial;\n§ 1º  Para os fins"
    assert desquebrar(t) == (
        "considera-se:\nI - ativo financeiro:\na) dinheiro;\nb) instrumento patrimonial;\n§ 1º Para os fins"
    )


def test_keeps_headings_and_tables():
    assert desquebrar("CAPÍTULO XI\nDAS DISPOSIÇÕES GERAIS\nArt. 1º  Texto") == (
        "CAPÍTULO XI\nDAS DISPOSIÇÕES GERAIS\nArt. 1º Texto"
    )
    tabela = "| a | b |\n|---|---|\n| 1 | 2 |"
    assert desquebrar(tabela) == tabela


def test_fixed_width_text():
    # bcb:comunicado:14271#item-vi: justified, hyphenated, indented paragraphs
    t = (
        "2.   Na formulação das propostas, limitadas a duas  por  instituição,\ndeverão  ser  informadas a "
        "quantidade\n\n3.   As propostas deverão  ser  encami-\nnhadas ao módulo"
    )
    assert desquebrar(t) == (
        "2. Na formulação das propostas, limitadas a duas por instituição, deverão ser informadas a quantidade\n\n"
        "3. As propostas deverão ser encaminhadas ao módulo"
    )
    recuo = "         A Diretoria  Colegiada do Banco Central do Brasil, em sessão\nrealizada  em   02.12.98,"
    juntos = "         A Diretoria Colegiada do Banco Central do Brasil, em sessão realizada em 02.12.98,"
    assert desquebrar(recuo) == juntos


def test_hanging_indent_and_capitals_continue_the_sentence():
    assert desquebrar("- FRANCISCO JOSE MENDONCA SOUZA, carteira de iden-\n          tidade n. 362.710") == (
        "- FRANCISCO JOSE MENDONCA SOUZA, carteira de identidade n. 362.710"
    )
    assert desquebrar("registrados no sub-\ntítulo Provenientes") == "registrados no subtítulo Provenientes"


def test_real_hyphens_at_line_end_stay():
    assert desquebrar("acatando-\nse as") == "acatando-se as"
    assert desquebrar("os não-\nresidentes") == "os não-residentes"
    assert desquebrar("vistoriá-\nlos") == "vistoriá-los"
    assert desquebrar("exclusivamen-\nte") == "exclusivamente"
    assert desquebrar("pe-\nlos") == "pelos"
    assert desquebrar("pró-\nprio") == "próprio"


def test_only_spaces_and_hyphens_change():
    t = "Art. 2º  Cabe aos chefes da Divisão\n(Dicel) e da Divisão de Gerenciamento\n\n§ 1º  Os níveis de servi-\nço"
    assert _letras(desquebrar(t)) == _letras(t)
    assert desquebrar("") == ""
    assert desquebrar("uma linha só") == "uma linha só"


def test_nome_federal():
    assert nome_federal("lei:14478-2022") == "Lei nº 14.478/2022"
    assert nome_federal("lei:4595-1964") == "Lei nº 4.595/1964"
    assert nome_federal("dec:11563-2023") == "Decreto nº 11.563/2023"
    assert nome_federal("del:1-1965") == "Decreto-Lei nº 1/1965"
    assert nome_federal("lcp:105-2001") == "Lei Complementar nº 105/2001"
    assert nome_federal("mpv:1470-14-1996") == "Medida Provisória nº 1.470-14/1996"
    assert nome_federal("bcb:resolucao-bcb:520") is None
    assert nome_federal("ext:carta-circular-ag:6-1985") is None
