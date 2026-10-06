// Usado nas páginas de retorno do Mercado Pago (/pedidos/{id}/sucesso|pendente|falha).
// window.__pedidoId e window.__resultado são definidos inline pelo template retorno.html.

const statusBox = document.getElementById("status-pedido");

const mensagensIniciais = {
  sucesso: "Pagamento confirmado! Estamos preparando seu relatório — isso pode levar alguns minutos.",
  pendente: "Recebemos seu pagamento, mas ele ainda está sendo processado (comum em boleto e alguns PIX). Assim que for confirmado, o relatório é gerado automaticamente.",
  falha: "O pagamento não foi concluído. Nenhuma cobrança foi feita — você pode tentar novamente quando quiser.",
};

const mensagensStatus = {
  aguardando_pagamento: "Aguardando confirmação do pagamento...",
  pago: "Pagamento confirmado. Iniciando a pesquisa...",
  recebido: "Pedido recebido. Iniciando pesquisa...",
  pesquisando: "Pesquisando sua empresa e seus concorrentes nas fontes públicas...",
  verificando: "Pesquisa concluída. Verificando o rigor do conteúdo antes de montar o documento...",
  gerando_documento: "Montando o documento final...",
  pronto: null, // mensagem final é montada com o e-mail do cliente, abaixo
  erro: "Ocorreu um erro ao gerar o relatório. Nossa equipe foi notificada e vai te retornar.",
};

function mostrarStatus(texto) {
  statusBox.hidden = false;
  statusBox.textContent = texto;
}

async function consultarStatus(pedidoId) {
  const resp = await fetch(`/api/pedidos/${pedidoId}`);
  if (!resp.ok) {
    // Pedido pode não existir mais ou a notificação do Mercado Pago ainda não chegou — tenta de novo.
    setTimeout(() => consultarStatus(pedidoId), 4000);
    return;
  }
  const pedido = await resp.json();

  if (pedido.status === "pronto") {
    mostrarStatus(`Pronto! O relatório foi enviado para ${pedido.cliente.email_contato}.`);
    return;
  }

  mostrarStatus(mensagensStatus[pedido.status] || pedido.status);

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
