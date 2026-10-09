/* Localize visible numeric text in the Arabic UI only. Values, URLs and identifiers stay intact. */
(() => {
  const digitMap = {"0":"٠", "1":"١", "2":"٢", "3":"٣", "4":"٤", "5":"٥", "6":"٦", "7":"٧", "8":"٨", "9":"٩"};
  const asciiLetter = /[A-Za-z]/;
  const isoDate = /^\d{4}-\d{2}(?:-\d{2})?$/;
  const protectedSelector = "script,style,textarea,input,code,pre,kbd,samp,[contenteditable='true']";

  function localizeNumericText(text) {
    return String(text).split(/(\s+)/).map((token) => {
      if (!token) return token;
      // Keep ISO date separators, while using Arabic grouping/decimal marks for values.
      if (/^\d{4}-\d{2}(?:-\d{2})?$/.test(token)) {
        return token.replace(/[0-9]/g, (digit) => digitMap[digit]);
      }
      // Compact financial values use the app's k/M suffixes (for example 9.7k).
      const compact = token.match(/^([+\-−]?\d+(?:[,.]\d+)?)([kM])$/);
      if (compact) return compact[1].replace(",", "٬").replace(".", "٫").replace(/[0-9]/g, (digit) => digitMap[digit]) + compact[2];
      const number = token.match(/^([+\-−]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(%?)$/);
      if (number) {
        const localized = number[1] + number[2].replaceAll(",", "٬") + (number[3] || "").replace(".", "٫") + number[4];
        return localized.replace(/[0-9]/g, (digit) => digitMap[digit]);
      }
      // Alphanumeric tokens are often tickers, version strings, filenames or transaction references.
      if (asciiLetter.test(token)) return token;
      return token.replace(/[0-9]/g, (digit) => digitMap[digit]);
    }).join("");
  }

  function excludedTextNode(node) {
    let parent = node.parentElement;
    while (parent) {
      if (parent.matches(protectedSelector)) return true;
      if (parent.classList?.contains("code")) {
        const value = parent.textContent.trim();
        // ISO dates use the code style in registers; other code-styled strings are identifiers.
        if (!isoDate.test(value)) return true;
      }
      parent = parent.parentElement;
    }
    return false;
  }

  function localizeTextNode(node) {
    if (!excludedTextNode(node)) {
      const localized = localizeNumericText(node.nodeValue);
      if (localized !== node.nodeValue) node.nodeValue = localized;
    }
  }

  function localizeAttribute(element, name) {
    const value = element.getAttribute(name);
    if (value == null || (element.matches(protectedSelector) && name !== "placeholder") || element.classList?.contains("code")) return;
    const localized = localizeNumericText(value);
    if (localized !== value) element.setAttribute(name, localized);
  }

  function localizeTree(root) {
    if (root.nodeType === Node.TEXT_NODE) {
      localizeTextNode(root);
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
    if (root.nodeType === Node.ELEMENT_NODE) {
      for (const name of ["aria-label", "title", "data-tip", "placeholder"]) localizeAttribute(root, name);
      if (root.matches(protectedSelector)) return;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) localizeTextNode(node);
    if (root.querySelectorAll) {
      root.querySelectorAll("[aria-label], [title], [data-tip], [placeholder]").forEach((element) => {
        for (const name of ["aria-label", "title", "data-tip", "placeholder"]) localizeAttribute(element, name);
      });
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = {localizeNumericText};
  if (typeof document === "undefined" || !/^ar(?:-|$)/i.test(document.documentElement.lang)) return;

  localizeTree(document.body);
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") localizeTextNode(record.target);
      for (const node of record.addedNodes || []) localizeTree(node);
      if (record.type === "attributes") localizeAttribute(record.target, record.attributeName);
    }
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["aria-label", "title", "data-tip", "placeholder"]
  });
})();
