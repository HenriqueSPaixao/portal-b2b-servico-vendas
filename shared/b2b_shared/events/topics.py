from enum import StrEnum


class Topic(StrEnum):
    """Tópicos Kafka oficiais usados pelo domínio Vendas.

    Lista canônica vem do guia de infra da Eq. Sérgio. Não inventar tópicos.
    """

    EMPRESA_CADASTRADA = "empresa_cadastrada"
    PRODUTO_CADASTRADO = "produto_cadastrado"
    FORNECIMENTO_CRIADO = "fornecimento_criado"
    ESTOQUE_ATUALIZADO = "estoque_atualizado"
    DEMANDA_CRIADA = "demanda_criada"
    DEMANDA_RECORRENTE_GERADA = "demanda_recorrente_gerada"
    MODO_NEGOCIACAO_DEFINIDO = "modo_negociacao_definido"
    LEILAO_INICIADO = "leilao_iniciado"
    LANCE_REALIZADO = "lance_realizado"
    NEGOCIACAO_FECHADA = "negociacao_fechada"
    PEDIDO_CRIADO = "pedido_criado"
    PEDIDO_ATUALIZADO = "pedido_atualizado"
    SOLICITACAO_FRETE_CRIADA = "solicitacao_frete_criada"
    COTACAO_FRETE_ENVIADA = "cotacao_frete_enviada"
    FRETE_SELECIONADO = "frete_selecionado"
