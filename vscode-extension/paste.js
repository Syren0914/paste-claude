'use strict';

function createPasteHandler(vscode, capture, output) {
  let busy = false;
  return async function paste() {
    const terminal = vscode.window.activeTerminal;
    if (!terminal || busy) return;
    busy = true;
    let moved = false;
    const listeners = [
      vscode.window.onDidChangeActiveTerminal(() => { moved = true; }),
      vscode.window.onDidChangeActiveTextEditor(() => { moved = true; }),
      vscode.window.onDidChangeWindowState(state => { if (!state.focused) moved = true; })
    ];
    try {
      const result = await capture(terminal);
      if (moved || vscode.window.activeTerminal !== terminal) return;
      if (result.kind === 'image') {
        if (result.client === 'claude' || result.client === 'codex') {
          // sendText brackets pasted text, which prevents CLI shortcut handling.
          // Send the raw key sequence so the CLI reads the original clipboard image.
          await vscode.commands.executeCommand('workbench.action.terminal.sendSequence', {
            text: result.client === 'claude' ? '\x1bv' : '\x16'
          });
          output.appendLine('Native image attachment requested for ' + result.client);
          return;
        }
        // Forward slashes also work in Windows CLIs; no backslash escape ambiguity.
        const path = result.path.replace(/\\/g, '/');
        terminal.sendText(JSON.stringify(path) + ' ', false);
        output.appendLine('Screenshot inserted into integrated terminal: ' + result.path);
      } else if (result.kind === 'other') {
        await vscode.commands.executeCommand('workbench.action.terminal.paste');
      }
    } catch (error) {
      output.appendLine('Screenshot paste failed: ' + error.message);
      vscode.window.showErrorMessage('Screenshot paste failed: ' + error.message);
    } finally {
      listeners.forEach(listener => listener.dispose());
      busy = false;
    }
  };
}

module.exports = { createPasteHandler };
