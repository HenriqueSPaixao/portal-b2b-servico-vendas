"""Pub/sub in-process para empurrar lances novos via SSE (Server-Sent Events).

Canal 100% interno entre o negociacao-service e a negociacao-web (navegador).
NÃO envolve Kafka nem outros microsserviços: quando um lance é aceito, a rota o
publica aqui e todos os navegadores conectados naquele processo recebem na hora.

Limitação: o fan-out é por instância (mesmo processo Python). Em 1 instância (o
caso do trabalho/demo) cobre tudo; com N réplicas, cada uma só empurra para os
clientes conectados a ela — por isso a negociacao-web mantém um polling leve como
rede de segurança.
"""

import asyncio
from collections import defaultdict
from uuid import UUID


class LanceBroker:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, processo_id: UUID) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subscribers[processo_id].add(q)
        return q

    def unsubscribe(self, processo_id: UUID, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(processo_id)
        if subs is None:
            return
        subs.discard(q)
        if not subs:
            self._subscribers.pop(processo_id, None)

    def publish(self, processo_id: UUID, data: dict) -> None:
        for q in list(self._subscribers.get(processo_id, ())):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                # Cliente lento: descarta o push; o polling de fallback reconcilia.
                pass
