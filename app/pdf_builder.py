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


# Colunas fixas esperadas em cada painel — usadas por _sanear_secoes para
# preencher "n/d" se o modelo, por algum motivo, omitir uma delas (a API
# não garante 100% os campos "required" do schema sem modo strict). Sem
# isso, o template quebraria com UndefinedError ao chamar .colunas.keys()
# no primeiro item, se "colunas" (ou uma de suas chaves) estiver ausente.
_COLUNAS_REPUTACAO = ["reclame_aqui", "google_meu_negocio", "mencoes"]
_COLUNAS_ATIVIDADE = ["seguidores_instagram", "posts_30_dias", "anuncios_ativos"]


def _sanear_painel(lista, colunas_esperadas: list[str]) -> list[dict]:
    """Garante que cada item tem 'empresa' e 'colunas' com exatamente as
    chaves esperadas, na mesma ordem, preenchendo 'n/d' onde faltar —
    nunca deixa o template ler uma chave ausente."""
    saneado = []
    for item in lista or []:
        colunas_originais = (item or {}).get("colunas") or {}
        saneado.append({
            "empresa": (item or {}).get("empresa", "—"),
            "colunas": {c: colunas_originais.get(c, "n/d") for c in colunas_esperadas},
        })
    return saneado


def _sanear_secoes(secoes_gerais: dict) -> dict:
    """Normaliza as seções gerais antes de renderizar, preenchendo
    valores padrão para qualquer campo que o modelo tenha omitido —
    defesa extra além do schema da tool (ver generator.py), para o PDF
    nunca quebrar por um JSON incompleto."""
    secoes_gerais = secoes_gerais or {}
    return {
        "sumario_executivo": secoes_gerais.get("sumario_executivo") or "",
        "metodologia_e_fontes": secoes_gerais.get("metodologia_e_fontes") or "",
        "comparativo_consolidado": [
            {
                "frente": (bloco or {}).get("frente", "—"),
                "linhas": [
                    {"empresa": (linha or {}).get("empresa", "—"), "resumo": (linha or {}).get("resumo", "—")}
                    for linha in (bloco or {}).get("linhas") or []
                ],
            }
            for bloco in secoes_gerais.get("comparativo_consolidado") or []
        ],
        "painel_reputacao_sinais_br": _sanear_painel(secoes_gerais.get("painel_reputacao_sinais_br"), _COLUNAS_REPUTACAO),
        "painel_atividade_marketing_digital": _sanear_painel(secoes_gerais.get("painel_atividade_marketing_digital"), _COLUNAS_ATIVIDADE),
        "mapa_oportunidade_comparativo": [
            {"canal": (item or {}).get("canal", "—"), "empresas": (item or {}).get("empresas") or {}}
            for item in secoes_gerais.get("mapa_oportunidade_comparativo") or []
        ],
        "fontes_citadas": [
            {"nome": (f or {}).get("nome", "—"), "url": (f or {}).get("url", ""), "data": (f or {}).get("data", "—")}
            for f in secoes_gerais.get("fontes_citadas") or []
        ],
        "sobre_atualizacoes": secoes_gerais.get("sobre_atualizacoes") or "",
    }


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
        secoes=_sanear_secoes(secoes_gerais),
        frentes=FRENTES,
        css=css,
        # Lista canônica de nomes de empresa (do pedido, não do que o
        # modelo escreveu) — usada no mapa de oportunidade para que a
        # tabela nunca desalinhe/quebre se o modelo grafar um nome de
        # empresa de um jeito levemente diferente do original.
        nomes_empresas=list(resultados.keys()),
    )

    Path(caminho_saida).parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_renderizado, base_url=str(_BASE_DIR)).write_pdf(caminho_saida)
    return caminho_saida
