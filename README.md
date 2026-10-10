# Portal de Análise de Concorrência — sistema

Sistema que vende e entrega automaticamente o relatório de análise de
concorrência (VMAI). Reaproveita, ponto por ponto, o padrão de relatório
validado manualmente em setembro de 2026 (modelo fictício + simulação com
dados reais da NBG Telecom), e agora inclui cobrança real via Mercado Pago
— pronto para a rodada de teste com você e alguns amigos.

## O que já funciona

- **Página de vendas** (`/`) — explica o produto, mostra o preço e leva
  ao formulário; escrita para deixar claro o que o relatório é (um
  retrato factual, com fonte de cada informação) e o que não é (uma
  consultoria com opinião).
- **Formulário de intake** (`/comprar`) — nome da empresa cliente + e-mail,
  âncoras digitais (site/Instagram/Facebook), CNPJ opcional; até N
  concorrentes, cada um exigindo pelo menos uma âncora digital.
- **Pagamento real via Mercado Pago** (`app/payment.py`, Checkout Pro) —
  ao enviar o formulário, o sistema cria uma preferência de pagamento e
  redireciona o cliente para a página de checkout do Mercado Pago
  (cartão, PIX ou boleto, sem precisarmos construir formulário de cartão
  nós mesmos). Só depois que o Mercado Pago confirma o pagamento — via
  webhook, nunca só pelo retorno do navegador — é que o relatório começa
  a ser gerado. Ver "Como configurar o Mercado Pago" abaixo.
- **API** (`POST /api/pedidos`, `GET /api/pedidos/{id}`,
  `POST /api/webhooks/mercadopago`) — cria o pedido, inicia o pagamento,
  recebe a confirmação do Mercado Pago e dispara a geração em segundo
  plano; permite acompanhar o status.
- **Páginas de retorno** (`/pedidos/{id}/sucesso|pendente|falha`) — para
  onde o Mercado Pago traz o cliente de volta depois do checkout; mostram
  o andamento do pedido em tempo real (a mesma consulta de status de
  antes).
- **Motor de geração** (`app/generator.py`) — pesquisa cada empresa via
  API da Anthropic com a ferramenta de busca web, seguindo exatamente
  as 13 frentes do modelo validado (`app/report_frentes.py`).
- **Linter de rigor** (`app/linter.py`) — verifica automaticamente se
  algum texto gerado contém os mesmos tipos de erro que foram
  corrigidos manualmente no relatório da NBG (comparação com o modelo
  fictício, "sem tentativa de resolver", juízo de valor, recomendação
  etc.). Hoje ele **registra os avisos no pedido, mas não bloqueia o
  envio** — ver "Próximo passo importante" abaixo.
- **Montagem do relatório final em PDF** (`app/pdf_builder.py`, com
  `app/templates/relatorio.html` + `app/static/relatorio.css`) —
  reproduz a mesma estrutura de seções do modelo (sumário executivo,
  metodologia, diagnóstico por empresa nas 13 frentes, comparativo
  consolidado, painéis, mapa de oportunidade, fontes citadas, sobre
  atualizações), com design completo: capa com as cores da marca, selos
  coloridos no mapa de oportunidade (✓ verde / — vermelho / n/d âmbar),
  tipografia cuidada, cabeçalho/rodapé com numeração de página — layout
  consistente em qualquer leitor de PDF, ao contrário de um .docx.
  `app/docx_builder.py` continua no projeto como alternativa (gera a
  mesma estrutura em Word, editável, mas com design bem mais simples) —
  não é usado no fluxo padrão hoje.
- **Envio por e-mail** (`app/email_sender.py`) — via Resend, com o PDF
  em anexo.

Todo o pipeline foi testado localmente nesta sessão: página de vendas e
formulário renderizam, validação de intake bloqueia os casos que devem
ser bloqueados, a criação do pedido chega a tentar mesmo a chamada real
ao Mercado Pago (bloqueada aqui só pela rede restrita deste ambiente de
desenvolvimento, não por erro de código), o webhook processa
notificações válidas e ignora as irrelevantes, e a montagem do PDF roda
de ponta a ponta com dados simulados. **Falta só colocar as chaves reais
(Anthropic, Resend, Mercado Pago) para testar o fluxo completo de
verdade — ver Etapa 3 e Etapa 6 do plano de teste.**

### Sobre o design do PDF

O visual segue a identidade real da VMAI: cinza-chumbo (`#424242`) como
cor estrutural (títulos, tabelas, capítulos) e o vermelho da marca
(`#ef0c0c`) só em detalhes pontuais — a faixa da capa, o anel dos
números de frente e a etiqueta "Empresa cliente" — para dar personalidade
sem pesar a leitura. A capa usa o logo de verdade
(`app/static/vmai-logo.png`, fundo transparente) em vez de texto, sobre
um fundo creme (`#f7f2e7`). Trocar qualquer cor, fonte ou imagem é mexer
só em `app/static/relatorio.css` (variáveis no topo do arquivo) e
`app/static/vmai-logo.png` — o resto do sistema não precisa mudar.

## O que ainda não está aqui (de propósito)

- **WhatsApp** — a entrega é só por e-mail nesta fase, como combinado.
  Quando a VMAI tiver acesso à API oficial do WhatsApp Business, entra
  como uma segunda função em `email_sender.py` (ou um módulo
  `whatsapp_sender.py` novo), chamada ao lado do e-mail.
- **Banco de dados** — os pedidos são salvos em arquivo JSON
  (`orders/`). Funciona bem para o volume de um MVP concierge; trocar
  por Postgres depois é uma mudança isolada em `app/storage.py`.
- **Hospedagem definitiva** — ver sugestões mais abaixo; o que está
  aqui já roda em qualquer lugar que suporte Python/WeasyPrint.

## Próximo passo importante: decidir o papel do linter

Hoje, se o linter encontrar linguagem proibida, ele só grava um aviso
no pedido (`avisos_linter`) — o relatório ainda é montado e enviado
normalmente. Antes de vender para o primeiro cliente real (mesmo que
amigo), vale decidir: o sistema deve **bloquear o envio automático** e
cair para revisão manual quando houver avisos? Recomendo que sim, pelo
menos nesta fase inicial — é barato de ligar (mudar o `if avisos:` em
`app/main.py` para impedir o envio e notificar você por e-mail em vez
do cliente), e evita que um erro de redação do modelo chegue a um
testador antes de você ter visto o padrão de erros que a IA comete em
dados reais variados.

## Como configurar o Mercado Pago

1. Crie (ou acesse) sua conta em [mercadopago.com.br](https://www.mercadopago.com.br),
   vá em **Seu negócio > Configurações > Credenciais** (ou
   `dashboard.mercadopago.com.br` → "Suas integrações" → crie uma
   aplicação).
2. Para testar sem cobrar de verdade, use as **credenciais de teste**
   (Access Token que começa com `TEST-`) e um comprador de teste
   (Mercado Pago gera usuários de teste compradores e vendedores
   separados — não use sua própria conta de produção nos dois lados).
3. Coloque o Access Token em `MERCADOPAGO_ACCESS_TOKEN` no `.env`.
4. **O webhook precisa de uma URL pública.** Rodando só em
   `localhost`, o Mercado Pago não consegue te avisar quando alguém
   paga. Para testar localmente antes do deploy, exponha a porta 8000
   com um túnel (ex. `ngrok http 8000`) e cadastre
   `https://SEU-TUNEL.ngrok.io` como a URL base — o sistema já monta
   `notification_url` e as `back_urls` sozinho a partir da URL que o
   navegador usou para acessar o site, então basta acessar o site pelo
   endereço do túnel em vez de `localhost` durante esse teste. Em
   produção (Etapa 5 do plano), a URL pública real do deploy resolve
   isso automaticamente, sem precisar de túnel.
5. Quando for cobrar de verdade, troque pelo Access Token de produção
   (começa com `APP_USR-`) — nenhuma outra mudança de código é
   necessária.

## Como rodar localmente

O PDF é gerado com WeasyPrint, que depende de bibliotecas de sistema
(Pango, Cairo, GDK-Pixbuf) além dos pacotes Python. Em Linux (Debian/
Ubuntu), antes do `pip install`, rode:

```bash
sudo apt-get install -y libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

No macOS, `brew install pango` resolve. Sem essas bibliotecas, o
`pip install -r requirements.txt` funciona, mas a geração do PDF falha
ao importar `weasyprint`.

```bash
cd portal-analise-concorrencia
pip install -r requirements.txt
cp .env.example .env
# edite o .env com suas chaves (ANTHROPIC_API_KEY, RESEND_API_KEY, MERCADOPAGO_ACCESS_TOKEN)
uvicorn app.main:app --reload
```

Abra `http://localhost:8000` — a página de vendas. O formulário fica em
`http://localhost:8000/comprar`.

## Variáveis de ambiente necessárias

| Variável | Para quê | Onde conseguir |
|---|---|---|
| `ANTHROPIC_API_KEY` | Pesquisa + redação do relatório | console.anthropic.com — precisa ter a ferramenta "Web search" habilitada |
| `RESEND_API_KEY` | Envio do e-mail com o relatório | resend.com (tem plano gratuito para começar) |
| `EMAIL_REMETENTE` | Endereço que aparece como remetente | precisa de um domínio verificado na Resend |
| `MERCADOPAGO_ACCESS_TOKEN` | Cobrança do relatório | dashboard.mercadopago.com.br — use o token de teste (`TEST-...`) até a Etapa 6 do plano, depois troque para produção (`APP_USR-...`) |
| `PRECO_RELATORIO_CENTAVOS` | Preço cobrado, em centavos | você mesmo decide — 1990 (R$ 19,90) é o valor padrão sugerido para a rodada de teste |

## Custo por relatório (estimativa)

Cada pedido faz **1 chamada por empresa** (cliente + cada concorrente)
para pesquisar as 13 frentes, mais **1 chamada final** para sintetizar
as seções comparativas. Com 3-4 empresas por relatório (cliente + 2-3
concorrentes, como no cenário da NBG), isso são de 4 a 5 chamadas ao
modelo, cada uma podendo disparar várias buscas web (a busca web é
cobrada à parte, ~R$ 55 por 1.000 buscas ao câmbio atual, fora o custo
de tokens do modelo e a taxa do Mercado Pago sobre cada venda). Vale
medir o custo real nos primeiros pedidos de teste (Etapa 6 do plano)
antes de fechar o preço de venda definitivo.

## Hospedagem e domínio

Para a rodada de teste com amigos, a recomendação é um subdomínio da
VMAI (ex. `concorrencia.vmai.com.br` ou `teste.vmai.com.br`) — o
domínio `vmai.com.br` já está ativo (DNS na Syscoin Host/cPanel), então
não é preciso comprar nada novo, só criar o registro de DNS apontando
para onde o sistema for hospedado. Para o deploy em si, Railway ou
Render são as opções mais rápidas (deploy direto do código, HTTPS
automático, suportam as dependências do WeasyPrint via Dockerfile);
um VPS próprio é a alternativa caso já exista um disponível.

## Estrutura do projeto

```
app/
  main.py                      # FastAPI: rotas, pagamento, webhook, orquestração do pipeline
  config.py                    # variáveis de ambiente
  models.py                    # regras de validação do intake + status/campos do pagamento
  payment.py                   # integração com o Mercado Pago (Checkout Pro)
  report_frentes.py            # as 13 frentes + regra de zero interpretação (fonte única da verdade sobre o padrão do relatório)
  column_labels.py             # rótulos acentuados para as colunas dos painéis (evita "Mencoes" sem acento)
  generator.py                 # pesquisa (Anthropic + web search) e síntese
  linter.py                    # checagem automática de linguagem proibida
  pdf_builder.py               # monta o relatório final em PDF (formato padrão de entrega)
  docx_builder.py               # alternativa em .docx editável (não usado no fluxo padrão)
  email_sender.py               # envio por e-mail (Resend)
  storage.py                    # persistência dos pedidos (JSON por enquanto)
  templates/vendas.html         # página de vendas ("/")
  templates/intake.html         # formulário de pedido ("/comprar")
  templates/retorno.html        # páginas de volta do Mercado Pago (sucesso/pendente/falha)
  templates/relatorio.html      # template do relatório final (PDF)
  static/style.css              # visual do site (vendas + formulário + retorno)
  static/intake.js              # formulário: valida, cria o pedido, redireciona ao checkout
  static/retorno.js             # páginas de retorno: consulta e mostra o status em tempo real
  static/relatorio.css          # visual do relatório final — cores/identidade ficam todas aqui
orders/                         # pedidos salvos (.json) e relatórios gerados (.pdf)
requirements.txt
.env.example
```
