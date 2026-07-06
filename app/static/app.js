const itemInput = document.querySelector("#items");
const moveDate = document.querySelector("#moveDate");
const homeSize = document.querySelector("#homeSize");
const planButton = document.querySelector("#planButton");
const loadSample = document.querySelector("#loadSample");
const copyMarkdown = document.querySelector("#copyMarkdown");
const summaryGrid = document.querySelector("#summaryGrid");
const timeline = document.querySelector("#timeline");
const itemsTable = document.querySelector("#itemsTable");
const itemCount = document.querySelector("#itemCount");
const firstNight = document.querySelector("#firstNight");
const supplies = document.querySelector("#supplies");
const moveClock = document.querySelector("#moveClock");
const coachLine = document.querySelector("#coachLine");

const future = new Date();
future.setDate(future.getDate() + 24);
moveDate.value = future.toISOString().slice(0, 10);

async function requestPlan() {
  const response = await fetch("/api/plan", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      items: itemInput.value,
      moveDate: moveDate.value,
      homeSize: homeSize.value,
    }),
  });
  const plan = await response.json();
  renderPlan(plan);
}

function renderPlan(plan) {
  moveClock.textContent = `${plan.days_until_move} days until move day`;
  coachLine.textContent = plan.coach_notes[0] || "Your plan is ready.";

  summaryGrid.innerHTML = "";
  for (const [label, value] of Object.entries(plan.stage_summary)) {
    const card = document.createElement("article");
    card.className = "metric";
    card.innerHTML = `<strong>${value}</strong><span>${label}</span>`;
    summaryGrid.appendChild(card);
  }

  timeline.innerHTML = plan.timeline
    .map((step) => `<article><strong>${step.when}</strong><span>${step.task}</span></article>`)
    .join("");

  itemCount.textContent = `${plan.items.length} lines`;
  itemsTable.innerHTML = plan.items
    .map(
      (item) => `
      <article class="item-row">
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <span>${escapeHtml(item.box_label)}</span>
        </div>
        <span class="pill">${escapeHtml(item.stage)}</span>
        <span>${escapeHtml(item.action)}</span>
        <span>${item.risk_score}</span>
      </article>`
    )
    .join("");

  firstNight.innerHTML = plan.first_night_kit.map((name) => `<li>${escapeHtml(name)}</li>`).join("");
  supplies.innerHTML = plan.supply_list
    .map((item) => `<li><strong>${item.quantity}x ${escapeHtml(item.name)}</strong><span>${escapeHtml(item.why)}</span></li>`)
    .join("");
}

async function copyExport() {
  const response = await fetch("/api/export", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      items: itemInput.value,
      moveDate: moveDate.value,
      homeSize: homeSize.value,
    }),
  });
  const markdown = await response.text();
  await navigator.clipboard.writeText(markdown);
  copyMarkdown.textContent = "Copied";
  setTimeout(() => {
    copyMarkdown.textContent = "Copy Markdown";
  }, 1400);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" };
    return entities[char];
  });
}

loadSample.addEventListener("click", async () => {
  itemInput.value = await (await fetch("/sample")).text();
  requestPlan();
});
planButton.addEventListener("click", requestPlan);
copyMarkdown.addEventListener("click", copyExport);

loadSample.click();

