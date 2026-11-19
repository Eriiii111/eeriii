const form = document.getElementById("reportForm");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.getElementById("formMessage");
  const button = form.querySelector("button");
  button.disabled = true;
  button.innerHTML = "Duke dërguar…";
  message.textContent = "";
  try {
    const response = await fetch("/api/reports", { method: "POST", body: new FormData(form) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Raportimi nuk u dërgua.");
    form.reset();
    message.className = "form-message success";
    message.textContent = `Raportimi u ruajt me sukses. Numri yt i referencës është #${result.id}.`;
  } catch (error) {
    message.className = "form-message error";
    message.textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Dërgo raportimin <span>→</span>';
  }
});
