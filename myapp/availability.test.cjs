const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('availability debounces each field independently and ignores stale responses', async () => {
    const timers = new Map();
    const requests = [];
    let id = 0;
    const elements = Object.fromEntries(['username', 'email'].map(name => [name, {
        value: '', getAttribute: () => null, setAttribute() {},
        after(span) { this.feedback = span; },
        addEventListener(event, listener) { this.input = listener; },
    }]));
    const context = {
        document: {
            getElementById: () => ({elements, dataset: {availabilityUrl: '/availability/'}}),
            createElement: () => ({textContent: '', setAttribute() {}}),
        },
        window: {location: {origin: 'https://portalign.example'}},
        URL, URLSearchParams, AbortController,
        setTimeout(fn, delay) { assert.equal(delay, 400); timers.set(++id, fn); return id; },
        clearTimeout(key) { timers.delete(key); },
        fetch(url) { return new Promise(resolve => requests.push({url, resolve})); },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/myapp/availability.js'), 'utf8'), context);
    const type = (field, value) => { elements[field].value = value; elements[field].input(); };
    type('username', 'first');
    type('username', 'second');
    type('email', 'person@example.com');
    assert.equal(timers.size, 2);
    assert.equal(requests.length, 0);
    const pending = [...timers.values()].map(fn => fn());
    timers.clear();
    assert.equal(requests[0].url.searchParams.get('value'), 'second');
    assert.equal(requests[1].url.searchParams.get('field'), 'email');
    type('username', 'latest');
    requests[0].resolve({ok: true, json: async () => ({message: 'Stale'})});
    requests[1].resolve({ok: true, json: async () => ({message: 'Available.'})});
    await Promise.all(pending);
    assert.equal(elements.username.feedback.textContent, '');
    assert.equal(elements.email.feedback.textContent, 'Available.');
    const latest = [...timers.values()][0]();
    requests[2].resolve({ok: true, json: async () => ({message: 'Already in use.'})});
    await latest;
    assert.equal(elements.username.feedback.textContent, 'Already in use.');
});
