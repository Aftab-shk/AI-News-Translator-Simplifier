chrome.runtime.onInstalled.addListener(() => {
  // Parent menu creation is the same...
  chrome.contextMenus.create({
    id: "simplifyTranslateParent",
    title: "Simplify & Translate",
    contexts: ["selection"]
  });
  
  // Updated list to include all supported Indian languages to match popup.html
  const languages = [
      "English", "Hindi", "Gujarati", "Punjabi", "Bengali", 
      "Marathi", "Tamil", "Telugu", "Urdu", "Kannada", "Malayalam", "Odia", "Assamese", "Sanskrit"
  ];
  
  for (const lang of languages) {
    chrome.contextMenus.create({
      id: `simplifyTranslate_${lang}`,
      parentId: "simplifyTranslateParent",
      title: `→ ${lang}`,
      contexts: ["selection"]
    });
  }
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId.startsWith("simplifyTranslate_") && info.selectionText) {
    const targetLang = info.menuItemId.replace("simplifyTranslate_", "");

    // Always open popup with target language + text
    chrome.windows.create({
      url: "popup.html",
      type: "popup",
      width: 360,
      height: 500
    }, (win) => {
      // Use a listener to ensure the popup is ready before sending the message
      const listener = (tabId, changeInfo, tab) => {
        if (tabId === win.tabs[0].id && changeInfo.status === 'complete') {
          chrome.runtime.sendMessage({
            action: "processText",
            text: info.selectionText,
            targetLang: targetLang
          });
          chrome.tabs.onUpdated.removeListener(listener);
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    });
  }
});

