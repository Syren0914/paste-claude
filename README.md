# paste-claude

Windows screenshot pasting for Claude Code and Codex in Antigravity IDE, VS Code, Command Prompt, or Windows Terminal.

## Antigravity IDE / VS Code integrated terminals

The integrated-terminal extension handles **Ctrl+V**, **Ctrl+Shift+V**, and **Shift+Insert** only when a terminal has focus. It detects the CLI running below the terminal shell and sends its native image-paste shortcut: Alt+V for Claude, Ctrl+V for Codex. Claude shows an [Image #N] attachment. Other shells receive a saved PNG path as a fallback. The shortcut is sent as raw input, not bracketed paste, and never submits the prompt. It runs automatically inside the IDE and requires no Python worker. Normal text uses the IDE's regular paste command; browser and editor pastes are unaffected.

Build and install the local extension:

```powershell
.\.venv\Scripts\python.exe scripts/package_extension.py
& "$env:LOCALAPPDATA\Programs\Antigravity IDE\bin\antigravity-ide.cmd" --install-extension "$PWD\dist\paste-claude-native-images-0.3.0.vsix" --force
# For VS Code instead: code --install-extension .\dist\paste-claude-native-images-0.3.0.vsix --force
```

The extension activates automatically after installation. See the **Paste Claude** output channel for diagnostics. It adds its command to `terminal.integrated.commandsToSkipShell` so the IDE handles the shortcut. If a custom user keybinding overrides Ctrl+V, bind `pasteClaude.attachScreenshot` with `terminalFocus && isWindows`. This targets local Windows terminals; remote/WSL image paths are not translated. Right-click paste still uses the IDE's native behavior.

## Standalone Command Prompt / Windows Terminal

Copy a screenshot, focus your CLI prompt, and press **Ctrl+V**, **Ctrl+Shift+V**, or **Shift+Insert**. The helper saves a PNG and types its quoted file path into the prompt. It never presses Enter. Ask the CLI to inspect that image as part of your message.

The clipboard is never rewritten, so pasting the same screenshot into a browser still pastes the image. Ordinary text and copied files pass through normally. Right-click paste is not intercepted. Integrated terminals use the extension above. Run the helper at the same privilege level as the terminal; Windows blocks input from a normal helper into an elevated terminal.

## Install and start

```powershell
.\.venv\Scripts\python.exe -m paste_claude --install
```

This starts a hidden worker immediately and registers it under the current user's Windows Run key for future sign-ins. No console window stays open. Launching it again does not create another active worker. Keep this checkout and its virtual environment in place.

Without `--install`, `python -m paste_claude` starts the hidden worker for this session only. Use `--foreground` to run in your current console. The old `--copy-path` option is accepted for compatibility and uses the same clipboard-preserving behavior.

Remove automatic startup with `python -m paste_claude --uninstall`. To stop an already running worker, end the Python process whose command line points to this project's `__main__.py --worker` in Task Manager.

Logs: `%LOCALAPPDATA%\paste-claude\paste-claude.log` (rotated). Screenshots: `%TEMP%\paste-claude`. Saved images remain available for the CLI and can be deleted when no longer needed.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_extension.cjs
```
