'use strict';
const vscode = require('vscode');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { createPasteHandler } = require('./paste');
const execute = promisify(execFile);

async function activate(context) {
  const output = vscode.window.createOutputChannel('Paste Claude');
  const powershell = path.join(process.env.SystemRoot || 'C:\\Windows',
    'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
  const capture = async terminal => {
    const terminalProcessId = await terminal.processId;
    const { stdout } = await execute(powershell, [
      '-NoLogo', '-NoProfile', '-NonInteractive', '-STA', '-ExecutionPolicy', 'Bypass',
      '-File', path.join(context.extensionPath, 'capture.ps1'),
      '-TerminalProcessId', String(terminalProcessId || 0)
    ], { windowsHide: true, timeout: 10000, encoding: 'utf8' });
    return JSON.parse(stdout.replace(/^\uFEFF/, '').trim());
  };
  context.subscriptions.push(output, vscode.commands.registerCommand(
    'pasteClaude.attachScreenshot', createPasteHandler(vscode, capture, output)));
  // Custom terminal commands must be handled by the IDE instead of the shell.
  const config = vscode.workspace.getConfiguration('terminal.integrated');
  const skip = config.get('commandsToSkipShell', []);
  if (!skip.includes('pasteClaude.attachScreenshot')) {
    const custom = config.inspect('commandsToSkipShell').globalValue || [];
    await config.update('commandsToSkipShell', [...custom.filter(name => name !== 'pasteClaude.paste'), 'pasteClaude.attachScreenshot'],
      vscode.ConfigurationTarget.Global);
  }
  output.appendLine('Ready: Ctrl+V, Ctrl+Shift+V, and Shift+Insert in Windows terminals.');
}

module.exports = { activate };
