const lista = document.getElementById("lista-concorrentes");
const templateConcorrente = document.getElementById("template-concorrente");
const btnAdd = document.getElementById("btn-add-concorrente");
const form = document.getElementById("form-pedido");
const statusBox = document.getElementById("status-pedido");

function adicionarConcorrente() {
  const clone = templateConcorrente.content.cloneNode(true);
  clone.querySelector(".btn-remover").addEventListener("click", (e) => {
    e.target.closest(".concorrente").remove();
  });
  lista.appendChild(clone);
}

btnAdd.addEventListener("click", adicionarConcorrente);
// Começa com um concorrente já visível, pra não confundir o usuário com a lista vazia.
adicionarConcorrente();

function lerConcorrentes() {
  return Array.from(lista.querySelectorAll(".concorrente")).map((el) => ({
    nome: el.querySelector(".c-nome").value.trim(),
    site: el.querySelector(".c-site").value.trim() || null,
    instagram: el.querySelector(".c-instagram").value.trim() || null,
    facebook: el.querySelector(".c-facebook").value.trim() || null,
    cnpj: el.querySelector(".c-cnpj").value.trim() || null,
  }));
}

function mostrarStatus(texto) {
  statusBox.hidden = false;
  statusBox.textContent = texto;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const dados = new FormData(form);

  const payload = {
    cliente: {
      nome: dados.get("cliente_nome").trim(),
      email_contato: dados.get("cliente_email").trim(),
      site: dados.get("cliente_site").trim() || null,
      instagram: dados.get("cliente_instagram").trim() || null,
      facebook: dados.get("cliente_facebook").trim() || null,
      cnpj: dados.get("cliente_cnpj").trim() || null,
    },
    concorrentes: lerConcorrentes(),
  };

  const semAncora = payload.concorrentes.find((c) => !c.site && !c.instagram && !c.facebook);
  if (semAncora) {
    mostrarStatus(`Informe ao menos um site, Instagram ou Facebook para "${semAncora.nome || "o concorrente"}".`);
    return;
  }

  // Modo de teste: acesse /comprar?teste=1 para pular o pagamento e
  // validar o fluxo completo (pesquisa real, PDF real, download real)
  // sem precisar de uma cobrança no Mercado Pago. Só funciona se
  // PERMITIR_PEDIDO_TESTE estiver ligado no servidor.
  const modoTeste = new URLSearchParams(window.location.search).get("teste") === "1";
  const endpoint = modoTeste ? "/api/pedidos/teste" : "/api/pedidos";

  form.querySelector(".btn-primario").disabled = true;
  mostrarStatus(modoTeste ? "Enviando pedido de teste (sem pagamento)..." : "Enviando pedido e preparando o pagamento...");

  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const erro = await resp.json().catch(() => ({}));
    mostrarStatus(`Erro ao enviar o pedido: ${erro.detail || resp.statusText}`);
    form.querySelector(".btn-primario").disabled = false;
    return;
  }

  const resultado = await resp.json();
  if (modoTeste) {
    mostrarStatus("Pedido de teste criado! Redirecionando para acompanhar...");
    window.location.href = resultado.retorno_url;
  } else {
    mostrarStatus("Pedido criado! Redirecionando para o pagamento...");
    window.location.href = resultado.checkout_url;
  }
});
