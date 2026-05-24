// API base: same-origin in production, override here for separate backend.
window.config = {
  API_BASE_URL: window.location.origin,
};
// Convenience for legacy scripts.
var config = window.config;
