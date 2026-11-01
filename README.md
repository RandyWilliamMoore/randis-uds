# Randis UDS™

**Randis UDS™ by Randy Moore. This is the original.** Repository: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix

Copies, clones and derivatives must say so at the very top of their work and link back to the original repository: see `NOTICE.md`.

**Randis UDS™ is a universal software with no fixed purpose. Describe what you need, and the LLM inside it builds that into the app while you're using it. If you can dream it you can build it.**

Link a local model or an online account to start. With no LLM linked, it works as a notepad and text editor.

Status: pre-release. Windows only for now.

Like it? Support the author: https://ko-fi.com/moorescombinatoricsmatrix

Find real in-game items here: https://www.etsy.com/shop/UberRandis

Join the Discord: https://discord.gg/83RmuHcQTR

YouTube: https://www.youtube.com/@Randis9000 and https://www.youtube.com/@MooresCombinatoricsMatrix

## What it does

- Browser-style tabs, including dragging a tab into its own window
- Chat with a linked LLM: a local model, LM Studio, your own Anthropic API key, or Claude Code on this computer
- Build tabs by chat, keep their versions, and save any of them as a template
- An IDE tab, a notepad, and a rubber duck you can restyle, pop out or talk a problem through with
- A PDF tab: read, make from text or pictures, merge, rotate, reorder, and add a drawn or typed signature (a picture on the page, not a certificate signature)
- A snapshot before every Claude Code turn, so each turn can be undone
- Projects: separate copies of the app for separate work, with changes from Base pushed into them

## Install

Run `RandisUDS-Setup-<version>.exe`. It installs for your user only, with no admin rights, brings its own Python, and adds a desktop icon. The first time you open it, a window shows you how to pin it to your taskbar and connect Claude Code. Windows may warn about an unknown publisher because the installer isn't signed yet.

Running a newer setup over an install updates it. Your data stays, and any app code you or your Claude changed is saved to `data\edited_before_update` before the new code goes in.

The local GGUF link also needs `llama-cpp-python`, which isn't bundled. LM Studio, an Anthropic API key and Claude Code links don't.

## Edit it with Claude Code

Claude Code can change Randis UDS from outside the app, and fix it if it ever won't start. `CLAUDE_CODE_SETUP.md` takes you from Claude in your browser to Claude Code in PowerShell, including your account and permissions. Claude then starts from `CLAUDE.md`, which walks it through the rest. A snapshot is saved before each message, so each turn can be undone.

## Run from source

Needs Python 3.14 and the Microsoft Edge WebView2 runtime (already on most Windows 10 and 11 PCs).

```powershell
pip install -r requirements.txt
python launch.py
```

Optional: Git for Projects, and Claude Code for the Claude Code link.

API keys are stored in `%APPDATA%\RandisUDS`, encrypted with Windows' per-user encryption. They are not stored in this folder.

## Tests

```powershell
pip install pillow
python tests/tabs_test.py --no-real
python tests/restore_test.py
python tests/projects_test.py
python tests/tabbar_test.py
python tests/tab_icons_test.py
python tests/load_retry_test.py
python tests/launch_test.py
python tests/origin_test.py
python tests/first_run_test.py
python tests/pdf_test.py
python tests/ui_test.py --no-real
```

## Known issues

- Sometimes a page reload doesn't finish loading, and your open tabs don't come back. Automated tests show this now and then on a new install. The cause isn't known yet.
- Undoing a Claude Code turn puts the whole folder back to how it was before that turn, including any other changes made since then.

## License

GNU General Public License, version 3: see `LICENSE`. Copyright (C) 2026 Randy Moore.

Every copy, clone or derivative must show that it came from Randis UDS and link back to the original repository and to the author's support page, every time it runs: see the additional terms in `NOTICE.md`. The name Randis UDS™ and the logos aren't covered by the GPL, and parts by others keep their own licenses: see `NOTICE.md`.
