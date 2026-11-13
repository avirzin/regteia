from regteia_query.sinonimos import SINONIMOS, expandir


def test_expands_whole_words_ignoring_case_and_accents():
    assert expandir("Exchange de cripto") == (
        "prestadora de serviços de ativos virtuais intermediária ativos virtuais criptoativos"
    )
    assert expandir("regras de PLD/FT para bancos") == SINONIMOS["pld/ft"]
    assert expandir("Open Finance: compartilhamento") == SINONIMOS["open finance"]


def test_no_partial_matches_and_no_expansion_when_not_needed():
    assert expandir("tokenização de recebíveis") == ""  # "token" only as a whole word
    assert expandir("capital mínimo de instituição de pagamento") == ""
    assert expandir("") == ""


def test_keys_are_plain_lower_case():
    for k in SINONIMOS:
        assert k == k.lower() and k.isascii(), k
