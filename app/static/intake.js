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

  form.querySelector(".btn-primario").disabled = true;
  mostrarStatus("Enviando pedido e preparando o pagamento...");

  const resp = await fetch("/api/pedidos", {
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

  const { checkout_url } = await resp.json();
  mostrarStatus("Pedido criado! Redirecionando para o pagamento...");
  window.location.href = checkout_url;
});
