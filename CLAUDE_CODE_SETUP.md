# Connect Claude Code to Randis UDS

**Randis UDS™ by Randy Moore.** Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix

Randis UDS can change its own code. To do that from outside the app, or to fix it when it won't start, you need Claude Code: Claude in a terminal window, working on the files on your computer. Claude in your browser can't reach those files.

This guide takes about ten minutes and doesn't need admin rights. If you get stuck, paste this guide and the error into Claude in your browser and ask what to do next.

## 1. Check your Claude account

Claude Code uses a Claude account, and you sign in with the same one you use in your browser.

- **A Pro, Max, Ultra, Team or Enterprise plan** includes it.
- **The free plan doesn't.** To upgrade, see https://claude.com/pricing.
- **An Anthropic Console account** also works and bills per use: https://console.anthropic.com.

No account yet? Make one at https://claude.ai.

## 2. Open PowerShell

Press the Windows key, type `PowerShell`, and press Enter. Don't choose "Run as administrator". It isn't needed.

If you see `irm is not recognized` in the next step, you're in Command Prompt instead. Open PowerShell as described here.

## 3. Install Claude Code

Copy this line, paste it into PowerShell, and press Enter:

```powershell
irm https://claude.ai/install.ps1 | iex
```

It shows no progress while it downloads, so give it a few minutes. When it finishes, **close PowerShell and open a new window**, then check it:

```powershell
claude --version
```

You should see a version number.

**If `claude` isn't recognized,** run these two lines, then open a new PowerShell window and try again:

```powershell
$currentPath = [Environment]::GetEnvironmentVariable('PATH', 'User')
[Environment]::SetEnvironmentVariable('PATH', "$currentPath;$env:USERPROFILE\.local\bin", 'User')
```

Still stuck? `claude doctor` lists what's wrong.

## 4. Go to your Randis UDS folder

Open Randis UDS once and close it. That connects its history to Claude Code.

If you used the installer, run this line. If you run Randis UDS from source, use the folder you put it in:

```powershell
cd "$env:LOCALAPPDATA\Programs\RandisUDS\app"
```

The app's own setup window has an **Open Claude Code here** button that does this and step 5 for you.

## 5. Start Claude Code and sign in

```powershell
claude
```

- **Signing in:** the first time, your browser opens. Sign in, approve, and go back to PowerShell. You only do this once. To switch accounts later, type `/login`.
- **Trusting the folder:** it asks whether you trust this folder. Say yes. This folder's settings only apply once you do.

## 6. Let Claude finish the setup

Type this and press Enter:

```text
Please set up Randis UDS.
```

Claude reads the guide in this folder (`CLAUDE.md`), checks everything, and shows you how to undo its changes.

## What Claude is allowed to do

Randis UDS starts Claude Code in **accept edits** mode, set in `.claude/settings.json`:

| What | Does it ask you first? |
|---|---|
| Read files | No |
| Edit files in this folder | No |
| Run other commands | Yes |

When it asks, read what it wants to do. You can say no. This is all you need to edit Randis UDS, and you don't need to change anything else.

You can press **Shift+Tab** to switch modes during a session. Avoid running Claude Code with full access, or with the `--dangerously-skip-permissions` option. It would then act on your whole computer without asking, and a file or web page it reads could trick it.

## Undoing a change

A snapshot of the folder is saved before each message you send. To undo, run these in PowerShell from your Randis UDS folder. If you run from source, use `python` in place of `..\python\python.exe`.

```powershell
..\python\python.exe restore.py              # list recent turns
..\python\python.exe restore.py --undo-last  # put the folder back to before the last one
```

Undo puts back the whole folder, including anything else changed since that turn. Anything Claude changes outside this folder isn't covered.

## Optional extras

- **Git for Windows** (https://git-scm.com): free. Randis UDS's Projects feature needs it. Claude Code works without it, using PowerShell for commands.

## Next time

Open PowerShell, go to your folder as in step 4, and run `claude`. There's nothing else to set up.
