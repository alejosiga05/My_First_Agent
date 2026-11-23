const form = document.getElementById("match-form");
const button = form.querySelector("button");
const messageEl = document.getElementById("message");
const summaryEl = document.getElementById("summary");
const resultsEl = document.getElementById("results");

function addText(parent, tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  parent.appendChild(el);
  return el;
}

function renderCard(match) {
  const card = document.createElement("article");
  card.className = match.sure ? "card" : "card unsure";

  if (!match.sure) addText(card, "span", "Not sure – ask your coordinator", "badge");
  addText(card, "h2", match.exchange_course);
  const ects = match.ects === null ? "ECTS not stated" : `${match.ects} ECTS`;
  addText(card, "p", `${ects} · Matches: ${match.home_course}`, "meta");
  addText(card, "p", match.reason);

  const link = document.createElement("a");
  link.href = "/" + match.source;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Source";
  card.appendChild(link);

  resultsEl.appendChild(card);
}

// All numbers come from the server (recommender.py); no arithmetic here.
function renderSummary(s) {
  let text = `Confirmed: ${s.confirmed_ects} of ${s.credits_needed} ECTS needed`;
  if (s.unsure_ects) text += ` · +${s.unsure_ects} ECTS not sure`;
  summaryEl.textContent = text;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const body = {
    home_university: data.get("home_university").trim(),
    exchange_university: data.get("exchange_university").trim(),
    home_courses: data
      .get("home_courses")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean),
    credits_needed: Number(data.get("credits_needed")),
    question: data.get("question").trim() || null,
  };

  button.disabled = true;
  messageEl.className = "";
  messageEl.textContent = "Searching...";
  summaryEl.textContent = "";
  resultsEl.replaceChildren();

  try {
    const response = await fetch("/api/match", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    const result = await response.json();

    if (result.matches.length === 0) {
      messageEl.textContent = "Not sure – no matching courses found in our sources. Ask your coordinator.";
    } else {
      messageEl.textContent = "";
      renderSummary(result.summary);
      result.matches.forEach(renderCard);
    }
  } catch (err) {
    messageEl.className = "error";
    messageEl.textContent = "Something went wrong. Please check your input and try again.";
  } finally {
    button.disabled = false;
  }
});
