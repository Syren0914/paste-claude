const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createPasteHandler } = require('../vscode-extension/paste');

function fixture(capture) {
  const sent = [], commands = [], errors = [];
  const listeners = {};
  const listen = name => callback => {
    listeners[name] = callback;
    return { dispose() { delete listeners[name]; } };
  };
  const terminal = { sendText: (...args) => sent.push(args) };
  const vscode = {
    window: {
      activeTerminal: terminal,
      onDidChangeActiveTerminal: listen('terminal'),
      onDidChangeActiveTextEditor: listen('editor'),
      onDidChangeWindowState: listen('window'),
      showErrorMessage: message => errors.push(message)
    },
    commands: { executeCommand: async (name, args) => commands.push(args ? [name, args] : name) }
  };
  const paste = createPasteHandler(vscode, capture, { appendLine() {} });
  return { paste, sent, commands, errors, listeners, vscode };
}

test('image path is delivered directly without submitting or clipboard writes', async () => {
  const f = fixture(async () => ({ kind: 'image', path: 'C:\\User Name\\image.png' }));
  await f.paste();
  assert.deepEqual(f.sent, [['"C:/User Name/image.png" ', false]]);
  assert.deepEqual(f.commands, []);
  assert.deepEqual(Object.keys(f.listeners), []);
});

test('ordinary clipboard uses the IDE native paste', async () => {
  const f = fixture(async () => ({ kind: 'other' }));
  await f.paste();
  assert.deepEqual(f.commands, ['workbench.action.terminal.paste']);
  assert.deepEqual(f.sent, []);
});

for (const [client, sequence] of [['claude', '\x1bv'], ['codex', '\x16']]) {
  test(`${client} receives a native image shortcut, never a path or bracketed paste`, async () => {
    const f = fixture(async terminal => {
      assert.equal(terminal, f.vscode.window.activeTerminal);
      return { kind: 'image', client };
    });
    await f.paste();
    assert.deepEqual(f.sent, []);
    assert.deepEqual(f.commands, [['workbench.action.terminal.sendSequence', { text: sequence }]]);
  });
}

test('clipboard changed during capture cancels paste', async () => {
  const f = fixture(async () => ({ kind: 'changed' }));
  await f.paste();
  assert.deepEqual(f.sent, []);
  assert.deepEqual(f.commands, []);
});

for (const target of ['terminal', 'editor', 'window']) {
  test(`moving focus to ${target} cancels delayed paste`, async () => {
    const f = fixture(async () => {
      f.listeners[target]({ focused: false });
      return { kind: 'image', path: 'C:\\image.png' };
    });
    await f.paste();
    assert.deepEqual(f.sent, []);
  });
}

test('capture errors surface and later pastes can recover', async () => {
  let calls = 0;
  const f = fixture(async () => {
    if (!calls++) throw new Error('Clipboard is busy');
    return { kind: 'image', path: 'C:\\image.png' };
  });
  await f.paste();
  assert.equal(f.errors.length, 1);
  await f.paste();
  assert.equal(f.sent.length, 1);
});

test('keybindings only apply to Windows terminal focus', () => {
  const manifest = require('../vscode-extension/package.json');
  for (const binding of manifest.contributes.keybindings) {
    assert.equal(binding.when, 'terminalFocus && isWindows');
  }
});
