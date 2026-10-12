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
import logging
import re

import anthropic

log = logging.getLogger("portal-analise-concorrencia")

from .config import settings
from .models import Empresa
from .report_frentes import FRENTES, REGRA_ZERO_INTERPRETACAO

_client: anthropic.Anthropic | None = None

# Preços oficiais por milhão de tokens (USD) — platform.claude.com/docs/en/about-claude/pricing,
# consultado em 12/10/2026. Atualize aqui se os preços mudarem; o cálculo
# de custo é só uma estimativa para acompanhar o gasto, não é usado para
# cobrar o cliente.
_PRECOS_POR_MILHAO_USD = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0},
    "claude-opus-5": {"input": 5.0, "output": 25.0},
    "claude-opus-4-8": {"input": 5.0, "output": 25.0},
    "claude-opus-4-5": {"input": 5.0, "output": 25.0},
    "claude-opus-4-1": {"input": 15.0, "output": 75.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0},
    "claude-sonnet-5": {"input": 2.0, "output": 10.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
}
_PRECO_BUSCA_WEB_USD_POR_MIL = 10.0

# Teto de buscas web por CHAMADA à API (não por pedido inteiro) — cada
# chamada de pesquisar_empresa/sintetizar_secoes_gerais que usa a tool de
# busca pode fazer no máximo isso. Antes era 40 (US$ 0,40/chamada só de
# busca); 10 trava isso em US$ 0,10/chamada. Decisão de Emerson, 12/10/2026,
# após um teste que custou US$ 5 por um bug de dimensionamento (ver
# _chamar_ate_tool e CustoExcedidoError).
_MAX_BUSCAS_POR_CHAMADA = 10


class CustoExcedidoError(RuntimeError):
    """O custo estimado acumulado deste pedido passou do teto configurado
    (settings.custo_maximo_usd) — aborta o pedido imediatamente em vez de
    continuar gastando. Decisão de Emerson, 12/10/2026: nenhum pedido deve
    custar mais que o teto, nem em caso de bug ou comportamento inesperado
    do modelo."""


def _uso_vazio() -> dict:
    return {"chamadas": 0, "input_tokens": 0, "output_tokens": 0, "web_search_requests": 0}


def _somar_uso(acumulado: dict, resposta) -> None:
    acumulado["chamadas"] += 1
    uso = resposta.usage
    acumulado["input_tokens"] += uso.input_tokens or 0
    acumulado["output_tokens"] += uso.output_tokens or 0
    if uso.server_tool_use:
        acumulado["web_search_requests"] += uso.server_tool_use.web_search_requests or 0


def calcular_custo_estimado_usd(uso: dict, modelo: str) -> float | None:
    """Estimativa de custo em USD a partir do uso acumulado — None se o
    modelo não estiver na tabela de preços conhecida (atualize
    _PRECOS_POR_MILHAO_USD nesse caso)."""
    precos = _PRECOS_POR_MILHAO_USD.get(modelo)
    if precos is None:
        return None
    custo_tokens = (
        uso["input_tokens"] / 1_000_000 * precos["input"]
        + uso["output_tokens"] / 1_000_000 * precos["output"]
    )
    custo_busca = uso["web_search_requests"] / 1_000 * _PRECO_BUSCA_WEB_USD_POR_MIL
    return round(custo_tokens + custo_busca, 4)


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _extrair_json(texto: str) -> dict:
    """Extrai o primeiro bloco JSON válido da resposta do modelo (tolera
    que o modelo tenha envolvido o JSON em ```json ... ``` ou em texto).

    Usado só como ÚLTIMO recurso, se o modelo não chamar a tool de saída
    estruturada (ver _extrair_tool_input) — pedir para o modelo escrever
    um JSON gigante como texto livre é frágil: basta uma aspas não
    escapada dentro de um parágrafo pesquisado (comum, já que o texto
    vem de pesquisa web) para quebrar o parsing. As funções de pesquisa
    evitam depender disso sempre que possível."""
    bloco = re.search(r"\{.*\}", texto, re.DOTALL)
    if not bloco:
        raise ValueError("A resposta do modelo não contém um bloco JSON reconhecível.")
    return json.loads(bloco.group(0))


def _buscar_tool_use(resposta, nome_tool: str):
    for bloco in resposta.content:
        if getattr(bloco, "type", None) == "tool_use" and bloco.name == nome_tool:
            return bloco
    return None


def _extrair_tool_input(resposta, nome_tool: str) -> dict:
    """Pega o input (já validado contra o schema pela própria API — sem
    risco de JSON malformado) da chamada à tool de saída estruturada
    `nome_tool`. Se o modelo não chamou a tool (respondeu em texto livre
    por algum motivo), cai para _extrair_json no texto como reserva — isto
    só é chamado depois que _chamar_ate_tool já tentou insistir e mesmo
    assim não conseguiu, então aqui é realmente o último recurso."""
    bloco_tool = _buscar_tool_use(resposta, nome_tool)
    if bloco_tool is not None:
        return bloco_tool.input
    texto_final = "".join(
        bloco.text for bloco in resposta.content if getattr(bloco, "type", None) == "text"
    )
    tipos_blocos = [getattr(b, "type", "?") for b in resposta.content]
    log.warning(
        "Tool '%s' não foi chamada. stop_reason=%s, tipos_de_bloco=%s, trecho_do_texto=%r",
        nome_tool, resposta.stop_reason, tipos_blocos, texto_final[:1500],
    )
    if not texto_final:
        raise ValueError(f"O modelo não chamou a tool '{nome_tool}' nem devolveu texto para extrair JSON.")
    return _extrair_json(texto_final)


def _checar_teto_de_gasto(uso_acumulado: dict | None, model: str) -> None:
    """Freio de gasto: aborta o pedido imediatamente se o custo estimado
    acumulado já passou do teto (settings.custo_maximo_usd). Chamado depois
    de CADA chamada à API — não só no fim — para nunca deixar um pedido
    ultrapassar o teto, mesmo em caso de bug ou de o modelo fazer muito
    mais buscas/tokens do que o esperado."""
    if uso_acumulado is None:
        return
    custo_atual = calcular_custo_estimado_usd(uso_acumulado, model)
    if custo_atual is not None and custo_atual > settings.custo_maximo_usd:
        raise CustoExcedidoError(
            f"Custo estimado acumulado (US$ {custo_atual:.4f}) passou do teto "
            f"configurado (US$ {settings.custo_maximo_usd:.2f}) — pedido abortado "
            "para não gastar mais."
        )


def _chamar_ate_tool(
    *, system: str, mensagens: list, tools: list, nome_tool: str, max_tokens: str | int,
    model: str, uso_acumulado: dict | None, max_tentativas: int = 2,
    validar=None,
) -> dict:
    """Chama a API e garante (dentro do razoável) que a tool `nome_tool` seja
    chamada antes de desistir — sem jogar fora pesquisa já paga.

    A Anthropic não garante que o modelo sempre termine chamando uma tool
    específica (ver docs de tool_choice): às vezes ele responde só em
    texto. Em vez de falhar o pedido inteiro nessa hora (como acontecia
    antes — jogando fora toda a pesquisa já feita e seu custo), insiste
    numa nova mensagem na MESMA conversa, reaproveitando o que já foi
    apurado, em vez de recomeçar a pesquisa do zero.

    IMPORTANTE (ajustado em 12/10/2026 depois de um teste que custou US$ 5
    por causa de um bug de dimensionamento aqui): uma retomada de
    pause_turn NÃO é uma correção barata — ela devolve ao modelo o MESMO
    orçamento de buscas (até _MAX_BUSCAS_POR_CHAMADA) de novo, então cada
    retomada pode custar tanto quanto a chamada original. Por isso
    pause_turn só é retomado 1 vez (nunca mais, mesmo que max_tentativas
    seja maior) — depois disso, desiste e tenta extrair o que der. Além
    disso, o custo acumulado é checado depois de CADA chamada
    (_checar_teto_de_gasto), então mesmo esse único retry é interrompido
    na hora se passar do teto.

    `validar`, se passado, é uma função (dict) -> list[str] que recebe o
    input já devolvido pela tool e retorna uma lista de problemas
    encontrados (vazia = passou limpo). Existe porque a API só garante
    que os campos "required" do schema ESTEJAM PRESENTES, nunca que
    tenham conteúdo de verdade (nada impede o modelo de chamar a tool
    com strings/listas vazias e ainda assim passar na validação de
    schema) — foi exatamente isso que aconteceu num teste real em
    12/10/2026: a tool de síntese foi chamada corretamente, sem nenhum
    aviso, mas com todas as seções vazias, e o PDF saiu "pronto" sem
    conteúdo nenhum de comparativo. Se `validar` aponta problemas, é
    tratado como se a tool não tivesse sido chamada: insiste numa nova
    mensagem, descrevendo exatamente o que falta, reaproveitando a
    pesquisa já feita (sem precisar repetir buscas)."""
    client = _get_client()
    historico = list(mensagens)
    pause_turn_ja_retomado = False

    for tentativa in range(1, max_tentativas + 1):
        resposta = client.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=historico, tools=tools,
        )
        if uso_acumulado is not None:
            _somar_uso(uso_acumulado, resposta)
        _checar_teto_de_gasto(uso_acumulado, model)

        bloco_tool = _buscar_tool_use(resposta, nome_tool)
        if bloco_tool is not None:
            problemas = validar(bloco_tool.input) if validar is not None else []
            if not problemas:
                return bloco_tool.input

            log.warning(
                "Tentativa %d/%d: tool '%s' foi chamada mas o conteúdo não passou na "
                "validação: %s",
                tentativa, max_tentativas, nome_tool, "; ".join(problemas),
            )
            if tentativa == max_tentativas:
                # Esgotou as tentativas — entrega o que tem (incompleto é
                # melhor que erro, mas fica registrado em log para auditoria).
                return bloco_tool.input

            historico = historico + [
                {"role": "assistant", "content": resposta.content},
                {
                    "role": "user",
                    "content": (
                        f"Sua chamada à tool '{nome_tool}' foi registrada, mas está "
                        f"incompleta ou vazia nos seguintes pontos: {'; '.join(problemas)}. "
                        "Chame a tool novamente, agora com o conteúdo completo para "
                        "esses pontos — reaproveite a pesquisa que você já fez, só "
                        "pesquise de novo o que for estritamente necessário para "
                        "preencher o que falta."
                    ),
                },
            ]
            continue

        log.warning(
            "Tentativa %d/%d: tool '%s' não foi chamada (stop_reason=%s).",
            tentativa, max_tentativas, nome_tool, resposta.stop_reason,
        )

        if resposta.stop_reason == "pause_turn":
            if pause_turn_ja_retomado:
                # Já usamos a única retomada permitida — não insiste de novo
                # (isso recomeçaria outro orçamento de busca). Desiste aqui.
                break
            pause_turn_ja_retomado = True
            # pause_turn é a API pausando NO MEIO de uma busca web longa —
            # não é o modelo desistindo. O protocolo exige retomar enviando
            # o conteúdo da resposta pausada de volta tal como veio, sem
            # intercalar uma mensagem de usuário no meio (isso quebra o
            # par tool_use/tool_result da busca em andamento e a API
            # responde 400 "web_search tool use ... was found without a
            # corresponding web_search_tool_result block"). Só continua.
            historico = historico + [{"role": "assistant", "content": resposta.content}]
            continue

        if tentativa == max_tentativas:
            break

        historico = historico + [
            {"role": "assistant", "content": resposta.content},
            {
                "role": "user",
                "content": (
                    f"Você ainda não chamou a tool '{nome_tool}'. Pare de responder em texto "
                    f"livre e chame agora a tool '{nome_tool}' com os resultados que você já "
                    "apurou (não repita buscas que já fez, só registre o que já tem)."
                ),
            },
        ]

    # Esgotou as tentativas de insistir — último recurso, tenta extrair JSON
    # do texto da última resposta antes de desistir de vez.
    return _extrair_tool_input(resposta, nome_tool)


def _schema_frente() -> dict:
    return {
        "type": "object",
        "properties": {
            "texto": {
                "type": "string",
                "description": "Parágrafo denso e factual, terminando com a citação de fonte(s) entre colchetes.",
            },
            "fontes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "url": {"type": "string"},
                        "data": {"type": "string", "description": "DD/MM/AAAA"},
                    },
                    "required": ["nome", "url", "data"],
                },
            },
        },
        "required": ["texto", "fontes"],
    }


def _tool_registrar_pesquisa() -> dict:
    """Tool de saída estruturada para pesquisar_empresa — uma propriedade
    por frente (chave "1".."13", igual à estrutura que docx_builder e
    pdf_builder esperam). Gerada a partir de FRENTES para nunca
    dessincronizar do relatório real."""
    propriedades = {str(f["numero"]): _schema_frente() for f in FRENTES}
    return {
        "name": "registrar_pesquisa_empresa",
        "description": (
            "Registra o resultado da pesquisa das 13 frentes sobre a empresa. "
            "Chame esta tool UMA VEZ, só depois de terminar toda a pesquisa web."
        ),
        "input_schema": {
            "type": "object",
            "properties": propriedades,
            "required": [str(f["numero"]) for f in FRENTES],
        },
    }


_TOOL_REGISTRAR_SINTESE = {
    "name": "registrar_sintese",
    "description": "Registra as seções comparativas finais do relatório.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sumario_executivo": {
                "type": "string",
                "description": "3-5 parágrafos objetivos descrevendo o que foi coletado, sem juízo de valor.",
            },
            "metodologia_e_fontes": {
                "type": "string",
                "description": "Parágrafos explicando fontes usadas e limitações reais de coleta encontradas.",
            },
            "comparativo_consolidado": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "frente": {"type": "string"},
                        "linhas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "empresa": {"type": "string"},
                                    "resumo": {"type": "string", "description": "1-2 frases factuais."},
                                },
                                "required": ["empresa", "resumo"],
                            },
                        },
                    },
                    "required": ["frente", "linhas"],
                },
            },
            "painel_reputacao_sinais_br": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "empresa": {"type": "string"},
                        "colunas": {
                            "type": "object",
                            "properties": {
                                "reclame_aqui": {"type": "string"},
                                "google_meu_negocio": {"type": "string"},
                                "mencoes": {"type": "string"},
                            },
                            "required": ["reclame_aqui", "google_meu_negocio", "mencoes"],
                        },
                    },
                    "required": ["empresa", "colunas"],
                },
            },
            "painel_atividade_marketing_digital": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "empresa": {"type": "string"},
                        "colunas": {
                            "type": "object",
                            "properties": {
                                "seguidores_instagram": {"type": "string"},
                                "posts_30_dias": {"type": "string"},
                                "anuncios_ativos": {"type": "string"},
                            },
                            "required": ["seguidores_instagram", "posts_30_dias", "anuncios_ativos"],
                        },
                    },
                    "required": ["empresa", "colunas"],
                },
            },
            "mapa_oportunidade_comparativo": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "canal": {"type": "string"},
                        "empresas": {
                            "type": "object",
                            "description": "Mapa nome da empresa -> '✓' (presente), '—' (ausente) ou 'n/d' (não determinável). Nunca omita uma empresa.",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["canal", "empresas"],
                },
            },
            "fontes_citadas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "url": {"type": "string"},
                        "data": {"type": "string", "description": "DD/MM/AAAA"},
                    },
                    "required": ["nome", "url", "data"],
                },
            },
            "sobre_atualizacoes": {
                "type": "string",
                "description": "Parágrafo curto explicando que este é um retrato datado, e atualização é adquirida avulsamente.",
            },
        },
        "required": [
            "sumario_executivo",
            "metodologia_e_fontes",
            "comparativo_consolidado",
            "painel_reputacao_sinais_br",
            "painel_atividade_marketing_digital",
            "mapa_oportunidade_comparativo",
            "fontes_citadas",
            "sobre_atualizacoes",
        ],
    },
}


def _validar_pesquisa_empresa(resultado: dict) -> list[str]:
    """Confere que as 13 frentes vieram com texto de verdade — não só a
    chave presente. Sem isso, um frente que ficou sem orçamento de busca
    (teto de _MAX_BUSCAS_POR_CHAMADA) some silenciosamente do relatório
    em vez de aparecer como 'não pesquisado', e ninguém percebe."""
    problemas = []
    for f in FRENTES:
        chave = str(f["numero"])
        entrada = resultado.get(chave)
        if not isinstance(entrada, dict) or not (entrada.get("texto") or "").strip():
            problemas.append(f"frente {chave} ({f['titulo']}) sem texto")
    return problemas


def _validar_sintese(resultado: dict) -> list[str]:
    """Confere que as seções gerais vieram com conteúdo de verdade — a API
    só garante que os campos 'required' do schema existam, nunca que
    tenham texto/itens reais (uma string vazia ou lista vazia passa limpo
    no schema). Foi assim que um relatório real saiu com todas as seções
    comparativas em branco sem nenhum erro ou aviso, em 12/10/2026."""
    problemas = []
    for campo in ("sumario_executivo", "metodologia_e_fontes", "sobre_atualizacoes"):
        if not (resultado.get(campo) or "").strip():
            problemas.append(f"'{campo}' vazio")
    for campo in (
        "comparativo_consolidado", "painel_reputacao_sinais_br",
        "painel_atividade_marketing_digital", "mapa_oportunidade_comparativo",
        "fontes_citadas",
    ):
        if not resultado.get(campo):
            problemas.append(f"'{campo}' vazio")
    return problemas


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


def pesquisar_empresa(empresa: Empresa, papel: str, uso_acumulado: dict | None = None) -> dict:
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
        "Pesquise as 13 frentes abaixo. Cada campo \"texto\" deve ser um "
        "parágrafo denso e factual (no estilo: 'Instagram: 890 seguidores, "
        "3 posts/30 dias...'), terminando com a citação de fonte(s) entre "
        "colchetes. Quando terminar toda a pesquisa, chame a tool "
        "registrar_pesquisa_empresa com os 13 resultados de uma vez — não "
        "responda em texto livre. Frentes:\n\n" + _prompt_frentes()
    )

    return _chamar_ate_tool(
        system=system,
        mensagens=[{"role": "user", "content": prompt}],
        tools=[
            {"type": "web_search_20250305", "name": "web_search", "max_uses": _MAX_BUSCAS_POR_CHAMADA},
            _tool_registrar_pesquisa(),
        ],
        nome_tool="registrar_pesquisa_empresa",
        # 13 frentes com parágrafo denso + fontes cada uma é bastante
        # conteúdo de saída — 8000 tokens era curto e deixava a resposta
        # cortada antes de a tool ser chamada (sem tool_use, sem JSON, erro
        # de parsing). 16000 dá folga sem custo extra: max_tokens é só o
        # teto, o custo real é pelo que o modelo efetivamente gerar.
        max_tokens=16000,
        model=settings.anthropic_model,
        uso_acumulado=uso_acumulado,
        validar=_validar_pesquisa_empresa,
    )


def sintetizar_secoes_gerais(cliente_nome: str, resultados: dict[str, dict], uso_acumulado: dict | None = None) -> dict:
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
        + "\n\nChame a tool registrar_sintese com as seções comparativas finais "
        "— não responda em texto livre. Use ✓ quando o canal/frente foi "
        "confirmado como presente, — quando foi confirmado como ausente, e "
        "n/d quando não pôde ser determinado nesta consulta — nunca omita "
        "uma empresa de uma linha do mapa de oportunidade."
    )

    return _chamar_ate_tool(
        system=system,
        mensagens=[{"role": "user", "content": prompt}],
        tools=[_TOOL_REGISTRAR_SINTESE],
        nome_tool="registrar_sintese",
        max_tokens=12000,
        model=settings.anthropic_model,
        uso_acumulado=uso_acumulado,
        validar=_validar_sintese,
    )


def gerar_relatorio_completo(cliente, concorrentes) -> tuple[dict, dict, dict]:
    """
    Orquestra a pesquisa de todas as empresas + a síntese das seções
    gerais. Retorna (resultados_por_empresa, secoes_gerais, uso_ia), onde
    uso_ia acumula chamadas/tokens/buscas de todas as chamadas deste
    pedido e inclui "custo_estimado_usd" (None se o modelo não estiver em
    _PRECOS_POR_MILHAO_USD).
    """
    resultados: dict[str, dict] = {}
    uso = _uso_vazio()

    resultados[cliente.nome] = {
        "papel": "cliente",
        "frentes": pesquisar_empresa(cliente, "cliente", uso),
    }
    for concorrente in concorrentes:
        resultados[concorrente.nome] = {
            "papel": "concorrente",
            "frentes": pesquisar_empresa(concorrente, "concorrente", uso),
        }

    secoes_gerais = sintetizar_secoes_gerais(cliente.nome, resultados, uso)
    uso["custo_estimado_usd"] = calcular_custo_estimado_usd(uso, settings.anthropic_model)
    return resultados, secoes_gerais, uso


def _frente_simulada(numero: int, empresa_nome: str) -> dict:
    return {
        "texto": (
            f"Dado simulado de teste para a frente {numero} de {empresa_nome} — "
            "este texto é fictício, gerado sem chamar a API da Anthropic, só para "
            "validar o pipeline (linter, PDF, download) sem custo. Inclui uma "
            '"citação entre aspas" de propósito, para continuar cobrindo o caso '
            "que já quebrou o parsing antigo. [Fonte Simulada, 12/10/2026]"
        ),
        "fontes": [{"nome": "Fonte Simulada", "url": "https://exemplo.com", "data": "12/10/2026"}],
    }


def gerar_relatorio_completo_simulado(cliente, concorrentes) -> tuple[dict, dict, dict]:
    """Mesma assinatura/formato de retorno de gerar_relatorio_completo(), mas
    SEM nenhuma chamada à API da Anthropic — dados fictícios fixos.

    Existe só para testar o resto do pipeline (status/progresso, linter,
    montagem do PDF, download) de graça, de propósito, quantas vezes
    precisar, sem gastar tokens. Ativado via settings.simular_ia — ver
    config.py e o uso em main.py/processar_pedido.

    As pausas (time.sleep) são só para a tela de progresso ter algo visível
    para mostrar em cada etapa, como aconteceria numa pesquisa de verdade."""
    import time

    resultados: dict[str, dict] = {}

    empresas = [(cliente, "cliente")] + [(c, "concorrente") for c in concorrentes]
    for empresa, papel in empresas:
        time.sleep(2)
        resultados[empresa.nome] = {
            "papel": papel,
            "frentes": {str(f["numero"]): _frente_simulada(f["numero"], empresa.nome) for f in FRENTES},
        }

    time.sleep(1)
    secoes_gerais = {
        "sumario_executivo": "Resumo executivo simulado — sem chamada real à IA, só para teste de pipeline.",
        "metodologia_e_fontes": "Metodologia simulada para fins de teste.",
        "comparativo_consolidado": [
            {
                "frente": FRENTES[0]["titulo"],
                "linhas": [{"empresa": nome, "resumo": "Resumo factual simulado."} for nome in resultados],
            },
        ],
        "painel_reputacao_sinais_br": [
            {"empresa": nome, "colunas": {"reclame_aqui": "4,0", "google_meu_negocio": "4,5 (50)", "mencoes": "não encontrada"}}
            for nome in resultados
        ],
        "painel_atividade_marketing_digital": [
            {"empresa": nome, "colunas": {"seguidores_instagram": "1.000", "posts_30_dias": "5", "anuncios_ativos": "1"}}
            for nome in resultados
        ],
        "mapa_oportunidade_comparativo": [
            {"canal": "WhatsApp", "empresas": {nome: "✓" for nome in resultados}},
        ],
        "fontes_citadas": [{"nome": "Fonte Simulada", "url": "https://exemplo.com", "data": "12/10/2026"}],
        "sobre_atualizacoes": "Retrato datado simulado.",
    }

    uso = _uso_vazio()
    uso["custo_estimado_usd"] = 0.0
    uso["simulado"] = True
    return resultados, secoes_gerais, uso
