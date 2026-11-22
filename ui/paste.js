// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";
(function () {
  const CHAT = ".composer textarea, textarea.bot-chat-box, textarea.bt-chat-input, textarea.agi-bot-chat-input, " +
               "textarea.suite-wizard-in, textarea.bot-words, textarea.add-bot-words, textarea.build-req, textarea[data-chat]";
  const IS_BOX = t => t && t.tagName === "TEXTAREA" && t.matches(CHAT);

  async function addImage(box, file) {
    if (!file || !/^image\//.test(file.type)) return false;
    const a = api();
    if (!a || !a.chat_save_image) { toast("Restart Randis UDS to turn on images in chats."); return true; }
    const url = await new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(file); });
    const r = await a.chat_save_image(url);
    if (r.error) { toast(r.error); return true; }
    const line = `[Image attached: ${r.path} — open it with the Read tool and look at it]`;
    const before = box.value.slice(0, box.selectionStart), after = box.value.slice(box.selectionEnd);
    const pad = before && !before.endsWith("\n") ? "\n" : "";
    box.value = before + pad + line + "\n" + after;
    box.selectionStart = box.selectionEnd = (before + pad + line + "\n").length;
    box.dispatchEvent(new Event("input", { bubbles: true }));
    box.focus();
    toast("Image added");
    return true;
  }

  document.addEventListener("paste", e => {
    if (!IS_BOX(e.target)) return;
    const files = [...(e.clipboardData && e.clipboardData.items || [])].filter(i => i.kind === "file" && /^image\//.test(i.type)).map(i => i.getAsFile());
    if (!files.length) return;
    e.preventDefault();
    files.forEach(f => addImage(e.target, f));
  }, true);

  document.addEventListener("dragover", e => {
    if (IS_BOX(e.target) && [...(e.dataTransfer.items || [])].some(i => i.kind === "file")) e.preventDefault();
  }, true);
  document.addEventListener("drop", e => {
    if (!IS_BOX(e.target)) return;
    const files = [...(e.dataTransfer.files || [])].filter(f => /^image\//.test(f.type));
    if (!files.length) return;
    e.preventDefault(); e.stopPropagation();
    files.forEach(f => addImage(e.target, f));
  }, true);

  document.addEventListener("click", e => {
    const b = e.target.closest(".img-pick");
    if (!b) return;
    e.stopPropagation();
    const near = b.closest(".composer");
    const box = (near && near.querySelector("textarea")) || (b.previousElementSibling && b.previousElementSibling.matches("textarea") ? b.previousElementSibling : null);
    if (!box) return;
    const pick = document.createElement("input");
    pick.type = "file"; pick.accept = "image/*"; pick.multiple = true;
    pick.onchange = () => [...pick.files].forEach(f => addImage(box, f));
    pick.click();
  }, true);

  function equip(ta) {
    if (ta.dataset.imgReady) return;
    ta.dataset.imgReady = "1";
    const near = ta.closest(".composer");
    if (near && near.querySelector(".img-pick")) return;
    const b = document.createElement("button");
    b.type = "button"; b.className = "pill img-pick"; b.textContent = "🖼";
    b.title = "Add an image (or paste one with Ctrl+V, or drop one here)";
    ta.insertAdjacentElement("afterend", b);
  }

  const TAG = /\[Image(?: attached)?: ([^\]\n]+?\.(?:png|jpe?g|gif|webp|bmp))/gi;
  const cache = new Map();
  function picture(path) {
    if (!cache.has(path)) { const a = api(); cache.set(path, a && a.chat_image_data ? a.chat_image_data(path) : Promise.resolve(null)); }
    return cache.get(path);
  }
  function thumbs(node) {
    const host = node.nodeType === 3 ? node.parentElement : node;
    if (!host || host.closest("textarea, input, script, style, .chat-thumbs, [contenteditable='true']")) return;
    const text = host.textContent || "";
    if (text.indexOf("[Image") < 0) return;
    const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
    for (let t; (t = walker.nextNode());) {
      const el = t.parentElement;
      if (!el || el.closest("textarea, input, script, style, .chat-thumbs")) continue;
      const paths = [...(t.nodeValue || "").matchAll(TAG)].map(m => m[1].trim());
      if (!paths.length) continue;
      const key = paths.join("|");
      if ([...el.children].some(c => c.classList.contains("chat-thumbs") && c.dataset.key === key)) continue;
      const row = document.createElement("div");
      row.className = "chat-thumbs";
      row.dataset.key = key;
      paths.forEach(p => picture(p).then(url => {
        if (!url) return;
        const img = document.createElement("img");
        img.src = url; img.alt = "image in this chat"; img.title = "Click to make it bigger or smaller";
        img.onclick = () => img.classList.toggle("big");
        row.appendChild(img);
      }));
      el.appendChild(row);
    }
  }

  function scan(root) {
    if (root.nodeType === 1) {
      if (root.matches && root.matches(CHAT)) equip(root);
      if (root.querySelectorAll) root.querySelectorAll(CHAT).forEach(equip);
    }
    thumbs(root);
  }
  function start() {
    scan(document.body);
    new MutationObserver(list => {
      for (const m of list) {
        if (m.type === "characterData") thumbs(m.target);
        else m.addedNodes.forEach(n => { if (n.nodeType === 1 || n.nodeType === 3) scan(n); });
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
})();
