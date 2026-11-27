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

// --- Tabs ---
const tabs = document.querySelectorAll('[role="tab"]');
tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    tabs.forEach((other) => {
      const selected = other === tab;
      other.setAttribute("aria-selected", String(selected));
      document.getElementById(other.getAttribute("aria-controls")).hidden = !selected;
    });
  });
});

// --- Housing and Clubs: questions answered from our documents ---
function renderAnswer(resultEl, result) {
  const card = document.createElement("article");
  card.className = `card ${result.found ? "label-match" : "label-not_sure"}`;
  addText(card, "p", result.answer, result.model_error ? "model-error" : "answer");

  if (result.sources.length) {
    addText(card, "p", result.found ? "Sources:" : "Closest sources:", "meta");
    const list = document.createElement("ul");
    list.className = "sources";
    result.sources.forEach((source) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = source.title;
      item.appendChild(link);
      list.appendChild(item);
    });
    card.appendChild(list);
  }
  resultEl.replaceChildren(card);
}

document.querySelectorAll(".ask-form").forEach((askForm) => {
  const panel = askForm.closest('[role="tabpanel"]');
  const box = askForm.querySelector("textarea");
  const askButton = askForm.querySelector('button[type="submit"]');
  const askMessage = panel.querySelector(".ask-message");
  const resultEl = panel.querySelector(".ask-result");

  askForm.querySelectorAll(".suggestion").forEach((suggestion) => {
    suggestion.addEventListener("click", () => {
      box.value = suggestion.textContent;
      box.focus();
    });
  });

  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = box.value.trim();
    if (!question) return;

    askButton.disabled = true;
    askMessage.className = "ask-message";
    askMessage.textContent = "Searching...";
    resultEl.replaceChildren();

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ section: askForm.dataset.section, question }),
      });
      if (!response.ok) throw new Error(`Server error ${response.status}`);
      askMessage.textContent = "";
      renderAnswer(resultEl, await response.json());
    } catch (err) {
      askMessage.className = "ask-message error";
      askMessage.textContent = "Something went wrong. Please try again.";
    } finally {
      askButton.disabled = false;
    }
  });
});

// --- Fixed lists (no model): parsed from data/ files by the server ---
const NOT_AVAILABLE = "Not sure – this list is not available.";

function addLink(parent, url, text, className) {
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = text;
  if (className) link.className = className;
  parent.appendChild(link);
  return link;
}

function addSourceLine(parent, source, label) {
  if (!source || !source.url) return;
  const line = addText(parent, "p", `${label || "Source"}: `, "meta");
  addLink(line, source.url, source.title);
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Server error ${response.status}`);
  return response.json();
}

async function loadHousingWebsites() {
  const panel = document.getElementById("housing-websites");
  const hint = panel.querySelector(".hint");
  try {
    const result = await getJson("/api/housing/websites");
    if (!result.websites.length) {
      hint.textContent = NOT_AVAILABLE;
      return;
    }
    hint.remove();
    const list = document.createElement("div");
    list.className = "link-buttons";
    result.websites.forEach((site) => addLink(list, site.url, site.name, "link-button"));
    panel.appendChild(list);
    addText(panel, "p", result.disclaimer, "meta");
    addSourceLine(panel, result.source);
  } catch (err) {
    hint.textContent = NOT_AVAILABLE;
  }
}

async function loadStartHere() {
  const panel = document.getElementById("clubs-start");
  const hint = panel.querySelector(".hint");
  try {
    const { esn, fair } = await getJson("/api/clubs/start-here");
    if (!esn && !fair) {
      hint.textContent = NOT_AVAILABLE;
      return;
    }
    hint.remove();
    if (esn) {
      addText(panel, "h3", esn.name);
      const links = document.createElement("div");
      links.className = "link-buttons";
      if (esn.website) addLink(links, esn.website, "Website", "link-button");
      if (esn.instagram) addLink(links, esn.instagram.url, `Instagram ${esn.instagram.handle}`, "link-button");
      panel.appendChild(links);
      if (esn.app) addText(panel, "p", `App: ${esn.app}`);
      addSourceLine(panel, esn.source);
    }
    if (fair) {
      addText(panel, "h3", "Associations on Display");
      addText(panel, "p", fair.text);
      if (fair.event_url) addLink(addText(panel, "p", ""), fair.event_url, "Event page");
      addSourceLine(panel, fair.source);
    }
  } catch (err) {
    hint.textContent = NOT_AVAILABLE;
  }
}

const clubAreasForm = document.getElementById("club-areas-form");
const clubAreasEl = document.getElementById("club-areas");
const clubMessage = document.getElementById("club-message");
const clubResults = document.getElementById("club-results");
let clubList = { areas: [], source: null };

async function loadClubAreas() {
  const hint = clubAreasEl.querySelector(".hint");
  try {
    clubList = await getJson("/api/clubs/areas");
    if (!clubList.areas.length) {
      hint.textContent = NOT_AVAILABLE;
      return;
    }
    hint.remove();
    clubList.areas.forEach((area) => {
      const label = document.createElement("label");
      label.className = "checkbox";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.name = "area";
      box.value = area.name;
      label.append(box, " " + area.name);
      clubAreasEl.appendChild(label);
    });
  } catch (err) {
    hint.textContent = NOT_AVAILABLE;
  }
}

clubAreasForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const chosen = new FormData(clubAreasForm).getAll("area");
  clubResults.replaceChildren();
  if (!chosen.length) {
    clubMessage.className = "error";
    clubMessage.textContent = "Please choose at least one area.";
    return;
  }
  clubMessage.className = "";
  clubMessage.textContent = "";
  const card = document.createElement("article");
  card.className = "card";
  clubList.areas
    .filter((area) => chosen.includes(area.name))
    .forEach((area) => {
      addText(card, "h3", area.name);
      const list = document.createElement("ul");
      list.className = "sources";
      area.clubs.forEach((club) => addText(list, "li", club));
      card.appendChild(list);
    });
  if (clubList.source) {
    addSourceLine(card, { url: clubList.source.url, title: "official Bocconi list" });
  }
  clubResults.appendChild(card);
});

loadHousingWebsites();
loadStartHere();
loadClubAreas();
