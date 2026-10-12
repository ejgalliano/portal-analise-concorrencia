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

function mostrarStatus(texto) {
  statusBox.hidden = false;
  statusBox.textContent = texto;
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

  mostrarStatus(mensagensStatus[pedido.status] || pedido.status);

  if (pedido.status === "pronto") {
    mostrarDownload(pedido);
    return;
  }

  if (pedido.status !== "erro") {
    setTimeout(() => consultarStatus(pedidoId), 4000);
  }
}

if (window.__pedidoId) {
  mostrarStatus(mensagensIniciais[window.__resultado] || "Consultando status do pedido...");
  if (window.__resultado !== "falha") {
    consultarStatus(window.__pedidoId);
  }
}
