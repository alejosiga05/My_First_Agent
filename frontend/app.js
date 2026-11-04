const statusEl = document.getElementById("status");

fetch("/health")
  .then((response) => response.json())
  .then((data) => {
    statusEl.textContent = data.ok ? "Server is running." : "Server reported a problem.";
  })
  .catch(() => {
    statusEl.textContent = "Could not reach the server.";
  });
