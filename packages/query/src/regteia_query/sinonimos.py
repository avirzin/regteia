"""How people ask -> how the norms write it. A fixed, reviewed table (no LLM, no embeddings): `buscar` keeps the
words typed and adds these, at lower weight, so "exchange" also finds "prestadora de serviços de ativos virtuais".

Keys are lower case without accents and match whole words or phrases of the query. Add entries only when the
mapping is unambiguous in BCB/CMN/CVM regulation; test them in tests/unit/test_sinonimos.py.
"""

import re

from .trechos import sem_acento

SINONIMOS: dict[str, str] = {
    # crypto assets
    "cripto": "ativos virtuais criptoativos",
    "criptomoeda": "ativos virtuais criptoativos",
    "criptomoedas": "ativos virtuais criptoativos",
    "bitcoin": "ativos virtuais criptoativos",
    "exchange": "prestadora de serviços de ativos virtuais intermediária",
    "exchanges": "prestadora de serviços de ativos virtuais intermediária",
    "psav": "prestadora de serviços de ativos virtuais",
    "vasp": "prestadora de serviços de ativos virtuais",
    "stablecoin": "ativo virtual referenciado em moeda fiduciária",
    "stablecoins": "ativo virtual referenciado em moeda fiduciária",
    "token": "ativo virtual",
    # payments and banking
    "fintech": "instituição de pagamento sociedade de crédito direto",
    "scd": "sociedade de crédito direto",
    "sep": "sociedade de empréstimo entre pessoas",
    "open finance": "sistema financeiro aberto",
    "open banking": "sistema financeiro aberto",
    "boleto": "boleto de pagamento",
    "basileia": "capital regulamentar patrimônio de referência",
    "compulsorio": "recolhimento compulsório",
    # compliance
    "pld": "prevenção à lavagem de dinheiro",
    "pld-ft": "prevenção à lavagem de dinheiro financiamento do terrorismo",
    "pld/ft": "prevenção à lavagem de dinheiro financiamento do terrorismo",
    "kyc": "identificação e qualificação de clientes",
    "lgpd": "proteção de dados pessoais",
    # capital markets
    "fidc": "fundo de investimento em direitos creditórios",
    "fii": "fundo de investimento imobiliário",
    "ipo": "oferta pública de distribuição",
    "cri": "certificado de recebíveis imobiliários",
    "cra": "certificado de recebíveis do agronegócio",
}

_CHAVES = sorted(SINONIMOS, key=len, reverse=True)  # longest first: "open finance" before "open"


def expandir(consulta: str) -> str:
    """Extra words for `consulta` (empty if none applies). Matching ignores case and accents."""
    plano = f" {re.sub(r'[^a-z0-9/ -]+', ' ', sem_acento(consulta))} "
    extras: list[str] = []
    for k in _CHAVES:
        if f" {k} " in plano:
            extras.append(SINONIMOS[k])
            plano = plano.replace(f" {k} ", " ")
    return " ".join(extras)
