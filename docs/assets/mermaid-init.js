window.addEventListener("DOMContentLoaded", () => {
  if (!window.mermaid) {
    return;
  }

  window.mermaid.initialize({
    startOnLoad: true,
    securityLevel: "strict",
    theme: window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "default",
  });
});
