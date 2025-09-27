const scrapeBtn = document.getElementById("scrapeBtn");
const copyBtn = document.getElementById("copyBtn");
const output = document.getElementById("output");

async function callBackend(url) {
  const endpoint = "http://localhost:8000/scrape";
  try {
    output.textContent = "Scraping...";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(`Backend error ${res.status}: ${t}`);
    }
    const data = await res.json();
    const title = data.title ? `Title: ${data.title}\n` : "";
    const board = data.job_board ? `Job Board: ${data.job_board}\n` : "";
    const jid = data.job_id ? `Job ID: ${data.job_id}\n` : "";
    const header = [
      `URL: ${data.url}`,
      title.trim(),
      board.trim(),
      jid.trim()
    ].filter(Boolean).join("\n");
    output.textContent = `${header}\n\n${data.text}`;
  } catch (e) {
    output.textContent = `Failed to scrape via backend: ${e.message}`;
  }
}

scrapeBtn.addEventListener("click", async () => {
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab.url;
  await callBackend(url);
});

copyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(output.textContent).then(() => {
    alert("Copied to clipboard!");
  });
});
