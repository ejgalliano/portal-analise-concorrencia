"""
Modelos de dados do pedido — espelham exatamente as regras de intake
já validadas por Emerson em 18/09/2026:
  - nome da empresa obrigatório (cliente e cada concorrente)
  - pelo menos uma âncora digital (site OU Instagram OU Facebook) por
    concorrente, para evitar ambiguidade de identificação
  - CNPJ opcional, com explicação no formulário do motivo
  - sem campo de cidade/região
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class Empresa(BaseModel):
    nome: str
    site: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    cnpj: Optional[str] = None

    @field_validator("nome")
    @classmethod
    def nome_obrigatorio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Nome da empresa é obrigatório.")
        return v.strip()


class Concorrente(Empresa):
    @field_validator("site")
    @classmethod
    def ancora_digital_obrigatoria(cls, v, info):
        # Validação completa (pelo menos 1 âncora entre site/instagram/facebook)
        # é feita em PedidoCreate.validar_concorrentes, pois depende dos 3 campos.
        return v


class ClienteInfo(Empresa):
    email_contato: EmailStr


class PedidoCreate(BaseModel):
    cliente: ClienteInfo
    concorrentes: list[Concorrente]

    @field_validator("concorrentes")
    @classmethod
    def minimo_um_concorrente_com_ancora(cls, lista: list[Concorrente]) -> list[Concorrente]:
        if not lista:
            raise ValueError("Informe ao menos um concorrente.")
        for c in lista:
            if not (c.site or c.instagram or c.facebook):
                raise ValueError(
                    f"O concorrente '{c.nome}' precisa de ao menos uma âncora digital "
                    "(site, Instagram ou Facebook)."
                )
        return lista


class Pedido(BaseModel):
    id: str
    criado_em: datetime
    # aguardando_pagamento | pago | recebido | pesquisando | verificando |
    # gerando_documento | pronto | erro
    status: str
    cliente: ClienteInfo
    concorrentes: list[Concorrente]
    caminho_relatorio: Optional[str] = None
    avisos_linter: list[str] = []
    erro: Optional[str] = None

    # Uso real da API da Anthropic neste pedido — chamadas, tokens, buscas
    # web e custo estimado (ver app/generator.py). None até o pedido
    # terminar o processamento.
    uso_ia: Optional[dict] = None

    # Pagamento (Mercado Pago)
    preference_id: Optional[str] = None
    payment_id: Optional[str] = None
    checkout_url: Optional[str] = None

    # Token aleatório e imprevisível que autoriza o download do relatório —
    # separado do id do pedido para não depender da previsibilidade do id.
    download_token: str

    @staticmethod
    def novo(dados: PedidoCreate) -> "Pedido":
        return Pedido(
            id=str(uuid.uuid4()),
            criado_em=datetime.utcnow(),
            status="aguardando_pagamento",
            cliente=dados.cliente,
            concorrentes=dados.concorrentes,
            download_token=uuid.uuid4().hex,
        )
