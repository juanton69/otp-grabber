const HOST = "com.juanton.otpgrabber";

let port = null;
let reqSeq = 0;
const pending = new Map();

function connect() {
  if (port) return port;
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (err) {
    port = null;
    return null;
  }
  port.onMessage.addListener((msg) => {
    const id = msg && msg.id;
    if (id && pending.has(id)) {
      const { resolve, timer } = pending.get(id);
      clearTimeout(timer);
      pending.delete(id);
      resolve(msg);
    }
  });
  port.onDisconnect.addListener(() => {
    port = null;
    for (const { resolve, timer } of pending.values()) {
      clearTimeout(timer);
      resolve({ code: null, error: "disconnected" });
    }
    pending.clear();
  });
  return port;
}

function nativeCall(payload, timeoutMs = 800) {
  return new Promise((resolve) => {
    const p = connect();
    if (!p) {
      resolve({ code: null, error: "no-native-host" });
      return;
    }
    const id = `r${Date.now()}-${++reqSeq}`;
    const timer = setTimeout(() => {
      pending.delete(id);
      resolve({ code: null, error: "timeout", id });
    }, timeoutMs);
    pending.set(id, { resolve, timer });
    try {
      p.postMessage({ ...payload, id });
    } catch (err) {
      clearTimeout(timer);
      pending.delete(id);
      port = null;
      resolve({ code: null, error: "post-failed" });
    }
  });
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const op = message && message.op;
  if (op === "peek" || op === "consume" || op === "status" || op === "ping") {
    nativeCall({ op, host: message.host || "" }).then(sendResponse);
    return true;
  }
  sendResponse({ error: "unknown" });
  return false;
});
