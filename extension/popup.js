function set(id, value) {
  document.getElementById(id).textContent = value;
}

function refresh() {
  chrome.runtime.sendMessage({ op: "status" }, (reply) => {
    if (chrome.runtime.lastError || !reply) {
      set("daemon", "unreachable");
      set("betterbird", "—");
      set("fresh", "—");
      set("native", chrome.runtime.lastError ? chrome.runtime.lastError.message : "failed");
      return;
    }
    if (reply.error === "no-native-host" || reply.error === "daemon-unavailable") {
      set("native", reply.error);
      set("daemon", "down");
      set("betterbird", "—");
      set("fresh", "—");
      return;
    }
    set("native", "ok");
    set("daemon", reply.ok ? "running" : "down");
    set("betterbird", reply.betterbird ? "watching" : "no profile");
    set("fresh", String(reply.fresh ?? 0));
  });
}

document.getElementById("retry").addEventListener("click", refresh);
refresh();
