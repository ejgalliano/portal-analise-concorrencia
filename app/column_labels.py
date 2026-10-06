"""
Mapa de rótulos amigáveis para as chaves técnicas que o generator.py usa
nas tabelas (colunas dos painéis). As chaves do JSON são snake_case sem
acento (ex.: "google_meu_negocio"); sem este mapa, o título exibido sai
sem acentuação ("Google Meu Negocio"). Usado por pdf_builder.py e
docx_builder.py.
"""

ROTULOS_COLUNAS = {
    "reclame_aqui": "Reclame Aqui",
    "google_meu_negocio": "Google Meu Negócio",
    "mencoes": "Menções",
    "seguidores_instagram": "Seguidores Instagram",
    "posts_30_dias": "Posts / 30 dias",
    "anuncios_ativos": "Anúncios ativos",
}


def rotulo_coluna(chave: str) -> str:
    if chave in ROTULOS_COLUNAS:
        return ROTULOS_COLUNAS[chave]
    # Fallback para chaves novas que o modelo venha a introduzir no futuro
    # (ainda sem acento, mas pelo menos legível).
    return chave.replace("_", " ").title()
