const registration = document.getElementById('registration');
for (const field of ['username', 'email']) {
    const input = registration.elements[field];
    const feedback = document.createElement('span');
    feedback.id = `${field}-availability`;
    feedback.setAttribute('aria-live', 'polite');
    input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), feedback.id].filter(Boolean).join(' '));
    input.after(feedback);
    let timer;
    let revision = 0;
    let controller;
    input.addEventListener('input', () => {
        clearTimeout(timer);
        controller?.abort();
        const current = ++revision;
        feedback.textContent = '';
        if (!input.value.trim()) return;
        timer = setTimeout(async () => {
            controller = new AbortController();
            const url = new URL(registration.dataset.availabilityUrl, window.location.origin);
            url.search = new URLSearchParams({field, value: input.value});
            try {
                const response = await fetch(url, {signal: controller.signal});
                if (!response.ok) throw new Error('Availability request failed');
                const result = await response.json();
                if (current === revision) feedback.textContent = result.message;
            } catch (error) {
                if (error.name !== 'AbortError' && current === revision) {
                    feedback.textContent = 'Availability could not be checked. Submit to validate.';
                }
            }
        }, 400);
    });
}
