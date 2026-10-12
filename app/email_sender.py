"""
Envio do relatório pronto por e-mail, via Resend (API simples, boa opção
para começar — trocar de provedor é isolado neste arquivo).

Fase 1: e-mail. WhatsApp entra depois, como uma segunda função de envio
(send_whatsapp), quando a GZ tiver acesso à API oficial do WhatsApp
Business (Meta Cloud API ou via um BSP como Twilio) — o restante do
sistema não precisa mudar para isso, só o endpoint chama as duas
funções de envio em vez de uma.

O envio por e-mail é opcional: a entrega principal do relatório é o
download direto na página de retorno (ver /pedidos/{id}/download em
main.py). Se RESEND_API_KEY não estiver configurada no .env, esta
função não faz nada — não é um erro, é a entrega por e-mail
simplesmente desligada.
"""
import base64
import logging
from pathlib import Path

import resend

from .config import settings

log = logging.getLogger("portal-analise-concorrencia")

resend.api_key = settings.resend_api_key


def enviar_relatorio_por_email(destinatario: str, nome_cliente: str, caminho_relatorio: str) -> None:
    if not settings.resend_api_key:
        log.info("RESEND_API_KEY não configurada — envio por e-mail desligado, entrega é só por download.")
        return

    conteudo = Path(caminho_relatorio).read_bytes()
    anexo_base64 = base64.b64encode(conteudo).decode("utf-8")

    resend.Emails.send(
        {
            "from": f"{settings.email_nome_remetente} <{settings.email_remetente}>",
            "to": [destinatario],
            "subject": f"Seu relatório de análise de concorrência — {nome_cliente}",
            "html": (
                f"<p>Olá,</p>"
                f"<p>Seu relatório de análise de concorrência para <strong>{nome_cliente}</strong> "
                f"está pronto e segue em anexo.</p>"
                f"<p>Qualquer dúvida, é só responder este e-mail.</p>"
                f"<p>{settings.nome_agencia}</p>"
            ),
            "attachments": [
                {
                    "filename": Path(caminho_relatorio).name,
                    "content": anexo_base64,
                }
            ],
        }
    )
