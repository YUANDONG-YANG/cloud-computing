/**
 * Frontend Authentication Utilities — Project 3 (Phase 3)
 *
 * Manages JWT token storage, user session state, and authenticated
 * fetch requests.  Uses localStorage for token persistence.
 */

const TOKEN_KEY = "nutrition_jwt";
const USER_KEY = "nutrition_user";

/* ------------------------------------------------------------------
 * Token management
 * ----------------------------------------------------------------*/

function saveToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (e) {
    console.warn("Could not save token:", e);
  }
}

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch (e) {
    return null;
  }
}

function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch (e) {
    console.warn("Could not clear token:", e);
  }
}

/* ------------------------------------------------------------------
 * User info (decoded from JWT or stored on login)
 * ----------------------------------------------------------------*/

function saveUser(user) {
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch (e) {
    console.warn("Could not save user:", e);
  }
}

function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

/**
 * Decode the JWT payload (base64url) WITHOUT verifying the signature.
 *
 * Only ever used to display a name and to pre-empt an expired token. It is
 * not access control: the signature is checked by the API, which rejects
 * anything it did not sign with 401.
 */
function decodeJWT(token) {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    let payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (payload.length % 4) payload += "=";
    return JSON.parse(atob(payload));
  } catch (e) {
    return null;
  }
}

/* ------------------------------------------------------------------
 * Session state
 * ----------------------------------------------------------------*/

function isAuthenticated() {
  const token = getToken();
  if (!token) return false;

  const claims = decodeJWT(token);
  if (!claims) return false;

  // Check expiry
  if (claims.exp) {
    const now = Math.floor(Date.now() / 1000);
    if (claims.exp < now) {
      clearToken();
      return false;
    }
  }
  return true;
}

function getCurrentUser() {
  const stored = getUser();
  if (stored) return stored;

  const token = getToken();
  if (!token) return null;
  const claims = decodeJWT(token);
  if (!claims) return null;

  return {
    id: claims.sub || "",
    email: claims.email || "",
    name: claims.name || "",
  };
}

/* ------------------------------------------------------------------
 * Authenticated fetch
 * ----------------------------------------------------------------*/

/**
 * Wrapper around fetch that adds the Authorization: Bearer header.
 */
async function authFetch(url, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(url, { ...options, headers });
}

/* ------------------------------------------------------------------
 * Logout
 * ----------------------------------------------------------------*/

function logout() {
  clearToken();
  window.location.href = "login.html";
}

/* ------------------------------------------------------------------
 * Handle OAuth redirect (token in URL)
 * ----------------------------------------------------------------*/

function handleOAuthRedirect() {
  // The backend returns the token in the URL fragment so it never reaches a
  // server log or a referrer header.
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  const params = new URLSearchParams(hash);
  const token = params.get("token");
  if (token) {
    saveToken(token);
    const claims = decodeJWT(token);
    if (claims) {
      saveUser({
        id: claims.sub || "",
        email: claims.email || "",
        name: claims.name || "",
      });
    }
    // Clean the URL
    window.history.replaceState({}, document.title, window.location.pathname);
    return true;
  }
  return false;
}
