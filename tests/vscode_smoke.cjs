// Run by the installed IDE's extension test host, using the current clipboard image.
const vscode = require('vscode');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

exports.run = async function () {
  const resultPath = path.join(__dirname, '..', 'dist', 'ide-smoke-result.json');
  let terminal;
  try {
    const extension = vscode.extensions.getExtension('paste-claude-local.paste-claude-native-images');
    assert.ok(extension, 'extension loaded');
    await extension.activate();
    const write = new vscode.EventEmitter();
    let receive;
    const input = new Promise(resolve => { receive = resolve; });
    terminal = vscode.window.createTerminal({ name: 'Paste screenshot verification', pty: {
      onDidWrite: write.event,
      open() { write.fire('Screenshot input verification (no shell)\r\n'); },
      close() {},
      handleInput(data) { receive(data); }
    } });
    terminal.show(true);
    const deadline = Date.now() + 10000;
    while (vscode.window.activeTerminal !== terminal) {
      if (Date.now() > deadline) throw new Error('Test terminal did not become active');
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    await vscode.commands.executeCommand('pasteClaude.attachScreenshot');
    let timer;
    const data = await Promise.race([input, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('No screenshot path received')), 15000);
    })]);
    clearTimeout(timer);
    assert.ok(!/[\r\n]/.test(data), 'must not submit the prompt');
    const imagePath = JSON.parse(data.trim());
    assert.ok(fs.existsSync(imagePath), 'PNG path exists');
    assert.equal(fs.readFileSync(imagePath).subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
    fs.writeFileSync(resultPath, JSON.stringify({ passed: true, imagePath, received: data }));
  } catch (error) {
    fs.writeFileSync(resultPath, JSON.stringify({ passed: false, error: error.stack }));
    throw error;
  } finally {
    if (terminal) terminal.dispose();
  }
};
