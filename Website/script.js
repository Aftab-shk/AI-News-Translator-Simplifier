document.addEventListener("DOMContentLoaded", () => {
  const ensureElement = (id, tag = 'div', parent = document.body, attrs = {}) => {
    let el = document.getElementById(id);
    if (!el) {
      el = document.createElement(tag);
      el.id = id;
      Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, v));
      parent.appendChild(el);
    }
    return el;
  };

  // ensure essential containers exist
  const resultContainer = ensureElement('result-container', 'div', document.body);
  const outputEl = ensureElement('output', 'div', resultContainer);
  const loaderEl = document.getElementById('loader') || (function(){
    const l = document.createElement('div');
    l.id = 'loader';
    l.className = 'hidden';
    // spinner
    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    l.appendChild(spinner);
    const txt = document.createElement('p');
    txt.innerText = 'Processing...';
    l.appendChild(txt);
    resultContainer.appendChild(l);
    return l;
  })();

  const ui = {
    inputText: document.getElementById("inputText"),
    processBtn: document.getElementById("processBtn"),
    languageSelect: document.getElementById("languageSelect"),
    evaluateToggle: document.getElementById("evaluateToggle"),
    goldSummary: document.getElementById("goldSummary"),
    goldTranslation: document.getElementById("goldTranslation"),
    keyPoints: document.getElementById("keyPoints"),
    loader: loaderEl,
    resultContainer: resultContainer,
    output: outputEl,
    evaluationBox: null,
    copyBtn: document.getElementById("copyBtn"),
    buttonText: document.getElementById("button-text"),
  };

  // Ensure button-text span exists inside the button
  if (ui.processBtn && !ui.buttonText) {
    const span = document.createElement("span");
    span.id = 'button-text';
    span.innerText = ui.processBtn.textContent.trim() || 'Process Text';
    ui.processBtn.innerHTML = '';
    ui.processBtn.appendChild(span);
    ui.buttonText = span;
  }

  const backendUrl = "/process";

  function setUiLoadingState(isLoading) {
    if (isLoading) {
      if (ui.processBtn) ui.processBtn.disabled = true;
      if (ui.buttonText) ui.buttonText.innerText = "Processing...";
      if (ui.resultContainer) ui.resultContainer.classList.add('hidden');
      if (ui.loader) ui.loader.classList.remove('hidden');
      ui.loader.setAttribute('aria-busy', 'true');
    } else {
      if (ui.loader) ui.loader.classList.add('hidden');
      if (ui.resultContainer) ui.resultContainer.classList.remove('hidden');
      if (ui.processBtn) ui.processBtn.disabled = false;
      if (ui.buttonText) ui.buttonText.innerText = "Process Text";
      if (ui.loader) ui.loader.removeAttribute('aria-busy');
    }
  }

  function displayResult(text) {
    if (ui.output) ui.output.innerText = text;
  }

  function displayEvaluation(evalObj, topLevelData) {
    if (!ui.resultContainer) return;
    let box = document.getElementById('evaluation-box');
    if (!box) {
      box = document.createElement('div');
      box.id = 'evaluation-box';
      box.className = 'evaluation-box';
      ui.resultContainer.appendChild(box);
      ui.evaluationBox = box;
    }
    if (!evalObj) {
      box.innerHTML = '';
      return;
    }

    const lines = [];
    const fromName = evalObj.source_language_name ?? "Unknown";
    const toName = evalObj.target_language ?? "Unknown";
    lines.push(`Translated: ${fromName} → ${toName}`);

    const respTime = evalObj.response_time_seconds ?? 0;
    lines.push(`Response time: ${Number(respTime).toFixed(3)}s`);

    const sim = evalObj.summary_similarity_pct ?? evalObj.summary_similarity ?? 0;
    lines.push(`Summary similarity: ${Number(sim).toFixed(2)}%`);

    const trans = evalObj.translation_consistency_pct ?? evalObj.translation_consistency ?? 0;
    lines.push(`Translation consistency: ${Number(trans).toFixed(2)}%`);

    box.innerHTML = '<h3>Evaluation</h3><p>' + lines.join('<br>') + '</p>';
  }

  async function handleTextProcessing(articleText, targetLang) {
    if (!articleText || !articleText.trim()) {
      displayResult("Please enter some text to process.");
      if (ui.resultContainer) ui.resultContainer.classList.remove('hidden');
      return;
    }

    setUiLoadingState(true);

    try {
      const payload = { text: articleText, target_lang_name: targetLang };
      const response = await fetch(backendUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const txt = await response.text().catch(() => '');
        throw new Error(txt || `HTTP ${response.status}`);
      }

      const data = await response.json();

      if (!data.evaluation) data.evaluation = {};
      data.evaluation.response_time_seconds = data.evaluation.response_time_seconds ?? data.response_time_seconds ?? 0;
      data.evaluation.source_language_name = data.evaluation.source_language_name ?? data.source_language_name ?? data.source_language ?? 'Unknown';
      data.evaluation.target_language = data.evaluation.target_language ?? data.target_language ?? targetLang;

      window.lastResponse = data;

      if (data.output) {
        displayResult(data.output);
      } else {
        displayResult("No output returned from server.");
      }

      displayEvaluation(data.evaluation, data);

    } catch (err) {
      let friendlyErrorMessage = "An error occurred while processing.";
      if (err instanceof TypeError && err.message.includes('Failed to fetch')) {
        friendlyErrorMessage = "Failed to reach the backend. Is the backend running?";
      } else if (err.message) {
        friendlyErrorMessage = err.message;
      }
      displayResult(friendlyErrorMessage);
      console.error(err);
    } finally {
      setUiLoadingState(false);
    }
  }

  if (ui.processBtn) {
    ui.processBtn.addEventListener("click", () => {
      handleTextProcessing(
        ui.inputText ? ui.inputText.value : '',
        ui.languageSelect ? ui.languageSelect.value : 'English'
      );
    });
  }

  if (ui.copyBtn) {
    ui.copyBtn.addEventListener("click", () => {
      const textToCopy = ui.output ? ui.output.innerText : '';
      if (textToCopy) {
        navigator.clipboard.writeText(textToCopy).catch(err => console.error('Copy failed', err));
      }
    });
  }

  // transient scrollbar helper (unchanged)
  (function enableTransientScrollbar() {
    const targets = [document.documentElement, document.body, ...Array.from(document.querySelectorAll('.container'))];
    let timer = null;

    function addShow() {
      clearTimeout(timer);
      targets.forEach(t => t.classList.add('show-scrollbar'));
      timer = setTimeout(removeShow, 900);
    }

    function removeShow() {
      targets.forEach(t => t.classList.remove('show-scrollbar'));
    }

    ['scroll', 'wheel', 'touchstart', 'touchmove', 'keydown', 'mousemove'].forEach(evt => {
      window.addEventListener(evt, addShow, { passive: true, capture: true });
    });

    window.addEventListener('mouseenter', addShow);
    window.addEventListener('mouseleave', removeShow);
    window.__showScroll = () => { addShow(); setTimeout(removeShow, 3000); };
  })();

  const evalToggle = document.getElementById('evaluateToggle');
  const evalFields = document.getElementById('evalFields');
  if (evalToggle && evalFields) {
    evalToggle.addEventListener('change', () => {
      if (evalToggle.checked) evalFields.classList.remove('hidden'); else evalFields.classList.add('hidden');
    });
  }
});