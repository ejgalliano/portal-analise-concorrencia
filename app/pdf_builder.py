"""
Monta o relatório final em PDF, com design completo (capa, cores da
marca, selos coloridos no mapa de oportunidade, tipografia cuidada).

Substitui o antigo docx_builder.py como formato de entrega padrão —
ver README.md para a decisão e o porquê. Este módulo só RENDERIZA: todo
o texto já vem pronto do generator.py, e o estilo visual vive inteiro
em app/static/relatorio.css (trocar cor/identidade = editar só esse
arquivo, não este código).
"""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .column_labels import rotulo_coluna
from .config import settings
from .report_frentes import FRENTES

_BASE_DIR = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(_BASE_DIR / "templates"))
_env.filters["rotulo_coluna"] = rotulo_coluna


_MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_por_extenso(momento: datetime) -> str:
    # Não depende de locale pt-BR estar configurada no servidor.
    return f"{momento.day} de {_MESES_PT[momento.month - 1]} de {momento.year}"


def montar_pdf(
    cliente_nome: str,
    resultados: dict[str, dict],
    secoes_gerais: dict,
    caminho_saida: str,
) -> str:
    template = _env.get_template("relatorio.html")
    css = (_BASE_DIR / "static" / "relatorio.css").read_text(encoding="utf-8")

    html_renderizado = template.render(
        cliente_nome=cliente_nome,
        nome_agencia=settings.nome_agencia,
        nome_produto=settings.nome_produto,
        data_geracao=_data_por_extenso(datetime.now()),
        resultados=resultados,
        secoes=secoes_gerais,
        frentes=FRENTES,
        css=css,
    )

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_renderizado, base_url=str(_BASE_DIR)).write_pdf(caminho_saida)
    return caminho_saida
