"""
Armazenamento dos pedidos — implementação mínima em arquivo JSON por
pedido, suficiente para o volume de um MVP concierge (poucos pedidos
por semana). Trocar por um banco de dados real (Postgres, por exemplo)
é uma troca isolada: só este arquivo muda, o resto do sistema não sabe
como os pedidos são guardados.
"""
import json
from pathlib import Path

from .config import settings
from .models import Pedido

_ORDERS_DIR = Path(settings.orders_dir)
_ORDERS_DIR.mkdir(parents=True, exist_ok=True)


def _caminho(pedido_id: str) -> Path:
    return _ORDERS_DIR / f"{pedido_id}.json"


def salvar(pedido: Pedido) -> None:
    _caminho(pedido.id).write_text(pedido.model_dump_json(indent=2), encoding="utf-8")


def carregar(pedido_id: str) -> Pedido | None:
    caminho = _caminho(pedido_id)
    if not caminho.exists():
        return None
    return Pedido.model_validate_json(caminho.read_text(encoding="utf-8"))


def listar() -> list[Pedido]:
    pedidos = []
    for arquivo in sorted(_ORDERS_DIR.glob("*.json")):
        pedidos.append(Pedido.model_validate_json(arquivo.read_text(encoding="utf-8")))
    return pedidos
