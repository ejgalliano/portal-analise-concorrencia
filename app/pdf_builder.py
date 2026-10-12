"""
Monta o relatório final em PDF, com design completo (capa, cores da
marca, selos coloridos no mapa de oportunidade, tipografia cuidada).

Substitui o antigo docx_builder.py como formato de entrega padrão —
ver README.md para a decisão e o porquê. Este módulo só RENDERIZA: todo
o texto já vem pronto do generator.py, e o estilo visual vive inteiro
em app/static/relatorio.css (trocar cor/identidade = editar só esse
arquivo, não este código).
"""
import re
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


def _parsear_numero_ptbr(texto: str | None) -> float | None:
    """Extrai o primeiro número do texto, tolerando formatação pt-BR
    (milhar com ponto, decimal com vírgula) e abreviações como '13K'.
    Usado só para desenhar a barra comparativa ao lado do valor — o texto
    original é sempre mantido como está, isto nunca o substitui. Se não
    conseguir reconhecer um número com confiança, devolve None e a barra
    simplesmente não é desenhada para aquela célula (sem crashar e sem
    inventar número)."""
    if not texto:
        return None
    m = re.search(r"(\d[\d.,]*)\s*([kK])?", texto)
    if not m:
        return None
    bruto, sufixo_k = m.group(1), m.group(2)
    if "," in bruto:
        # pt-BR: vírgula é decimal, ponto é separador de milhar (7.415,30).
        numero = bruto.replace(".", "").replace(",", ".")
    elif bruto.count(".") == 1 and len(bruto.split(".")[1]) in (1, 2) and len(bruto.split(".")[0]) <= 3:
        # Caso ambíguo tipo "3.5" (nota em formato en-US, comum vindo de
        # fontes como Glassdoor/Indeed) — trata como decimal, não milhar.
        numero = bruto
    else:
        numero = bruto.replace(".", "")
    try:
        valor = float(numero)
    except ValueError:
        return None
    if sufixo_k:
        valor *= 1000
    return valor


_RE_NOTA_DE_5 = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*(?:de\s*5(?:\s*estrelas)?|/\s*5|★)", re.IGNORECASE)


def _parsear_nota_de_5(texto: str | None) -> float | None:
    """Parser DELIBERADAMENTE mais rígido que _parsear_numero_ptbr — só para
    colunas de nota em escala 0-5 (Reclame Aqui, Google Meu Negócio).

    Pegar 'o primeiro número do texto' é perigoso aqui: um texto como
    'Sem reputação definida (1 reclamação)' tem um número (1), mas não é
    uma nota — é a contagem de reclamações. _parsear_numero_ptbr pegaria
    esse 1 e desenharia uma barra de '1 de 5 estrelas' enganosa (bug
    encontrado e corrigido ainda em teste local, antes de qualquer custo
    de API). Por isso aqui só reconhece o padrão explícito de nota: 'X,Y
    de 5', 'X,Y de 5 estrelas' ou 'X,Y/5' — qualquer outro formato não
    gera barra, só mantém o texto."""
    if not texto:
        return None
    m = _RE_NOTA_DE_5.search(texto)
    if not m:
        return None
    try:
        valor = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return valor if 0 <= valor <= 5 else None


def _barra_pct(valor: float | None, maximo: float | None, teto: float | None) -> float | None:
    """Calcula o preenchimento (0-100) da barrinha comparativa: proporcional
    ao maior valor da coluna (sem teto fixo) ou à escala fixa informada
    (ex.: nota de 0 a 5). Se o valor for muito maior que o teto esperado
    (ex.: confundiu quantidade de avaliações com a nota em si), não
    desenha a barra — mais seguro que uma barra enganosa."""
    if valor is None:
        return None
    escala = teto if teto is not None else maximo
    if not escala or escala <= 0:
        return None
    if teto is not None and valor > teto * 1.5:
        return None
    return round(max(0.0, min(100.0, valor / escala * 100)), 1)


def _sanear_painel(
    lista, colunas_esperadas: list[str], config_barras: dict[str, dict] | None = None,
) -> list[dict]:
    """Garante que cada item tem 'empresa' e 'colunas' com exatamente as
    chaves esperadas, na mesma ordem, preenchendo 'n/d' onde faltar —
    nunca deixa o template ler uma chave ausente.

    Cada coluna listada em `config_barras` ganha também uma barra
    comparativa (colunas[c].barra_pct) calculada a partir do número
    reconhecido no texto, SEM alterar ou remover o texto original — é só
    um complemento visual para não deixar o painel inteiro em texto corrido.
    `config_barras[c] = {}` compara contra o maior valor da própria coluna;
    `{"teto": 5.0}` usa uma escala fixa (ex.: nota de 0 a 5)."""
    config_barras = config_barras or {}
    saneado = []
    for item in lista or []:
        colunas_originais = (item or {}).get("colunas") or {}
        colunas = {}
        for c in colunas_esperadas:
            texto = colunas_originais.get(c, "n/d")
            cfg_coluna = config_barras.get(c)
            if cfg_coluna is None:
                valor = None
            elif cfg_coluna.get("teto") is not None:
                # Coluna de nota em escala fixa (0-5) — usa o parser rígido,
                # que só reconhece o padrão explícito "X de 5"/"X/5" (ver
                # _parsear_nota_de_5 para o motivo).
                valor = _parsear_nota_de_5(texto)
            else:
                valor = _parsear_numero_ptbr(texto)
            colunas[c] = {"texto": texto, "valor": valor, "barra_pct": None}
        saneado.append({"empresa": (item or {}).get("empresa", "—"), "colunas": colunas})

    for c, cfg in config_barras.items():
        valores = [row["colunas"][c]["valor"] for row in saneado if row["colunas"][c]["valor"] is not None]
        maximo = max(valores) if valores else None
        for row in saneado:
            row["colunas"][c]["barra_pct"] = _barra_pct(row["colunas"][c]["valor"], maximo, cfg.get("teto"))

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
        "painel_reputacao_sinais_br": _sanear_painel(
            secoes_gerais.get("painel_reputacao_sinais_br"), _COLUNAS_REPUTACAO,
            # Reclame Aqui e Google Meu Negócio costumam vir como nota de 0 a
            # 5 ("4,2 de 5") — escala fixa. "Menções" é texto livre demais
            # (ex.: "não encontrada", "1.186 publicações") para virar barra
            # com confiança, por isso fica de fora.
            config_barras={"reclame_aqui": {"teto": 5.0}, "google_meu_negocio": {"teto": 5.0}},
        ),
        "painel_atividade_marketing_digital": _sanear_painel(
            secoes_gerais.get("painel_atividade_marketing_digital"), _COLUNAS_ATIVIDADE,
            # As 3 colunas de atividade são sempre contagens — comparação
            # proporcional ao maior valor entre as empresas do relatório.
            config_barras={"seguidores_instagram": {}, "posts_30_dias": {}, "anuncios_ativos": {}},
        ),
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
