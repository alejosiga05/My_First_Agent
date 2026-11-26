const form = document.getElementById("match-form");
const button = form.querySelector("button");
const messageEl = document.getElementById("message");
const summaryEl = document.getElementById("summary");
const resultsEl = document.getElementById("results");
const homeCoursesEl = document.getElementById("home-courses");

function addText(parent, tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  parent.appendChild(el);
  return el;
}

function renderCard(match) {
  const card = document.createElement("article");
  card.className = `card label-${match.label}`;

  addText(card, "span", match.label_text, "badge");
  addText(card, "h2", match.exchange_course || "No exchange course found");
  const ects = match.ects === null ? "ECTS not stated" : `${match.ects} ECTS`;
  addText(card, "p", `${ects} · For: ${match.home_course} (${match.home_ects} ECTS)`, "meta");
  addText(card, "p", match.reason, match.model_error ? "model-error" : "");

  if (match.source_url) {
    const link = document.createElement("a");
    link.href = match.source_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "Source";
    card.appendChild(link);
  }

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
    home_courses: data.getAll("home_courses"),
    credits_needed: Number(data.get("credits_needed")),
    question: data.get("question").trim() || null,
  };

  if (body.home_courses.length === 0) {
    messageEl.className = "error";
    messageEl.textContent = "Please choose at least one home course.";
    return;
  }

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

async function loadHomeCourses() {
  const hint = homeCoursesEl.querySelector(".hint");
  try {
    const response = await fetch("/api/home-courses");
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    const result = await response.json();
    hint.remove();
    result.home_courses.forEach((name) => {
      const label = document.createElement("label");
      label.className = "checkbox";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.name = "home_courses";
      box.value = name;
      label.append(box, " " + name);
      homeCoursesEl.appendChild(label);
    });
  } catch (err) {
    hint.textContent = "Could not load home courses.";
  }
}

loadHomeCourses();
