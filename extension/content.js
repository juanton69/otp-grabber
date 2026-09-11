(() => {

  const filled = new Set();
  let watching = false;
  let deadline = 0;
  let timer = 0;

  function setNativeValue(el, value) {
    const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    el.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    el.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "Unidentified" }));
  }

  function visible(el) {
    if (!el || el.disabled || el.readOnly) return false;
    const style = window.getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none" || Number(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function attrBlob(el) {
    return [
      el.getAttribute("autocomplete"),
      el.getAttribute("name"),
      el.getAttribute("id"),
      el.getAttribute("aria-label"),
      el.getAttribute("placeholder"),
      el.getAttribute("inputmode"),
      el.getAttribute("data-testid"),
      el.className,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function isOtpInput(el) {
    if (!(el instanceof HTMLInputElement) && !(el instanceof HTMLTextAreaElement)) return false;
    if (!visible(el)) return false;
    const type = (el.type || "").toLowerCase();
    if (["hidden", "checkbox", "radio", "file", "submit", "button", "range", "color", "email", "url", "search"].includes(type)) {
      return false;
    }
    const blob = attrBlob(el);
    if (/\b(search|username|email|password|new-password|current-password)\b/.test(blob) && !/one-time|otp|totp|2fa|verification/.test(blob)) {
      if (type === "password" && !/one-time|otp|totp|2fa|code/.test(blob)) return false;
    }
    if ((el.autocomplete || "").toLowerCase() === "one-time-code") return true;
    if (/\b(one-time-code|otp|totp|2fa|mfa|verification[-_ ]?code|auth[-_ ]?code|sms[-_ ]?code|security[-_ ]?code)\b/.test(blob)) {
      return true;
    }
    const max = Number(el.maxLength);
    const inputMode = (el.inputMode || el.getAttribute("inputmode") || "").toLowerCase();
    const pattern = el.getAttribute("pattern") || "";
    if ((type === "tel" || type === "number" || inputMode === "numeric" || inputMode === "decimal") && max >= 4 && max <= 8) {
      return true;
    }
    if (/^\d{4,8}$/.test(pattern.replace(/[^\\d{}.]/g, "")) || /\\d\{[4-8]\}/.test(pattern)) {
      return true;
    }
    if (max === 1 && (type === "tel" || type === "number" || inputMode === "numeric" || el.inputMode === "numeric")) {
      return true;
    }
    return false;
  }

  function collectOtpInputs() {
    const nodes = Array.from(document.querySelectorAll("input, textarea")).filter(isOtpInput);
    return nodes;
  }

  function digitBoxes(inputs) {
    const singles = inputs.filter((el) => Number(el.maxLength) === 1 || (el.value.length <= 1 && el.size === 1));
    if (singles.length >= 4 && singles.length <= 8) return singles;
    return null;
  }

  function alreadyFilled(el, code) {
    const current = (el.value || "").replace(/\D/g, "");
    return current === code;
  }

  function fill(inputs, code) {
    const boxes = digitBoxes(inputs);
    if (boxes) {
      const digits = code.split("");
      boxes.forEach((el, i) => {
        if (digits[i]) setNativeValue(el, digits[i]);
      });
      return true;
    }
    const target =
      inputs.find((el) => (el.autocomplete || "").toLowerCase() === "one-time-code") ||
      inputs.find((el) => Number(el.maxLength) >= 4 && Number(el.maxLength) <= 8) ||
      inputs[0];
    if (!target) return false;
    if (alreadyFilled(target, code)) return false;
    setNativeValue(target, code);
    target.focus();
    return true;
  }

  function ask(op) {
    return new Promise((resolve) => {
      try {
        chrome.runtime.sendMessage({ op, host: location.hostname }, (reply) => {
          if (chrome.runtime.lastError) {
            resolve(null);
            return;
          }
          resolve(reply || null);
        });
      } catch (err) {
        resolve(null);
      }
    });
  }

  async function tryFill(consume) {
    const inputs = collectOtpInputs();
    if (!inputs.length) return false;
    const reply = await ask(consume ? "consume" : "peek");
    const code = reply && reply.code;
    if (!code || filled.has(code)) return false;
    const ok = fill(inputs, String(code));
    if (ok) {
      filled.add(String(code));
      if (!consume) await ask("consume");
      return true;
    }
    return false;
  }

  function arm() {
    deadline = Date.now() + 120000;
    if (watching) return;
    watching = true;
    const tick = async () => {
      if (Date.now() > deadline) {
        watching = false;
        timer = 0;
        return;
      }
      await tryFill(false);
      timer = window.setTimeout(tick, 1200);
    };
    tick();
  }

  function maybeArm() {
    if (collectOtpInputs().length) arm();
  }

  const observer = new MutationObserver(() => {
    maybeArm();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("focusin", (event) => {
    if (isOtpInput(event.target)) arm();
  });
  maybeArm();
})();
