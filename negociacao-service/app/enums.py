from enum import StrEnum


class ModoNegociacao(StrEnum):
    DIRETO = "direto"
    LEILAO_DIRETO = "leilao_direto"
    LEILAO_REVERSO = "leilao_reverso"


class StatusProcesso(StrEnum):
    ABERTO = "ABERTO"
    FECHADA = "FECHADA"
    CANCELADO = "CANCELADO"
