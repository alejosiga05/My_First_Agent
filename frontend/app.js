const form = document.getElementById("match-form");
const button = form.querySelector("button");
const messageEl = document.getElementById("message");
const summaryEl = document.getElementById("summary");
const resultsEl = document.getElementById("results");
const homeCoursesEl = document.getElementById("home-courses");
const homeUniversityEl = document.getElementById("home-university");
const EXCHANGE_UNIVERSITY = "Bocconi University";
let coursesByUniversity = {};

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
  addText(card, "h2", match.title);
  if (match.label === "not_sure") {
    if (match.closest_text) addText(card, "p", match.closest_text, "closest");
    addText(card, "p", `For: ${match.home_course} (${match.home_ects} ECTS)`, "meta");
  } else {
    const ects = match.ects === null ? "ECTS not stated" : `${match.ects} ECTS`;
    addText(card, "p", `${ects} · For: ${match.home_course} (${match.home_ects} ECTS)`, "meta");
  }
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
  if (s.not_sure_count) {
    const noun = s.not_sure_count === 1 ? "course" : "courses";
    text += ` · ${s.not_sure_count} ${noun} without a clear match – ask your coordinator`;
  }
  summaryEl.textContent = text;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const body = {
    home_university: data.get("home_university"),
    exchange_university: EXCHANGE_UNIVERSITY,
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

// Show only the chosen home university's courses as checkboxes.
function renderHomeCourses() {
  homeCoursesEl.querySelectorAll("label.checkbox").forEach((el) => el.remove());
  (coursesByUniversity[homeUniversityEl.value] || []).forEach((name) => {
    const label = document.createElement("label");
    label.className = "checkbox";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.name = "home_courses";
    box.value = name;
    label.append(box, " " + name);
    homeCoursesEl.appendChild(label);
  });
}

async function loadHomeCourses() {
  const hint = homeCoursesEl.querySelector(".hint");
  try {
    const response = await fetch("/api/home-courses");
    if (!response.ok) throw new Error(`Server error ${response.status}`);
    const result = await response.json();
    hint.remove();
    result.home_universities.forEach((group) => {
      coursesByUniversity[group.name] = group.courses;
      const option = document.createElement("option");
      option.value = group.name;
      option.textContent = group.name;
      homeUniversityEl.appendChild(option);
    });
    renderHomeCourses();
  } catch (err) {
    hint.textContent = "Could not load home courses.";
  }
}

homeUniversityEl.addEventListener("change", renderHomeCourses);

loadHomeCourses();
