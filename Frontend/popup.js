// popup.js

document.addEventListener('DOMContentLoaded', () => {
  const ui = {
    inputText: document.getElementById('inputText'),
    languageSelect: document.getElementById('languageSelect'),
    processBtn: document.getElementById('processBtn'),
    loader: document.getElementById('loader'),
    resultBox: document.getElementById('resultBox'),
    output: document.getElementById('output'),
    evaluateToggle: document.getElementById('evaluateToggle'),
    goldSummary: document.getElementById('goldSummary'),
    goldTranslation: document.getElementById('goldTranslation'),
    keyPoints: document.getElementById('keyPoints'),
    popupEvalFields: document.getElementById('popupEvalFields'),
    detectedLang: document.getElementById('detectedLang'),
    copyBtn: document.getElementById('copyBtn'),
  };

  // Ensure elements exist (warnings only)
  if (!ui.processBtn) console.warn('processBtn not found in popup.');
  if (!ui.loader) console.warn('loader not found in popup.');
  if (!ui.resultBox) console.warn('resultBox not found in popup.');

  // use the exact URL your backend listens on (port 5500)
  const backendUrl = "http://127.0.0.1:5500/process";

  function setUiLoadingState(isLoading) {
    if (!ui.processBtn) return;
    if (isLoading) {
      ui.processBtn.disabled = true;
      ui.processBtn.textContent = 'Processing...';
      if (ui.resultBox) ui.resultBox.classList.add('hidden');
      if (ui.loader) {
        ui.loader.classList.remove('hidden');
        ui.loader.classList.add('show-loader');
      }
    } else {
      if (ui.loader) {
        ui.loader.classList.remove('show-loader');
        ui.loader.classList.add('hidden');
      }
      if (ui.resultBox) ui.resultBox.classList.remove('hidden');
      ui.processBtn.disabled = false;
      ui.processBtn.textContent = 'Process Text';
    }
  }

  async function handleTextProcessing(text, targetLang) {
    if (!text || !text.trim()) {
      if (ui.output) ui.output.textContent = 'Please enter some text.';
      if (ui.resultBox) ui.resultBox.classList.remove('hidden');
      return;
    }

    setUiLoadingState(true);
    if (ui.detectedLang) ui.detectedLang.textContent = '';
    if (ui.output) ui.output.textContent = '';

    try {
      const payload = { text: text, target_lang_name: targetLang };
      // Evaluation is automatic on the backend; only send minimal payload

      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const txt = await res.text().catch(() => '');
        throw new Error(txt || `HTTP ${res.status}`);
      }

      const data = await res.json();
      if (ui.output) ui.output.textContent = data.output || 'No output.';
      // show evaluation if present
      if (data.evaluation) {
        const ev = data.evaluation;
        let txt = '';
        // mention target language selected in popup
        try { if (ui.languageSelect) txt += `Target language: ${ui.languageSelect.value}\n`; } catch(e) {}
        if (ev.response_time_s != null) txt += `Response time: ${ev.response_time_s?.toFixed(3)}s\n`;
        if (ev.summary_similarity_pct != null) txt += `Summary similarity: ${ev.summary_similarity_pct.toFixed(2)}%\n`;
        else if (ev.summary_similarity != null) txt += `Summary similarity: ${(ev.summary_similarity*100).toFixed(2)}%\n`;
        if (ev.translation_consistency_pct != null) txt += `Translation consistency: ${ev.translation_consistency_pct.toFixed(2)}%\n`;
        else if (ev.translation_consistency != null) txt += `Translation consistency: ${(ev.translation_consistency*100).toFixed(2)}%\n`;
        if (ev.keypoint_coverage) txt += `Keypoint coverage: ${(ev.keypoint_coverage.coverage*100).toFixed(1)}%\n`;
        // append to output area
        if (ui.output) ui.output.textContent += '\n\n--- Evaluation ---\n' + txt;
      }
      if (data.detected_language && ui.detectedLang) {
        ui.detectedLang.textContent = `Detected language: ${data.detected_language}`;
      }
      if (ui.resultBox) ui.resultBox.classList.remove('hidden');
    } catch (e) {
      if (ui.output) ui.output.textContent = `Error: ${e.message || e}`;
      if (ui.resultBox) ui.resultBox.classList.remove('hidden');
      console.error(e);
    } finally {
      setUiLoadingState(false);
    }
  }

  if (ui.processBtn) {
    ui.processBtn.addEventListener('click', () => {
      handleTextProcessing(ui.inputText ? ui.inputText.value : '', ui.languageSelect ? ui.languageSelect.value : 'English');
    });
  }

  if (ui.copyBtn) {
    ui.copyBtn.addEventListener('click', () => {
      const text = ui.output ? ui.output.textContent : '';
      if (!text) return;
      navigator.clipboard.writeText(text).catch(err => console.error('Copy failed', err));
    });
  }

  // toggle evaluation fields visibility in popup
  if (ui.evaluateToggle && ui.popupEvalFields) {
    ui.evaluateToggle.addEventListener('change', () => {
      if (ui.evaluateToggle.checked) ui.popupEvalFields.classList.remove('hidden'); else ui.popupEvalFields.classList.add('hidden');
    });
  }

  // Receive programmatic requests from background script (context menu)
  if (chrome && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg?.action === 'processText') {
        if (msg.text && ui.inputText) ui.inputText.value = msg.text;
        if (msg.targetLang && ui.languageSelect) {
          const opt = Array.from(ui.languageSelect.options).find(o => o.value === msg.targetLang);
          if (opt) ui.languageSelect.value = msg.targetLang;
        }
        handleTextProcessing(ui.inputText ? ui.inputText.value : '', ui.languageSelect ? ui.languageSelect.value : 'English');
      }
    });
  }

  // --- transient scrollbar for popup (show on scroll/hover/interact) ---
  (function enableTransientScrollbar() {
    const targets = [document.documentElement, document.body, ...Array.from(document.querySelectorAll('.container'))];
    let timer = null;

    function showOnce() {
      clearTimeout(timer);
      targets.forEach(t => t.classList.add('show-scrollbar'));
      timer = setTimeout(() => {
        targets.forEach(t => t.classList.remove('show-scrollbar'));
      }, 800);
    }

    const events = ['scroll', 'wheel', 'touchstart', 'touchmove', 'mousemove', 'keydown'];
    events.forEach(e => window.addEventListener(e, showOnce, { passive: true, capture: true }));

    // show while mouse is over popup, hide when mouse leaves
    targets.forEach(t => {
      t.addEventListener('mouseenter', showOnce);
      t.addEventListener('mouseleave', () => targets.forEach(x => x.classList.remove('show-scrollbar')));
    });

    // expose helper for debugging
    window.__popupShowScroll = () => { showOnce(); setTimeout(() => targets.forEach(t => t.classList.remove('show-scrollbar')), 3000); };
  })();
});
