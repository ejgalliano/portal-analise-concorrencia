"""
Motor de geração do relatório.

Duas etapas, cada uma uma chamada à API da Anthropic com a ferramenta
de busca web (server-side — a Anthropic pesquisa e devolve o resultado
já dentro da mesma resposta, sem loop manual de tool-use):

  1) pesquisar_empresa()      — uma chamada por empresa (cliente e cada
                                 concorrente), pesquisando as 13 frentes.
  2) sintetizar_secoes_gerais() — uma chamada final que recebe os dados
                                 brutos de todas as empresas e produz as
                                 seções comparativas (sumário executivo,
                                 comparativo consolidado, painéis, mapa
                                 de oportunidade, fontes citadas).

Em ambas, a regra de zero interpretação (REGRA_ZERO_INTERPRETACAO) vai
no system prompt, e a saída é sempre pedida em JSON estrito para que o
docx_builder só precise renderizar — nunca redigir.

IMPORTANTE: este motor depende de ANTHROPIC_API_KEY configurada e de
acesso à ferramenta "web_search" habilitado na conta da Anthropic
(platform.claude.com → Console). Sem isso, as chamadas abaixo falham.
"""
from __future__ import annotations

import json
import re

import anthropic

from .config import settings
from .models import Empresa
from .report_frentes import FRENTES, REGRA_ZERO_INTERPRETACAO

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _extrair_json(texto: str) -> dict:
    """Extrai o primeiro bloco JSON válido da resposta do modelo (tolera
    que o modelo tenha envolvido o JSON em ```json ... ``` ou em texto)."""
    bloco = re.search(r"\{.*\}", texto, re.DOTALL)
    if not bloco:
        raise ValueError("A resposta do modelo não contém um bloco JSON reconhecível.")
    return json.loads(bloco.group(0))


def _prompt_frentes() -> str:
    linhas = []
    for f in FRENTES:
        pontos = "; ".join(f["pontos"])
        fontes = ", ".join(f["fontes_tipicas"])
        linhas.append(
            f"{f['numero']}. {f['titulo']} — pesquisar: {pontos}. "
            f"Fontes típicas: {fontes}."
        )
    return "\n".join(linhas)


def pesquisar_empresa(empresa: Empresa, papel: str) -> dict:
    """
    papel: "cliente" ou "concorrente" — só muda o texto do prompt, a
    profundidade da pesquisa é idêntica para todas as empresas (regra
    de imparcialidade: o cliente é pesquisado com o mesmo rigor que os
    concorrentes).

    Retorna um dict:
      {
        "1": {"texto": "...", "fontes": [{"nome": "...", "url": "...", "data": "..."}]},
        "2": {...},
        ...
        "13": {...}
      }
    """
    ancoras = []
    if empresa.site:
        ancoras.append(f"site {empresa.site}")
    if empresa.instagram:
        ancoras.append(f"Instagram {empresa.instagram}")
    if empresa.facebook:
        ancoras.append(f"Facebook {empresa.facebook}")
    ancoras_txt = "; ".join(ancoras) if ancoras else "nenhuma âncora digital informada"

    system = (
        "Você é um pesquisador factual que produz insumos para um relatório de "
        "análise de concorrência. " + REGRA_ZERO_INTERPRETACAO + "\n\n"
        "Use a ferramenta de busca web para verificar cada informação antes de "
        "registrá-la. Nunca invente ou deduza dados que não conseguiu confirmar — "
        "nesses casos, registre explicitamente como não confirmado/não acessível "
        "nesta consulta, indicando a tentativa de fonte mesmo sem sucesso. Sempre "
        "que uma rede social, ferramenta de anúncios ou diretório bloquear a "
        "leitura automatizada (robots.txt, exigência de login, renderização via "
        "JavaScript), registre isso como fato de coleta, não como avaliação da "
        "empresa."
    )

    prompt = (
        f"Empresa a pesquisar ({papel}): {empresa.nome}.\n"
        f"Âncoras digitais informadas: {ancoras_txt}.\n"
        f"CNPJ informado: {empresa.cnpj or 'não informado'}.\n\n"
        "Pesquise as 13 frentes abaixo e devolva SOMENTE um JSON válido, sem "
        "nenhum texto fora do JSON, no formato:\n"
        '{"1": {"texto": "...", "fontes": [{"nome": "...", "url": "...", "data": "DD/MM/AAAA"}]}, '
        '"2": {...}, ..., "13": {...}}\n\n'
        "Cada campo \"texto\" deve ser um parágrafo denso e factual (no estilo: "
        "'Instagram: 890 seguidores, 3 posts/30 dias...'), terminando com a "
        "citação de fonte(s) entre colchetes. Frentes:\n\n" + _prompt_frentes()
    )

    resposta = _get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 40}],
    )

    texto_final = "".join(
        bloco.text for bloco in resposta.content if getattr(bloco, "type", None) == "text"
    )
    return _extrair_json(texto_final)


def sintetizar_secoes_gerais(cliente_nome: str, resultados: dict[str, dict]) -> dict:
    """
    resultados: {"<nome da empresa>": {"papel": "cliente"|"concorrente", "frentes": {...}}}

    Retorna um dict com as seções gerais do relatório, já prontas para o
    docx_builder renderizar:
      {
        "sumario_executivo": "texto...",
        "metodologia_e_fontes": "texto...",
        "comparativo_consolidado": [{"frente": "...", "linhas": [{"empresa": "...", "resumo": "..."}]}],
        "painel_reputacao_sinais_br": [{"empresa": "...", "colunas": {...}}],
        "painel_atividade_marketing_digital": [{"empresa": "...", "colunas": {...}}],
        "mapa_oportunidade_comparativo": [{"canal": "...", "empresas": {"nome": "✓"|"—"|"n/d"}}],
        "fontes_citadas": [{"nome": "...", "url": "...", "data": "..."}],
        "sobre_atualizacoes": "texto..."
      }
    """
    system = (
        "Você sintetiza seções comparativas de um relatório de análise de "
        "concorrência a partir de dados já pesquisados (não pesquise nada de "
        "novo, não tem ferramenta de busca nesta etapa). " + REGRA_ZERO_INTERPRETACAO
    )

    prompt = (
        f"Empresa cliente: {cliente_nome}. Dados brutos pesquisados de todas as "
        "empresas (cliente e concorrentes), por frente:\n\n"
        + json.dumps(resultados, ensure_ascii=False, indent=2)
        + "\n\nProduza SOMENTE um JSON válido, sem texto fora do JSON, com esta "
        "estrutura exata:\n"
        "{\n"
        '  "sumario_executivo": "3-5 parágrafos objetivos descrevendo o que foi coletado, sem juízo de valor",\n'
        '  "metodologia_e_fontes": "parágrafos explicando fontes usadas e limitações reais de coleta encontradas",\n'
        '  "comparativo_consolidado": [{"frente": "Nome da frente", "linhas": [{"empresa": "...", "resumo": "1-2 frases factuais"}]}],\n'
        '  "painel_reputacao_sinais_br": [{"empresa": "...", "colunas": {"reclame_aqui": "...", "google_meu_negocio": "...", "mencoes": "..."}}],\n'
        '  "painel_atividade_marketing_digital": [{"empresa": "...", "colunas": {"seguidores_instagram": "...", "posts_30_dias": "...", "anuncios_ativos": "..."}}],\n'
        '  "mapa_oportunidade_comparativo": [{"canal": "Nome do canal/frente", "empresas": {"Nome da empresa": "✓ ou — ou n/d"}}],\n'
        '  "fontes_citadas": [{"nome": "...", "url": "...", "data": "DD/MM/AAAA"}],\n'
        '  "sobre_atualizacoes": "parágrafo curto explicando que este é um retrato datado, e atualização é adquirida avulsamente"\n'
        "}\n\n"
        "Use ✓ quando o canal/frente foi confirmado como presente, — quando foi "
        "confirmado como ausente, e n/d quando não pôde ser determinado nesta "
        "consulta — nunca omita uma empresa de uma linha do mapa."
    )

    resposta = _get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=8000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    texto_final = "".join(
        bloco.text for bloco in resposta.content if getattr(bloco, "type", None) == "text"
    )
    return _extrair_json(texto_final)


def gerar_relatorio_completo(cliente, concorrentes) -> tuple[dict, dict]:
    """
    Orquestra a pesquisa de todas as empresas + a síntese das seções
    gerais. Retorna (resultados_por_empresa, secoes_gerais).
    """
    resultados: dict[str, dict] = {}

    resultados[cliente.nome] = {
        "papel": "cliente",
        "frentes": pesquisar_empresa(cliente, "cliente"),
    }
    for concorrente in concorrentes:
        resultados[concorrente.nome] = {
            "papel": "concorrente",
            "frentes": pesquisar_empresa(concorrente, "concorrente"),
        }

    secoes_gerais = sintetizar_secoes_gerais(cliente.nome, resultados)
    return resultados, secoes_gerais
