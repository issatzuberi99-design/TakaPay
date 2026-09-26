(function () {
    var root = document.documentElement;
    var toggle = document.getElementById("themeToggle");
    var sun = document.getElementById("iconSun");
    var moon = document.getElementById("iconMoon");
    var meta = document.querySelector('meta[name="theme-color"]');

    function apply(theme, save) {
        root.setAttribute("data-theme", theme);
        if (save) {
            try { window.localStorage.setItem("takapay-theme", theme); } catch (error) { /* Storage can be unavailable. */ }
        }
        if (toggle) {
            toggle.hidden = false;
            toggle.setAttribute("aria-pressed", String(theme === "dark"));
            toggle.setAttribute("aria-label", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
            toggle.setAttribute("title", theme === "dark" ? "Switch to light theme" : "Switch to dark theme");
        }
        if (sun) sun.hidden = theme === "dark";
        if (moon) moon.hidden = theme !== "dark";
        if (meta) meta.setAttribute("content", theme === "dark" ? "#071917" : "#0F766E");
    }

    apply(root.getAttribute("data-theme") || "light", false);
    if (toggle) {
        toggle.addEventListener("click", function () {
            apply(root.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
        });
    }

    if (window.matchMedia) {
        var preference = window.matchMedia("(prefers-color-scheme: dark)");
        var followSystem = function (event) {
            var saved = null;
            try { saved = window.localStorage.getItem("takapay-theme"); } catch (error) { /* Storage can be unavailable. */ }
            if (saved !== "dark" && saved !== "light") apply(event.matches ? "dark" : "light", false);
        };
        if (preference.addEventListener) preference.addEventListener("change", followSystem);
        else if (preference.addListener) preference.addListener(followSystem);
    }
})();
