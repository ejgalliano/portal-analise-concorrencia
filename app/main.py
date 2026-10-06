"""
Aplicação principal — serve a página de vendas, o formulário de intake e a
API que recebe o pedido, cobra pelo Mercado Pago e, só depois de confirmado
o pagamento, gera o relatório e entrega por e-mail.

Rodar localmente:
    uvicorn app.main:app --reload

Fluxo de um pedido (pagamento real via Mercado Pago — Checkout Pro):
    1. Cliente conhece o produto em "/" (página de vendas) e vai para
       "/comprar" (formulário de intake)
    2. POST /api/pedidos cria o pedido (status "aguardando_pagamento"),
       cria uma preferência de checkout no Mercado Pago e devolve a URL
       de pagamento — o front redireciona o navegador para lá
    3. O cliente paga no Mercado Pago (cartão, PIX ou boleto) e é trazido
       de volta para /pedidos/{id}/sucesso|pendente|falha
    4. O Mercado Pago avisa o backend em paralelo via webhook
       (POST /api/webhooks/mercadopago) — é esse aviso, não o retorno do
       navegador, que efetivamente libera o pedido: o webhook confirma o
       pagamento direto na API do Mercado Pago e só então dispara
       processar_pedido() em background
    5. processar_pedido() pesquisa cada empresa, sintetiza as seções
       gerais, roda o linter de rigor, monta o PDF final (com design —
       ver pdf_builder.py) e envia por e-mail
    6. GET /api/pedidos/{id} permite ao próprio front consultar o status

O formato de entrega padrão é PDF (app/pdf_builder.py), com capa, cores
da marca e selos coloridos no mapa de oportunidade. app/docx_builder.py
continua no projeto como alternativa editável em Word, mas não é usado
neste fluxo — ver README para como trocar ou oferecer os dois formatos.
"""
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .email_sender import enviar_relatorio_por_email
from .generator import gerar_relatorio_completo
from .linter import checar_relatorio
from .models import Pedido, PedidoCreate
from .payment import consultar_pagamento, criar_preferencia
from .pdf_builder import montar_pdf
from . import storage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("portal-analise-concorrencia")

app = FastAPI(title=settings.nome_produto)

_BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=_BASE_DIR / "templates")

_CONTEXTO_BASE = {
    "nome_produto": settings.nome_produto,
    "nome_agencia": settings.nome_agencia,
    "preco_reais": f"{settings.preco_relatorio_centavos / 100:.2f}".replace(".", ","),
}


@app.get("/", response_class=HTMLResponse)
def pagina_vendas(request: Request):
    return templates.TemplateResponse(request, "vendas.html", dict(_CONTEXTO_BASE))


@app.get("/comprar", response_class=HTMLResponse)
def formulario(request: Request):
    return templates.TemplateResponse(request, "intake.html", dict(_CONTEXTO_BASE))


@app.get("/pedidos/{pedido_id}/sucesso", response_class=HTMLResponse)
def retorno_sucesso(request: Request, pedido_id: str):
    return templates.TemplateResponse(
        request, "retorno.html", {**_CONTEXTO_BASE, "pedido_id": pedido_id, "resultado": "sucesso"}
    )


@app.get("/pedidos/{pedido_id}/pendente", response_class=HTMLResponse)
def retorno_pendente(request: Request, pedido_id: str):
    return templates.TemplateResponse(
        request, "retorno.html", {**_CONTEXTO_BASE, "pedido_id": pedido_id, "resultado": "pendente"}
    )


@app.get("/pedidos/{pedido_id}/falha", response_class=HTMLResponse)
def retorno_falha(request: Request, pedido_id: str):
    return templates.TemplateResponse(
        request, "retorno.html", {**_CONTEXTO_BASE, "pedido_id": pedido_id, "resultado": "falha"}
    )


@app.post("/api/pedidos")
def criar_pedido(dados: PedidoCreate, request: Request):
    pedido = Pedido.novo(dados)
    base_url = str(request.base_url).rstrip("/")

    try:
        preferencia = criar_preferencia(
            pedido.id, pedido.cliente.nome, pedido.cliente.email_contato, base_url
        )
    except Exception as exc:  # noqa: BLE001 — queremos capturar e registrar qualquer falha do Mercado Pago
        log.exception("Falha ao criar preferência de pagamento para pedido %s", pedido.id)
        pedido.status = "erro"
        pedido.erro = str(exc)
        storage.salvar(pedido)
        raise HTTPException(status_code=502, detail=f"Não foi possível iniciar o pagamento: {exc}") from exc

    pedido.preference_id = preferencia["id"]
    pedido.checkout_url = preferencia["init_point"]
    storage.salvar(pedido)
    return {"id": pedido.id, "status": pedido.status, "checkout_url": pedido.checkout_url}


@app.get("/api/pedidos/{pedido_id}")
def consultar_pedido(pedido_id: str):
    pedido = storage.carregar(pedido_id)
    if pedido is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    return pedido


@app.api_route("/api/webhooks/mercadopago", methods=["GET", "POST"])
async def webhook_mercadopago(request: Request, background_tasks: BackgroundTasks):
    """Recebe o aviso do Mercado Pago de que um pagamento mudou de status.

    O aviso em si não é prova de nada — ele só diz "vá conferir o pagamento
    X" (consultar_pagamento busca o dado de verdade na API do Mercado Pago
    antes de qualquer pedido ser liberado).
    """
    params = request.query_params
    payment_id = params.get("data.id") or params.get("id")
    tipo = params.get("type") or params.get("topic")

    if not payment_id:
        try:
            corpo = await request.json()
        except Exception:
            corpo = {}
        payment_id = (corpo.get("data") or {}).get("id") or corpo.get("id")
        tipo = tipo or corpo.get("type") or corpo.get("topic")

    if tipo != "payment" or not payment_id:
        # Outros tipos de notificação (ex.: merchant_order) não nos interessam.
        return {"status": "ignorado"}

    try:
        pagamento = consultar_pagamento(str(payment_id))
    except Exception:
        log.exception("Falha ao consultar pagamento %s no Mercado Pago", payment_id)
        raise HTTPException(status_code=502, detail="Falha ao consultar pagamento.")

    pedido_id = pagamento.get("external_reference")
    status_pagamento = pagamento.get("status")  # approved | pending | rejected | cancelled | ...

    if not pedido_id:
        log.warning("Pagamento %s sem external_reference.", payment_id)
        return {"status": "sem_referencia"}

    pedido = storage.carregar(pedido_id)
    if pedido is None:
        log.warning("Pagamento %s referencia pedido inexistente %s.", payment_id, pedido_id)
        return {"status": "pedido_nao_encontrado"}

    pedido.payment_id = str(payment_id)

    if status_pagamento == "approved" and pedido.status == "aguardando_pagamento":
        pedido.status = "pago"
        storage.salvar(pedido)
        log.info("Pagamento aprovado para pedido %s — iniciando geração.", pedido_id)
        background_tasks.add_task(processar_pedido, pedido.id)
    elif status_pagamento in ("rejected", "cancelled") and pedido.status == "aguardando_pagamento":
        pedido.erro = f"Pagamento {status_pagamento}."
        storage.salvar(pedido)
    else:
        # Notificação repetida ou de um status intermediário (ex. pending) — só
        # registra o payment_id mais recente, sem repetir o processamento.
        storage.salvar(pedido)

    return {"status": "ok"}


def processar_pedido(pedido_id: str) -> None:
    pedido = storage.carregar(pedido_id)
    if pedido is None:
        log.error("Pedido %s sumiu antes do processamento.", pedido_id)
        return

    try:
        pedido.status = "pesquisando"
        storage.salvar(pedido)

        resultados, secoes_gerais = gerar_relatorio_completo(pedido.cliente, pedido.concorrentes)

        pedido.status = "verificando"
        storage.salvar(pedido)

        # Roda o linter de rigor sobre todo o texto gerado antes de liberar.
        textos_para_checar = {"sumario_executivo": secoes_gerais.get("sumario_executivo", "")}
        for nome_empresa, dados in resultados.items():
            for chave, entrada in dados.get("frentes", {}).items():
                textos_para_checar[f"{nome_empresa} — frente {chave}"] = entrada.get("texto", "")
        avisos = checar_relatorio(textos_para_checar)
        pedido.avisos_linter = avisos
        if avisos:
            log.warning("Pedido %s tem %d avisos do linter — revisão manual recomendada antes de reenviar.", pedido_id, len(avisos))

        pedido.status = "gerando_documento"
        storage.salvar(pedido)

        caminho_relatorio = str(Path(settings.orders_dir) / f"{pedido_id}.pdf")
        montar_pdf(pedido.cliente.nome, resultados, secoes_gerais, caminho_relatorio)
        pedido.caminho_relatorio = caminho_relatorio

        enviar_relatorio_por_email(pedido.cliente.email_contato, pedido.cliente.nome, caminho_relatorio)

        pedido.status = "pronto"
        storage.salvar(pedido)
        log.info("Pedido %s concluído e enviado para %s.", pedido_id, pedido.cliente.email_contato)

    except Exception as exc:  # noqa: BLE001 — queremos capturar e registrar qualquer falha do pipeline
        log.exception("Falha ao processar pedido %s", pedido_id)
        pedido.status = "erro"
        pedido.erro = str(exc)
        storage.salvar(pedido)
