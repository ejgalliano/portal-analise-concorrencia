// Usado nas páginas de retorno do Mercado Pago (/pedidos/{id}/sucesso|pendente|falha).
// window.__pedidoId e window.__resultado são definidos inline pelo template retorno.html.

const statusBox = document.getElementById("status-pedido");
const downloadBox = document.getElementById("download-pedido");

const mensagensIniciais = {
  sucesso: "Pagamento confirmado! Estamos preparando seu relatório — isso pode levar alguns minutos. Não feche esta página, o relatório fica disponível para download aqui mesmo quando terminar.",
  pendente: "Recebemos seu pagamento, mas ele ainda está sendo processado (comum em boleto e alguns PIX). Assim que for confirmado, o relatório é gerado automaticamente e aparece aqui para download.",
  falha: "O pagamento não foi concluído. Nenhuma cobrança foi feita — você pode tentar novamente quando quiser.",
};

const mensagensStatus = {
  aguardando_pagamento: "Aguardando confirmação do pagamento...",
  pago: "Pagamento confirmado. Iniciando a pesquisa...",
  recebido: "Pedido recebido. Iniciando pesquisa...",
  pesquisando: "Pesquisando sua empresa e seus concorrentes nas fontes públicas...",
  verificando: "Pesquisa concluída. Verificando o rigor do conteúdo antes de montar o documento...",
  gerando_documento: "Montando o documento final...",
  pronto: "Pronto! Seu relatório está disponível para download abaixo.",
  erro: "Ocorreu um erro ao gerar o relatório. Nossa equipe foi notificada e vai te retornar.",
};

// Etapas visíveis para o cliente — intencionalmente mais simples que os
// status internos do pedido (aguardando_pagamento/pago/recebido viram só
// "Pagamento confirmado" aqui, não precisam de uma etapa própria).
const ETAPAS = [
  { chave: "pagamento", rotulo: "Pagamento confirmado" },
  { chave: "pesquisando", rotulo: "Pesquisando empresa e concorrentes" },
  { chave: "verificando", rotulo: "Verificando o conteúdo" },
  { chave: "gerando_documento", rotulo: "Montando o PDF" },
  { chave: "pronto", rotulo: "Relatório pronto" },
];

const INDICE_ETAPA = {
  aguardando_pagamento: 0,
  pago: 0,
  recebido: 0,
  pesquisando: 1,
  verificando: 2,
  gerando_documento: 3,
  pronto: 4,
};

function montarEsqueletoStatus() {
  statusBox.innerHTML = `
    <div class="status-texto" id="status-texto"></div>
    <div class="barra-progresso"><div class="barra-progresso-preenchimento"></div></div>
    <ul class="etapas" id="lista-etapas"></ul>
  `;
}

// "erro" não é uma etapa em si — é uma falha DURANTE alguma etapa. Guarda
// a última etapa conhecida para saber qual marcar em vermelho quando o
// status virar "erro" (senão nenhuma etapa fica destacada).
let ultimaEtapaConhecida = 0;

function mostrarStatus(texto, statusAtual) {
  statusBox.hidden = false;
  statusBox.classList.toggle("status-erro", statusAtual === "erro");

  if (!document.getElementById("status-texto")) {
    montarEsqueletoStatus();
  }

  document.getElementById("status-texto").textContent = texto;

  if (statusAtual in INDICE_ETAPA) {
    ultimaEtapaConhecida = INDICE_ETAPA[statusAtual];
  }
  const indiceAtual = statusAtual === "erro" ? ultimaEtapaConhecida : (statusAtual in INDICE_ETAPA ? INDICE_ETAPA[statusAtual] : -1);
  const lista = document.getElementById("lista-etapas");
  lista.innerHTML = ETAPAS.map((etapa, i) => {
    let classe = "etapa";
    let marca = "";
    if (statusAtual === "erro" && i === indiceAtual) {
      classe += " erro";
      marca = "!";
    } else if (i < indiceAtual || statusAtual === "pronto" && i <= indiceAtual) {
      classe += " concluida";
      marca = "✓";
    } else if (i === indiceAtual) {
      classe += " atual";
    }
    return `<li class="${classe}"><span class="etapa-marca">${marca}</span><span>${etapa.rotulo}</span></li>`;
  }).join("");
}

function mostrarDownload(pedido) {
  if (!downloadBox) return;
  const link = `/pedidos/${pedido.id}/download?token=${pedido.download_token}`;
  downloadBox.hidden = false;
  downloadBox.innerHTML = `
    <a href="${link}" class="btn-primario btn-link" download>Baixar relatório (PDF)</a>
    <p class="aviso-download">Guarde este link ou baixe agora — se você sair desta página sem salvar o PDF, pode não conseguir acessá-lo depois.</p>
  `;
}

async function consultarStatus(pedidoId) {
  const resp = await fetch(`/api/pedidos/${pedidoId}`);
  if (!resp.ok) {
    // Pedido pode não existir mais ou a notificação do Mercado Pago ainda não chegou — tenta de novo.
    setTimeout(() => consultarStatus(pedidoId), 4000);
    return;
  }
  const pedido = await resp.json();

  mostrarStatus(mensagensStatus[pedido.status] || pedido.status, pedido.status);

  if (pedido.status === "pronto") {
    mostrarDownload(pedido);
    return;
  }

  if (pedido.status !== "erro") {
    setTimeout(() => consultarStatus(pedidoId), 4000);
  }
}

const STATUS_INICIAL_POR_RESULTADO = {
  sucesso: "pago",
  pendente: "aguardando_pagamento",
};

if (window.__pedidoId) {
  if (window.__resultado !== "falha") {
    mostrarStatus(
      mensagensIniciais[window.__resultado] || "Consultando status do pedido...",
      STATUS_INICIAL_POR_RESULTADO[window.__resultado] || "aguardando_pagamento",
    );
    consultarStatus(window.__pedidoId);
  }
}
