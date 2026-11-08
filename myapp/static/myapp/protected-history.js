// History snapshots can be restored without making an HTTP request.
// Hide persisted content before leaving, then recheck the session on restore.
window.addEventListener('pagehide', (event) => {
    if (event.persisted) {
        document.documentElement.style.visibility = 'hidden';
    }
});

window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
        window.location.reload();
    }
});
