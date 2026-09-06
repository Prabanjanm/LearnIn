/*
    Deterrents only, per the spec this implements - none of this makes a
    screenshot, screen recording, or a photo of the screen impossible,
    and this file must never claim otherwise. A browser (or JavaScript
    running in it) has no way to see or block what the operating system
    or another device does with the pixels once they're on screen.
    There is no supported browser API that reliably reports "the user
    just took a screenshot" - the Screen Capture API
    (navigator.mediaDevices.getDisplayMedia) is for THIS page requesting
    to *share* the screen, it tells us nothing about an external
    capture, so it is deliberately not used here as if it were a
    detector. What this file *can* do, and does:

    1. Remove the easy first-party ways to copy/print/save/export the
       report from inside the browser itself (text selection, the
       context menu, Ctrl/Cmd+P/C/S/U) - scoped to this page only.
    2. Best-effort, temporary blanking of the report when a keyboard
       shortcut commonly bound to a screenshot/snip tool is detected:
       - The dedicated PrintScreen key. Windows historically handles a
         bare PrintScreen entirely at the OS level before it ever
         reaches a web page, so this fires inconsistently across
         browsers/OS versions - treat it as a bonus signal, not a
         guarantee.
       - Ctrl/Cmd+Shift+S (Windows Snip & Sketch / most browsers' and
         OSes' "snip" binding) - an ordinary modifier+key combo, so it
         reaches `keydown` far more reliably than bare PrintScreen.
       This is a deterrent for the in-browser-detectable subset of
       capture actions only. Print Screen implementations that don't
       expose an event, OS screenshot utilities invoked from outside
       the browser window, external screen recorders, and another
       device's camera are all completely invisible to this script -
       nothing here claims otherwise.
*/
(function () {
    const report = document.querySelector("[data-cbt-report]");
    if (!report) return;

    report.addEventListener("contextmenu", (event) => event.preventDefault());
    report.addEventListener("copy", (event) => event.preventDefault());
    report.addEventListener("cut", (event) => event.preventDefault());

    let restoreTimer = null;

    function triggerProtection() {
        report.setAttribute("data-report-protected", "true");

        // "Restore after the capture attempt has ended" - a screenshot
        // is effectively instantaneous, so there's no real "end" event
        // to wait for; a short fixed delay is the best available proxy,
        // long enough to cover the OS/browser capture pipeline.
        window.clearTimeout(restoreTimer);
        restoreTimer = window.setTimeout(() => {
            report.removeAttribute("data-report-protected");
        }, 1500);
    }

    // Attached on `document`, not just `report`, because these
    // shortcuts aren't scoped to whatever element has focus the way a
    // copy event is - but this whole listener only exists on this page
    // (see the early return above), so no other LearnIn page is
    // affected, and it never triggers on plain window blur/focus/tab
    // switches (those are not screenshot signals and firing on them
    // would just be visual noise for completely ordinary browsing).
    document.addEventListener("keydown", (event) => {
        const key = event.key.toLowerCase();
        const withModifier = event.ctrlKey || event.metaKey;
        const isPrint = withModifier && key === "p";
        const isSave = withModifier && key === "s";
        const isViewSource = withModifier && key === "u";
        const isCopy = withModifier && key === "c" && report.contains(document.activeElement);
        const isSnipShortcut = withModifier && event.shiftKey && key === "s";
        const isPrintScreen = event.key === "PrintScreen";

        if (isPrint || isSave || isViewSource || isCopy || isSnipShortcut) {
            event.preventDefault();
        }

        if (isSnipShortcut || isPrintScreen || isPrint) {
            triggerProtection();
        }
    });

    // Some browsers only ever deliver a bare PrintScreen on keyup, not
    // keydown - listening on both is still best-effort, not a guarantee.
    document.addEventListener("keyup", (event) => {
        if (event.key === "PrintScreen") {
            triggerProtection();
        }
    });
})();
