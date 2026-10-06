"""
Especificação das 13 frentes de diagnóstico — a mesma estrutura validada
manualmente (modelo fictício + simulação com dados reais da NBG Telecom)
é reaproduzida aqui em formato de dados, para orientar a pesquisa
automática feita pelo motor de geração (generator.py).

Alterar o padrão do relatório = alterar este arquivo. Não deve existir
lógica de conteúdo espalhada pelo resto do código.
"""

FRENTES = [
    {
        "numero": 1,
        "titulo": "Identificação",
        "pontos": [
            "Razão social e nome fantasia",
            "CNAE principal e secundário",
            "Porte e capital social",
            "Quadro societário e data da última alteração",
            "Tempo de CNPJ ativo",
            "Tempo de domínio registrado (WHOIS)",
            "Registros/licenças de classe aplicáveis ao setor, se houver",
        ],
        "fontes_tipicas": ["Receita Federal (CNPJ)", "WHOIS do domínio", "conselhos de classe do setor, se aplicável"],
    },
    {
        "numero": 2,
        "titulo": "Site e conversão",
        "pontos": [
            "Formas de contato disponíveis no site (WhatsApp, telefone, formulário, e-mail)",
            "Agendamento online, chat ao vivo, blog",
            "Certificado SSL e responsividade mobile",
            "Velocidade mobile (PageSpeed Insights)",
            "Política de privacidade/LGPD",
            "Depoimentos publicados e selos de terceiros",
            "Botão de WhatsApp flutuante, mapa incorporado, FAQ",
        ],
        "fontes_tipicas": ["site institucional", "Google PageSpeed Insights"],
    },
    {
        "numero": 3,
        "titulo": "Redes sociais",
        "pontos": [
            "Instagram: seguidores, posts/30 dias, formato predominante, média de curtidas e comentários, destaques, link na bio, taxa de resposta a comentários, uso de hashtags",
            "Facebook: seguidores, data da última postagem, nota e número de avaliações",
            "TikTok, YouTube, LinkedIn, Pinterest: presença ou ausência de perfil",
        ],
        "fontes_tipicas": ["Instagram", "Facebook", "LinkedIn", "TikTok", "YouTube"],
    },
    {
        "numero": 4,
        "titulo": "SEO local",
        "pontos": [
            "Google Meu Negócio: nota, número de avaliações, fotos, posts publicados, % de avaliações respondidas, completude do cadastro",
            "Presença em diretórios do setor (ex.: Doctoralia para saúde), Bing Places, Apple Maps",
            "Consistência de nome/endereço/telefone entre site e diretórios",
        ],
        "fontes_tipicas": ["Google Meu Negócio", "diretórios setoriais", "Bing Places", "Apple Maps"],
    },
    {
        "numero": 5,
        "titulo": "Tráfego pago",
        "pontos": [
            "Anúncios ativos no Meta Ads Library (formato, CTA, data de início, destino)",
            "Anúncios ativos no Google Ads Transparency Center",
            "Anúncios ativos no TikTok Ads Library",
        ],
        "fontes_tipicas": ["Meta Ads Library", "Google Ads Transparency Center", "TikTok Ads Library"],
    },
    {
        "numero": 6,
        "titulo": "Reputação",
        "pontos": [
            "Reclame Aqui: nota, número de reclamações recentes, % respondidas",
            "Diretórios setoriais com sistema de avaliação",
            "Menções no Google News",
            "Marcações de clientes encontradas em busca pontual nas redes (deixar explícito que é uma checagem pontual, não monitoramento contínuo)",
        ],
        "fontes_tipicas": ["Reclame Aqui", "Google News", "Instagram/Facebook (busca de marcações)"],
    },
    {
        "numero": 7,
        "titulo": "Posicionamento declarado",
        "pontos": [
            "Texto da bio/descrição em cada rede social",
            "Diferenciais ou parcerias declaradas publicamente",
            "Presença e conteúdo de página no LinkedIn",
        ],
        "fontes_tipicas": ["site institucional", "Instagram", "Facebook", "LinkedIn"],
    },
    {
        "numero": 8,
        "titulo": "Vendas online",
        "pontos": [
            "Checkout, carrinho ou catálogo de produtos/serviços no site",
            "Divulgação pública de preços ou apenas 'sob consulta'",
        ],
        "fontes_tipicas": ["site institucional"],
    },
    {
        "numero": 9,
        "titulo": "Atendimento",
        "pontos": [
            "Canais de atendimento disponíveis e SLA declarado em cada um",
            "Tempo de resposta observado em uma checagem pontual (registrar data/hora da checagem)",
        ],
        "fontes_tipicas": ["WhatsApp Business", "site institucional"],
    },
    {
        "numero": 10,
        "titulo": "Conteúdo",
        "pontos": [
            "Blog: existência e frequência de posts recentes",
            "YouTube, podcast, e-book ou outro material de conteúdo próprio",
        ],
        "fontes_tipicas": ["site institucional", "YouTube", "redes sociais"],
    },
    {
        "numero": 11,
        "titulo": "Tecnologia do site",
        "pontos": [
            "Plataforma/CMS identificado (ex.: WordPress, Wix, plataforma proprietária)",
        ],
        "fontes_tipicas": ["site institucional (análise técnica pública)"],
    },
    {
        "numero": 12,
        "titulo": "Presença em apps e marketplaces",
        "pontos": [
            "Aplicativo próprio nas lojas (iOS/Android)",
            "Presença em marketplaces ou plataformas de agendamento/venda do setor",
        ],
        "fontes_tipicas": ["App Store", "Google Play", "marketplaces/plataformas setoriais"],
    },
    {
        "numero": 13,
        "titulo": "Sinais de contratação",
        "pontos": [
            "Vagas publicadas em portais de emprego e há quanto tempo",
        ],
        "fontes_tipicas": ["LinkedIn Jobs", "Indeed", "Glassdoor"],
    },
]

# Seções do relatório além do diagnóstico por empresa — mantidas na mesma
# ordem validada no modelo (fictício) e na simulação com dados reais (NBG).
ORDEM_SECOES = [
    "sumario_executivo",
    "metodologia_e_fontes",
    "diagnostico_por_empresa",
    "comparativo_consolidado",
    "painel_reputacao_sinais_br",
    "painel_atividade_marketing_digital",
    "mapa_oportunidade_comparativo",
    "fontes_citadas",
    "sobre_atualizacoes",
]

# Regra inviolável (Emerson, 16-19/09/2026): o relatório é só apresentação
# de fatos verificados, com fonte e data — nunca leitura interpretativa,
# juízo de valor, comparação, sugestão de ação ou comentário sobre o
# próprio processo de construção do relatório.
REGRA_ZERO_INTERPRETACAO = (
    "Apresente apenas fatos verificáveis, cada um com fonte e data entre colchetes "
    "(ex.: [Instagram, 12/09/2026]). Nunca use linguagem de julgamento, avaliação, "
    "liderança, força/fraqueza, recomendação ou sugestão de ação. Quando uma "
    "informação não puder ser confirmada, registre isso como um fato (ex.: 'não "
    "acessível nesta consulta' ou 'não determinável nesta consulta') sem explicar "
    "ou justificar a limitação além do necessário, e sem comentar o processo de "
    "construção do relatório (nunca compare com nenhum modelo, nunca diga que uma "
    "divergência não foi/será resolvida — a ausência de resolução é sempre "
    "implícita e não deve ser mencionada)."
)
