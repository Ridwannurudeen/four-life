// MV3 popup — no inline handlers, so the anchor click is wired here.
// The anchor already has the correct href; this just ensures it opens in a new tab
// even when the popup closes before the browser finishes the navigation.
document.addEventListener("DOMContentLoaded", () => {
  const link = document.getElementById("open-radar");
  if (!link) return;
  link.addEventListener("click", (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: link.href });
    window.close();
  });
});
