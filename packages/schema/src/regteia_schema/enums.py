from enum import StrEnum


class Estado(StrEnum):
    VIGENTE = "vigente"
    ALTERADA = "alterada"
    REVOGADA = "revogada"
    #: federal acts only (ADR 0005): ctresb/leis doesn't say whether it is in force. Never shown as in force.
    SEM_INFORMACAO = "sem_informacao"


class Relacao(StrEnum):
    """Norm-to-norm relations, exactly as upstream names them. The Neo4j type is the upper-cased value."""

    REVOGA = "revoga"
    REVOGA_PARCIAL = "revoga_parcial"
    ALTERA = "altera"
    CITA = "cita"
    REGULAMENTA = "regulamenta"
    CONJUNTA = "conjunta"

    @property
    def tipo_neo4j(self) -> str:
        return self.value.upper()
