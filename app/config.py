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


settings = Settings()
