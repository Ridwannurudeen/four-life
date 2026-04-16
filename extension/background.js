// FOUR-LIFE Certified — service worker.
// Kept intentionally minimal. The content script handles all API work directly;
// host_permissions are declared in manifest so fetch() from the content script
// runs with extension origin privileges and avoids CORS surprises.

chrome.runtime.onInstalled.addListener(() => {
  // No-op. Nothing to seed. No storage, no tracking.
});
