from regteia_query.trechos import prefixos, trecho


def test_prefixos_drop_stopwords_and_cut_suffixes():
    assert prefixos("custódia de ativos virtuais") == ["custod", "ativ", "virtua"]


def test_trecho_finds_the_densest_window_ignoring_accents():
    texto = ("Lorem ipsum " * 60) + "a CUSTÓDIA de ativos virtuais dos clientes " + ("dolor sit " * 60)
    t = trecho(texto, "custodia ativos virtuais")
    assert "CUSTÓDIA de ativos virtuais" in t
    assert t.startswith("… ") and t.endswith(" …")
    assert len(t) <= 330


def test_trecho_without_match_is_the_start():
    assert trecho("Art. 1º  Texto curto.", "inexistente") == "Art. 1º Texto curto."  # whitespace collapsed
