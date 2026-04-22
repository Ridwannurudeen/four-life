// Onboarding page — minimal behavior.
//
// Only one real interactive bit: a "Close this tab" button. Chrome extension
// pages can't close themselves via window.close() the way a popup can, so we
// route through the tabs API. All outbound links are plain <a target="_blank">.

document.addEventListener("DOMContentLoaded", () => {
  const closeBtn = document.getElementById("btn-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      if (chrome?.tabs?.getCurrent) {
        chrome.tabs.getCurrent((tab) => {
          if (tab?.id != null) chrome.tabs.remove(tab.id);
          else window.close();
        });
      } else {
        window.close();
      }
    });
  }
});
