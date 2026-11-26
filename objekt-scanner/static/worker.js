/* Objekt-Scanner – Mitarbeiter-Seite */
(function () {
  "use strict";
  const CFG = window.SCAN_CFG;
  const $ = (id) => document.getElementById(id);

  // ------------------------------------------------------------ Sprachen
  const T = {
    de: { what: "Was möchtest du senden?", anon: "Kein Name nötig. Wird direkt ans Büro gesendet.",
      sub_reinigung: "Nachweis der Reinigung", sub_stunden: "Arbeitszeiten", sub_abnahme: "Sonderleistung abgenommen",
      back: "Zurück", hint: "Blatt auf einen dunklen Tisch legen, ganzes Blatt ins Bild.", photo: "Foto machen",
      more: "Weitere Seite fotografieren", note: "Notiz hinzufügen (optional)", send: "Senden", page: "Seite", pages: "Seiten",
      sending: "Wird gesendet…", scanning: "Wird gescannt…", noedge: "Rand nicht erkannt – anpassen", blurry: "Unscharf – bitte neu fotografieren", adjust: "Ränder", adjust_hint: "Ziehe die 4 Punkte auf die Ecken des Blattes", cancel: "Abbrechen", apply: "Übernehmen", done: "Danke! Gesendet.",
      again: "Weiteres Dokument senden", queued: "Kein Internet – wird automatisch gesendet, sobald Verbindung da ist.",
      pending: "{n} Dokument(e) warten auf Internet", error: "Fehler – bitte nochmal versuchen.", remove: "Entfernen" },
    sq: { what: "Çfarë dëshiron të dërgosh?", anon: "Nuk duhet emër. Dërgohet direkt në zyrë.",
      sub_reinigung: "Dëshmi pastrimi", sub_stunden: "Orët e punës", sub_abnahme: "Pranim shërbimi special",
      back: "Kthehu", hint: "Vendose letrën mbi një tavolinë të errët, e gjithë letra në foto.", photo: "Bëj foto",
      more: "Fotografo faqen tjetër", note: "Shto shënim (opsional)", send: "Dërgo", page: "faqe", pages: "faqe",
      sending: "Duke dërguar…", scanning: "Duke skanuar…", noedge: "Skaji nuk u gjet – rregulloje", blurry: "E paqartë – bëj foto përsëri", adjust: "Skajet", adjust_hint: "Tërhiq 4 pikat në qoshet e letrës", cancel: "Anulo", apply: "Ruaj", done: "Faleminderit! U dërgua.",
      again: "Dërgo dokument tjetër", queued: "Nuk ka internet – do të dërgohet automatikisht kur të ketë lidhje.",
      pending: "{n} dokument(e) në pritje për internet", error: "Gabim – provo përsëri.", remove: "Hiq" },
    tr: { what: "Ne göndermek istiyorsun?", anon: "İsim gerekmez. Doğrudan ofise gönderilir.",
      sub_reinigung: "Temizlik kanıtı", sub_stunden: "Çalışma saatleri", sub_abnahme: "Özel hizmet onayı",
      back: "Geri", hint: "Kağıdı koyu bir masaya koy, tüm sayfa görünsün.", photo: "Fotoğraf çek",
      more: "Başka sayfa çek", note: "Not ekle (isteğe bağlı)", send: "Gönder", page: "sayfa", pages: "sayfa",
      sending: "Gönderiliyor…", scanning: "Taranıyor…", noedge: "Kenar bulunamadı – düzelt", blurry: "Bulanık – tekrar çek", adjust: "Kenarlar", adjust_hint: "4 noktayı kağıdın köşelerine sürükle", cancel: "İptal", apply: "Uygula", done: "Teşekkürler! Gönderildi.",
      again: "Başka belge gönder", queued: "İnternet yok – bağlantı gelince otomatik gönderilecek.",
      pending: "{n} belge internet bekliyor", error: "Hata – tekrar dene.", remove: "Sil" },
    ro: { what: "Ce vrei să trimiți?", anon: "Nu e nevoie de nume. Se trimite direct la birou.",
      sub_reinigung: "Dovada curățeniei", sub_stunden: "Ore de lucru", sub_abnahme: "Recepție serviciu special",
      back: "Înapoi", hint: "Pune foaia pe o masă închisă la culoare, toată foaia în poză.", photo: "Fă o poză",
      more: "Fotografiază altă pagină", note: "Adaugă notă (opțional)", send: "Trimite", page: "pagină", pages: "pagini",
      sending: "Se trimite…", scanning: "Se scanează…", noedge: "Margine negăsită – ajustează", blurry: "Neclar – fă din nou poza", adjust: "Margini", adjust_hint: "Trage cele 4 puncte pe colțurile foii", cancel: "Anulează", apply: "Aplică", done: "Mulțumim! Trimis.",
      again: "Trimite alt document", queued: "Fără internet – se trimite automat când revine conexiunea.",
      pending: "{n} document(e) așteaptă internet", error: "Eroare – încearcă din nou.", remove: "Șterge" },
    pl: { what: "Co chcesz wysłać?", anon: "Imię nie jest potrzebne. Trafia prosto do biura.",
      sub_reinigung: "Potwierdzenie sprzątania", sub_stunden: "Godziny pracy", sub_abnahme: "Odbiór usługi dodatkowej",
      back: "Wstecz", hint: "Połóż kartkę na ciemnym stole, cała kartka w kadrze.", photo: "Zrób zdjęcie",
      more: "Zrób zdjęcie kolejnej strony", note: "Dodaj notatkę (opcjonalnie)", send: "Wyślij", page: "str.", pages: "str.",
      sending: "Wysyłanie…", scanning: "Skanowanie…", noedge: "Nie wykryto krawędzi – popraw", blurry: "Nieostre – zrób ponownie", adjust: "Krawędzie", adjust_hint: "Przeciągnij 4 punkty na rogi kartki", cancel: "Anuluj", apply: "Zastosuj", done: "Dziękujemy! Wysłano.",
      again: "Wyślij kolejny dokument", queued: "Brak internetu – zostanie wysłane automatycznie po połączeniu.",
      pending: "{n} dok. czeka na internet", error: "Błąd – spróbuj ponownie.", remove: "Usuń" },
    ar: { what: "ماذا تريد أن ترسل؟", anon: "لا حاجة للاسم. يُرسل مباشرة إلى المكتب.",
      sub_reinigung: "إثبات التنظيف", sub_stunden: "ساعات العمل", sub_abnahme: "استلام خدمة خاصة",
      back: "رجوع", hint: "ضع الورقة على طاولة داكنة، واجعل الورقة كاملة في الصورة.", photo: "التقط صورة",
      more: "صوّر صفحة أخرى", note: "أضف ملاحظة (اختياري)", send: "إرسال", page: "صفحة", pages: "صفحات",
      sending: "جارٍ الإرسال…", scanning: "جارٍ المسح…", noedge: "لم يتم اكتشاف الحافة – عدّلها", blurry: "غير واضحة – التقط الصورة مرة أخرى", adjust: "الحواف", adjust_hint: "اسحب النقاط الأربع إلى زوايا الورقة", cancel: "إلغاء", apply: "تطبيق", done: "شكراً! تم الإرسال.",
      again: "إرسال مستند آخر", queued: "لا يوجد إنترنت – سيتم الإرسال تلقائياً عند توفر الاتصال.",
      pending: "{n} مستند بانتظار الإنترنت", error: "خطأ – حاول مرة أخرى.", remove: "حذف" },
    en: { what: "What do you want to send?", anon: "No name needed. Goes straight to the office.",
      sub_reinigung: "Cleaning record", sub_stunden: "Working hours", sub_abnahme: "Special service sign-off",
      back: "Back", hint: "Place the sheet on a dark surface, whole page in frame.", photo: "Take photo",
      more: "Photograph another page", note: "Add a note (optional)", send: "Send", page: "page", pages: "pages",
      sending: "Sending…", scanning: "Scanning…", noedge: "Edge not found – adjust", blurry: "Blurry – please retake", adjust: "Edges", adjust_hint: "Drag the 4 points onto the corners of the sheet", cancel: "Cancel", apply: "Apply", done: "Thank you! Sent.",
      again: "Send another document", queued: "No internet – will be sent automatically when connected.",
      pending: "{n} document(s) waiting for internet", error: "Error – please try again.", remove: "Remove" },
  };

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; }
  }
  let lang = store("scan-lang") || (navigator.language || "de").slice(0, 2);
  if (!T[lang]) lang = "de";
  const t = (k) => T[lang][k] || T.de[k] || k;

  function applyLang() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-t]").forEach((el) => { el.textContent = t(el.dataset.t); });
    $("lang").value = lang;
    render();
    updatePending();
  }
  $("lang").addEventListener("change", (e) => { lang = e.target.value; store("scan-lang", lang); applyLang(); });

  // ------------------------------------------------------------ Zustand
  let docType = null;
  let pages = []; // {id, blob, preview, processed, busy, found}
  let seq = 0;

  function show(step) {
    ["step-type", "step-photos", "step-done"].forEach((s) => { $(s).hidden = s !== step; });
    window.scrollTo(0, 0);
  }

  document.querySelectorAll(".type-btn").forEach((b) => b.addEventListener("click", () => {
    docType = b.dataset.type;
    pages = [];
    $("note").value = "";
    $("doc-title").textContent = CFG.docTypes[docType];
    $("error").hidden = true;
    render();
    show("step-photos");
  }));
  $("back").addEventListener("click", () => {
    pages.forEach((p) => p.origUrl && URL.revokeObjectURL(p.origUrl));
    show("step-type");
  });
  $("again").addEventListener("click", () => show("step-type"));

  // ------------------------------------------------------------ Foto -> verkleinern -> Scan-Vorschau
  async function downscale(file, max = 2200) {
    try {
      const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
      const s = Math.min(1, max / Math.max(bmp.width, bmp.height));
      const c = document.createElement("canvas");
      c.width = Math.round(bmp.width * s);
      c.height = Math.round(bmp.height * s);
      c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
      return await new Promise((res) => c.toBlob((b) => res(b || file), "image/jpeg", 0.85));
    } catch (e) {
      return file; // Server kann auch das Original
    }
  }

  async function dataUrlToBlob(u) { return (await fetch(u)).blob(); }

  $("camera").addEventListener("change", async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file || pages.length >= CFG.maxPages) return;
    const p = { id: ++seq, orig: null, origUrl: URL.createObjectURL(file), blob: null, preview: null,
      processed: false, busy: true, found: true, blurry: false, corners: null, manual: false };
    p.preview = p.origUrl;
    pages.push(p);
    render();
    p.orig = await downscale(file);
    URL.revokeObjectURL(p.origUrl);
    p.origUrl = URL.createObjectURL(p.orig);
    p.preview = p.origUrl;
    await runScan(p);
  });

  // Scan auf dem Server (mit automatisch erkannten oder manuell gesetzten Ecken)
  async function runScan(p) {
    p.busy = true;
    render();
    try {
      const fd = new FormData();
      fd.append("image", p.orig, "foto.jpg");
      if (p.manual && p.corners) fd.append("corners", JSON.stringify(p.corners));
      const r = await fetch(`/o/${CFG.token}/scan`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(r.status);
      const j = await r.json();
      p.preview = j.image;
      p.blob = await dataUrlToBlob(j.image);
      p.processed = true;
      p.found = j.found;
      p.blurry = j.blurry;
      p.corners = j.corners;
    } catch (err) {
      // offline: Original behalten, Server scannt später beim Senden (inkl. manueller Ecken)
      p.processed = false;
      p.blob = null;
    }
    p.busy = false;
    render();
  }

  // ------------------------------------------------------------ Ecken-Editor
  const ed = { page: null, pts: null };
  const DEFAULT_PTS = [[0.08, 0.08], [0.92, 0.08], [0.92, 0.92], [0.08, 0.92]];

  function openEditor(p) {
    if (p.busy || !p.orig) return;
    ed.page = p;
    ed.pts = (p.corners || DEFAULT_PTS).map((c) => c.slice());
    $("ed-img").onload = layoutEditor;
    $("ed-img").src = p.origUrl;
    $("editor").hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeEditor() {
    $("editor").hidden = true;
    document.body.style.overflow = "";
    ed.page = null;
  }
  function layoutEditor() {
    const img = $("ed-img"), area = $("ed-area"), stage = $("ed-stage");
    const aw = area.clientWidth - 32, ah = area.clientHeight - 32;
    const s = Math.min(aw / img.naturalWidth, ah / img.naturalHeight);
    stage.style.width = Math.round(img.naturalWidth * s) + "px";
    stage.style.height = Math.round(img.naturalHeight * s) + "px";
    drawEditor();
  }
  function drawEditor() {
    const st = $("ed-stage");
    const w = st.clientWidth, h = st.clientHeight;
    $("ed-poly").setAttribute("points", ed.pts.map(([x, y]) => `${x * w},${y * h}`).join(" "));
    $("ed-svg").setAttribute("viewBox", `0 0 ${w} ${h}`);
    document.querySelectorAll(".ed-h").forEach((el, i) => {
      el.style.left = ed.pts[i][0] * 100 + "%";
      el.style.top = ed.pts[i][1] * 100 + "%";
    });
  }
  document.querySelectorAll(".ed-h").forEach((el, i) => {
    el.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      el.setPointerCapture(e.pointerId);
      el.classList.add("drag");
    });
    el.addEventListener("pointermove", (e) => {
      if (!el.hasPointerCapture(e.pointerId)) return;
      const r = $("ed-stage").getBoundingClientRect();
      ed.pts[i] = [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
                   Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
      drawEditor();
    });
    const up = (e) => { el.classList.remove("drag"); if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId); };
    el.addEventListener("pointerup", up);
    el.addEventListener("pointercancel", up);
  });
  window.addEventListener("resize", () => { if (!$("editor").hidden) layoutEditor(); });
  $("ed-cancel").addEventListener("click", closeEditor);
  $("ed-ok").addEventListener("click", () => {
    const p = ed.page;
    p.corners = ed.pts.map((c) => [+c[0].toFixed(4), +c[1].toFixed(4)]);
    p.manual = true;
    closeEditor();
    runScan(p);
  });

  function render() {
    const box = $("pages");
    if (!box) return;
    box.innerHTML = "";
    pages.forEach((p, i) => {
      const d = document.createElement("div");
      d.className = "page" + (p.busy ? " busy" : "");
      const img = document.createElement("img");
      img.src = p.preview;
      img.alt = `${t("page")} ${i + 1}`;
      d.appendChild(img);
      const n = document.createElement("span");
      n.className = "page-n";
      n.textContent = i + 1;
      d.appendChild(n);
      if (p.busy) {
        const s = document.createElement("div");
        s.className = "page-busy";
        s.innerHTML = '<span class="spin"></span>';
        s.appendChild(document.createTextNode(t("scanning")));
        d.appendChild(s);
      } else if (p.blurry) {
        const w = document.createElement("span");
        w.className = "page-warn bad";
        w.textContent = t("blurry");
        d.appendChild(w);
      } else if (p.processed && !p.found) {
        const w = document.createElement("span");
        w.className = "page-warn";
        w.textContent = t("noedge");
        d.appendChild(w);
      }
      if (!p.busy && p.orig) {
        img.addEventListener("click", () => openEditor(p));
        const c = document.createElement("button");
        c.className = "page-crop";
        c.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 2v16h16M2 6h16v16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
        c.appendChild(document.createTextNode(t("adjust")));
        c.onclick = () => openEditor(p);
        d.appendChild(c);
      }
      const x = document.createElement("button");
      x.className = "page-x";
      x.setAttribute("aria-label", t("remove"));
      x.textContent = "×";
      x.onclick = () => { if (p.origUrl) URL.revokeObjectURL(p.origUrl); pages = pages.filter((q) => q !== p); render(); };
      d.appendChild(x);
      box.appendChild(d);
    });
    const busy = pages.some((p) => p.busy);
    $("camera-txt").textContent = pages.length ? t("more") : t("photo");
    $("camera-label").classList.toggle("secondary", pages.length > 0);
    $("camera-label").hidden = pages.length >= CFG.maxPages;
    $("send").disabled = !pages.length || busy;
    $("send-count").textContent = pages.length ? `(${pages.length} ${pages.length === 1 ? t("page") : t("pages")})` : "";
  }

  // ------------------------------------------------------------ Offline-Warteschlange (IndexedDB)
  function idb() {
    return new Promise((res, rej) => {
      const r = indexedDB.open("objekt-scanner", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("queue", { keyPath: "id", autoIncrement: true });
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }
  async function qOp(mode, fn) {
    const d = await idb();
    return new Promise((res, rej) => {
      const tx = d.transaction("queue", mode);
      const req = fn(tx.objectStore("queue"));
      tx.oncomplete = () => res(req && req.result);
      tx.onerror = () => rej(tx.error);
    });
  }
  const qAdd = (item) => qOp("readwrite", (s) => s.add(item));
  const qAll = () => qOp("readonly", (s) => s.getAll());
  const qDel = (id) => qOp("readwrite", (s) => s.delete(id));

  async function updatePending() {
    try {
      const all = (await qAll()).filter((x) => x.token === CFG.token);
      const el = $("pending");
      el.hidden = !all.length;
      el.textContent = t("pending").replace("{n}", all.length);
    } catch (e) { /* IndexedDB nicht verfügbar */ }
  }

  // Ergebnis: "ok" | "offline" | "error"
  async function upload(item) {
    const fd = new FormData();
    fd.append("doctype", item.doctype);
    fd.append("note", item.note || "");
    item.pages.forEach((p, i) => {
      fd.append("pages", p.blob, `seite${i + 1}.jpg`);
      fd.append("processed", p.processed ? "1" : "0");
      fd.append("corners", p.corners || "");
    });
    try {
      const r = await fetch(`/o/${item.token}/submit`, { method: "POST", body: fd });
      if (r.ok) return "ok";
      return r.status >= 500 || r.status === 429 ? "offline" : "error";
    } catch (e) {
      return "offline";
    }
  }

  let flushing = false;
  async function flush() {
    if (flushing) return;
    flushing = true;
    try {
      for (const item of await qAll()) {
        const res = await upload(item);
        if (res === "ok" || res === "error") await qDel(item.id);
        else break;
      }
    } catch (e) { /* später erneut */ }
    flushing = false;
    updatePending();
  }
  window.addEventListener("online", flush);
  setInterval(() => { if (navigator.onLine) flush(); }, 60000);

  $("send").addEventListener("click", async () => {
    const btn = $("send");
    btn.disabled = true;
    btn.textContent = t("sending");
    $("error").hidden = true;
    const item = {
      token: CFG.token, doctype: docType, note: $("note").value.trim(), ts: Date.now(),
      pages: pages.map((p) => ({ blob: p.processed ? p.blob : p.orig, processed: p.processed,
        corners: p.manual && p.corners ? JSON.stringify(p.corners) : "" })),
    };
    const res = await upload(item);
    btn.innerHTML = `<span data-t="send">${t("send")}</span> <span id="send-count"></span>`;
    if (res === "error") {
      $("error").textContent = t("error");
      $("error").hidden = false;
      render();
      return;
    }
    if (res === "offline") {
      try { await qAdd(item); } catch (e) {
        $("error").textContent = t("error");
        $("error").hidden = false;
        render();
        return;
      }
    }
    $("done-ico").textContent = res === "ok" ? "✓" : "⏳";
    $("done-ico").classList.toggle("wait", res !== "ok");
    $("done-msg").textContent = res === "ok" ? t("done") : t("queued");
    pages = [];
    show("step-done");
    updatePending();
  });

  // ------------------------------------------------------------ Start
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  }
  applyLang();
  flush();
})();
