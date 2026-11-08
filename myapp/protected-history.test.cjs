const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function setup() {
    const handlers = {};
    const style = {visibility: ''};
    let reloads = 0;
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/myapp/protected-history.js'), 'utf8'), {
        window: {
            addEventListener(name, handler) { handlers[name] = handler; },
            location: {reload() { reloads++; }},
        },
        document: {documentElement: {style}},
    });
    return {handlers, style, reloads: () => reloads};
}

test('restored history snapshots stay hidden and force a session recheck', () => {
    const page = setup();
    page.handlers.pagehide({persisted: true});
    assert.equal(page.style.visibility, 'hidden');
    page.handlers.pageshow({persisted: true});
    assert.equal(page.reloads(), 1);
    assert.equal(page.style.visibility, 'hidden');
});

test('normal page loads do not hide content or trigger reload loops', () => {
    const page = setup();
    page.handlers.pageshow({persisted: false});
    page.handlers.pagehide({persisted: false});
    assert.equal(page.reloads(), 0);
    assert.equal(page.style.visibility, '');
});
