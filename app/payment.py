"""
Integração com o Mercado Pago (Checkout Pro) — cria a preferência de
pagamento (a página de checkout hospedada pelo próprio Mercado Pago, com
PIX/cartão/boleto já prontos, sem precisarmos implementar formulário de
cartão nós mesmos) e verifica o status de um pagamento a partir do id que
a notificação (webhook) avisa.

Importante: a notificação do Mercado Pago é só um aviso de que algo
mudou — ela não deve ser usada como prova de pagamento sozinha. O código
aqui sempre busca o pagamento de novo diretamente na API do Mercado Pago
antes de liberar o pedido (ver consultar_pagamento).
"""
from __future__ import annotations

import mercadopago

from .config import settings

_sdk: "mercadopago.SDK | None" = None


def _client() -> "mercadopago.SDK":
    global _sdk
    if not settings.mercadopago_access_token:
        raise RuntimeError(
            "MERCADOPAGO_ACCESS_TOKEN não configurado — defina no .env para "
            "gerar cobranças reais (veja README: Mercado Pago)."
        )
    if _sdk is None:
        _sdk = mercadopago.SDK(settings.mercadopago_access_token)
    return _sdk


def criar_preferencia(
    pedido_id: str,
    cliente_nome: str,
    cliente_email: str,
    base_url: str,
) -> dict:
    """Cria a preferência de checkout no Mercado Pago.

    base_url é a origem pública do site (ex. "https://concorrencia.vmai.com.br"
    em produção, "http://localhost:8000" em desenvolvimento) — usada para
    montar as URLs de retorno e a URL de notificação (webhook).

    Devolve {"id": ..., "init_point": ...}; init_point é a URL de checkout
    para a qual o navegador do cliente deve ser redirecionado.
    """
    preferencia = {
        "items": [
            {
                "title": f"{settings.nome_produto} — {cliente_nome}",
                "quantity": 1,
                "unit_price": settings.preco_relatorio_centavos / 100,
                "currency_id": "BRL",
            }
        ],
        "payer": {"email": cliente_email},
        "external_reference": pedido_id,
        "back_urls": {
            "success": f"{base_url}/pedidos/{pedido_id}/sucesso",
            "pending": f"{base_url}/pedidos/{pedido_id}/pendente",
            "failure": f"{base_url}/pedidos/{pedido_id}/falha",
        },
        "auto_return": "approved",
        "notification_url": f"{base_url}/api/webhooks/mercadopago",
        "statement_descriptor": settings.nome_agencia[:22],
    }
    resposta = _client().preference().create(preferencia)
    if resposta["status"] >= 300:
        raise RuntimeError(
            f"Mercado Pago recusou a criação da preferência de pagamento: {resposta['response']}"
        )
    corpo = resposta["response"]
    return {"id": corpo["id"], "init_point": corpo["init_point"]}


def consultar_pagamento(payment_id: str) -> dict:
    """Busca o pagamento diretamente na API do Mercado Pago a partir do id
    recebido na notificação — nunca confiar apenas no corpo/query da
    notificação em si, que é só um aviso para ir conferir."""
    resposta = _client().payment().get(payment_id)
    if resposta["status"] >= 300:
        raise RuntimeError(
            f"Não foi possível consultar o pagamento {payment_id} no Mercado Pago: {resposta['response']}"
        )
    return resposta["response"]
