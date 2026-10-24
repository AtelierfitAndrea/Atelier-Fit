const READY_TITLE = "Il tuo look è pronto · MyAtelier";

// If the user switched tab while waiting, flash the tab title until they come back.
export const notifyTabReady = () => {
  if (!document.hidden) return;
  const original = document.title;
  let on = false;
  const timer = setInterval(() => { on = !on; document.title = on ? READY_TITLE : original; }, 1000);
  document.title = READY_TITLE;
  const back = () => {
    if (document.hidden) return;
    clearInterval(timer);
    document.title = original;
    document.removeEventListener("visibilitychange", back);
  };
  document.addEventListener("visibilitychange", back);
};
