/**
 * Runtime configuration — Project 3 (Phase 3)
 *
 * `deploy.sh` rewrites the placeholder below with the deployed Function App
 * URL before uploading this file.  That substitution is required, not
 * cosmetic: the frontend is served from the storage account's static website,
 * which has no /api reverse proxy, so a relative "/api" would resolve against
 * the storage domain and return 404 for every request.  (Only Azure Static Web
 * Apps proxies /api, and this project does not use it.)
 *
 * Resolution order:
 *   1. the value substituted at deploy time
 *   2. http://localhost:7071/api when opened locally (the `func start` default)
 *   3. same-origin /api, correct only behind a reverse proxy
 */
(function () {
  var configured = "__API_BASE__";
  var isPlaceholder = configured.indexOf("__API_BASE") === 0;

  var host = window.location.hostname;
  var isLocal = host === "localhost" || host === "127.0.0.1" || host === "";

  var base;
  if (!isPlaceholder && configured) {
    base = configured;
  } else if (isLocal) {
    base = "http://localhost:7071/api";
  } else {
    base = "/api";
  }

  window.API_BASE = base.replace(/\/+$/, "");
})();
