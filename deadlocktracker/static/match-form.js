// A hero can only be in a match once. In each match form, disable a hero in
// every dropdown once it has been picked in another one. The server checks
// this too; this just stops the mistake before the form is submitted.
document.querySelectorAll("form").forEach((form) => {
  const selects = form.querySelectorAll("select[data-hero-select]");
  if (!selects.length) return;

  const sync = () => {
    const pickedBy = new Map(); // hero id -> selects that picked it
    selects.forEach((s) => {
      if (s.value) pickedBy.set(s.value, (pickedBy.get(s.value) || []).concat(s));
    });
    selects.forEach((s) => {
      for (const opt of s.options) {
        if (!opt.value) continue;
        const users = pickedBy.get(opt.value) || [];
        opt.disabled = users.length > 0 && !users.includes(s);
      }
    });
  };

  selects.forEach((s) => s.addEventListener("change", sync));
  form.addEventListener("reset", () => setTimeout(sync));
  sync();

  // Lanes are 2v2: exactly 2 lane opponents. Once 2 are marked, the rest are
  // disabled, and the form won't submit until exactly 2 are marked.
  const opponents = form.querySelectorAll("input[data-lane-opponent]");
  if (!opponents.length) return;
  const syncLane = () => {
    const marked = [...opponents].filter((c) => c.checked).length;
    opponents.forEach((c) => { c.disabled = !c.checked && marked >= 2; });
    opponents[0].setCustomValidity(marked === 2 ? "" : `Mark exactly 2 lane opponents (${marked} marked).`);
  };
  opponents.forEach((c) => c.addEventListener("change", syncLane));
  form.addEventListener("reset", () => setTimeout(syncLane));
  syncLane();
});
