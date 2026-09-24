(() => {
    const header = document.querySelector(".landing-header");
    const toggle = document.querySelector(".landing-menu-toggle");
    const menu = document.querySelector("#landing-menu");

    if (!header || !toggle || !menu) return;

    const setMenuOpen = (open) => {
        header.classList.toggle("is-menu-open", open);
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    };

    toggle.addEventListener("click", () => {
        setMenuOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    menu.addEventListener("click", (event) => {
        if (event.target.closest("a")) setMenuOpen(false);
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setMenuOpen(false);
            toggle.focus();
        }
    });
    window.addEventListener("resize", () => {
        if (window.matchMedia("(min-width: 54rem)").matches) setMenuOpen(false);
    });
})();
