"""
Linter de rigor — a "rede de segurança" automática da regra de zero
interpretação.

Isto existe porque, na construção manual do modelo e da simulação com
dados reais (NBG Telecom, set/2026), o próprio processo de revisão
encontrou várias vezes linguagem interpretativa/autorreferente que
tinha escapado numa primeira redação (ex.: comparações com o "exemplo
fictício", frases como "sem tentativa de resolver a divergência",
parágrafos analisando a própria adaptação do relatório). Cada uma
dessas correções virou um padrão proibido aqui, para que o sistema
nunca precise de uma correção manual para o mesmo tipo de erro.

Este linter NÃO substitui revisão humana em uma fase inicial — ele
é a primeira barreira, que bloqueia a liberação automática do
relatório e devolve para checagem manual antes de entregar ao cliente.
"""
import re
from dataclasses import dataclass


@dataclass
class Ocorrencia:
    padrao: str
    trecho: str


# Cada padrão é uma regex (case-insensitive) + uma explicação curta do
# porquê está proibido. Baseado literalmente nas correções feitas em
# 19/09/2026 no relatório de simulação da NBG Telecom.
PADROES_PROIBIDOS: list[tuple[str, str]] = [
    (r"\bresolv\w*", "linguagem de 'resolução' de divergência — implica análise/julgamento"),
    (r"\bsem tentativa de\b", "comentário sobre o próprio processo do relatório"),
    (r"fict[ií]ci[oa]", "comparação com o modelo/exemplo fictício — não cabe no relatório oficial"),
    (r"documento[- ]modelo", "referência ao documento-modelo — não cabe no relatório oficial"),
    (r"\bcorreç\w*", "linguagem de correção/ajuste — é avaliação, não apresentação de fato"),
    (r"\bl[ií]der\w*", "juízo de valor de liderança/posição competitiva"),
    (r"\bfragil\w*", "juízo de valor sobre fraqueza"),
    (r"\bforte\w*\s+(concorrente|posicionamento|presença)", "juízo de valor de força competitiva"),
    (r"\brecomend\w*", "recomendação — o relatório não sugere ação"),
    (r"\bdeveria\b|\bdevia\b", "sugestão de ação"),
    (r"\bmelhor\s+(que|do que)\b", "comparação avaliativa entre empresas"),
    (r"\bpior\s+(que|do que)\b", "comparação avaliativa entre empresas"),
    (r"\badapta[çc][ãa]o setorial\b", "comentário meta sobre a construção do relatório"),
]

_COMPILADOS = [(re.compile(p, re.IGNORECASE), motivo) for p, motivo in PADROES_PROIBIDOS]


def checar_texto(texto: str) -> list[Ocorrencia]:
    """Retorna todas as ocorrências de linguagem proibida encontradas no texto."""
    ocorrencias: list[Ocorrencia] = []
    for regex, motivo in _COMPILADOS:
        for m in regex.finditer(texto):
            inicio = max(0, m.start() - 40)
            fim = min(len(texto), m.end() + 40)
            trecho = texto[inicio:fim].replace("\n", " ").strip()
            ocorrencias.append(Ocorrencia(padrao=motivo, trecho=f"…{trecho}…"))
    return ocorrencias


def checar_relatorio(secoes_texto: dict[str, str]) -> list[str]:
    """
    Roda o linter sobre todas as seções de texto do relatório (dict
    nome_da_secao -> texto) e devolve uma lista legível de avisos.
    Lista vazia = passou limpo.
    """
    avisos: list[str] = []
    for nome_secao, texto in secoes_texto.items():
        for ocorrencia in checar_texto(texto):
            avisos.append(f"[{nome_secao}] {ocorrencia.padrao} — trecho: {ocorrencia.trecho}")
    return avisos
