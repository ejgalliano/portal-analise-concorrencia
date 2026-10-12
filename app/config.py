"""
Configuração central do sistema — lê tudo de variáveis de ambiente.
Nada de chave/segredo fica hardcoded no código.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic (motor de pesquisa e redação do relatório)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    # E-mail transacional (Resend) — troque de provedor sem mexer no resto do sistema
    resend_api_key: str = ""
    email_remetente: str = "relatorios@seu-dominio.com.br"
    email_nome_remetente: str = "Portal de Análise de Concorrência"

    # Marca / textos fixos usados no relatório e nos e-mails
    nome_produto: str = "Portal de Análise de Concorrência"
    nome_agencia: str = "VMAI"

    # Armazenamento simples dos pedidos (troque por banco de dados quando escalar)
    orders_dir: str = "orders"

    # Pagamento (Mercado Pago — Checkout Pro). Preço simbólico de teste por
    # padrão (R$ 19,90); ajuste pelo .env sem mexer em código.
    mercadopago_access_token: str = ""
    preco_relatorio_centavos: int = 1990

    # Modo de teste: libera POST /api/pedidos/teste, que pula o pagamento.
    # Deixe DESLIGADO (False) assim que a integração com o Mercado Pago
    # estiver funcionando — é um atalho de validação, não um recurso para
    # produção.
    permitir_pedido_teste: bool = False

    # Modo simulado: quando ligado, o pedido de teste NÃO chama a API da
    # Anthropic — usa dados fictícios prontos (mesmo formato que a IA real
    # devolveria) e segue o resto do pipeline de verdade (linter, PDF,
    # download, tela de progresso). Custo: US$ 0,00. Serve pra testar
    # interface/fluxo/PDF à vontade sem gastar tokens. Ligue
    # SIMULAR_IA=true no Render para usar; desligue quando quiser validar
    # a pesquisa real de verdade (e aí sim vai custar tokens de propósito).
    simular_ia: bool = False


settings = Settings()
