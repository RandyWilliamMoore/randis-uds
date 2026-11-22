**Made with the Shop Studio in [Randis UDS](https://github.com/RandyWilliamMoore/randis-uds) by Randy Moore. This shop is a derivative of its Shop Kit. Support Randis UDS: https://ko-fi.com/moorescombinatoricsmatrix**

# {{name}}

{{tagline}}

**[Open the shop]({{page}})**

Games, apps and music made with Randis UDS, playable right on the page. Every game and app runs walled off from the visitor's computer.

## How it's laid out

| What | Where |
|---|---|
| The shop's name, owner, links and look | `shop.json` |
| A game or an app | `games/<name>/` or `apps/<name>/`: `item.html`, `logo.svg` (or `.png`), `info.json` |
| A song in the Jukebox | `music/<name>/`: `song.mp3`, `cover.jpg`, `info.json` (add one with `tools/add_music.py`) |
| A program to download (like the Windows and Linux versions of a game) | `software/<name>/info.json`, its logo in `site/logos/` |
| The lists the page reads | `config.js`, `items.js`, `software.js`, `music.js`, written by `python tools/build_index.py` |

The Shop Studio tab in Randis UDS does all of this for you: it puts tabs on the shelves, publishes, and shows the checks.

## Checks and desktop versions

GitHub's machines check the shop on every push (`.github/workflows/check.yml`): every shelf is in order, and every page opens and runs in a real browser on Linux and Windows.

Pushing a tag like `my-game-v1.0.0` builds that game into a Windows program and a Linux program and puts them on a release page (`.github/workflows/desktop.yml`).

## Licence

The shop's own code (the Shop Kit) comes from Randis UDS, GPLv3 with additional attribution terms: keep the credit line at the top of the page and of this README. The games, apps and songs belong to whoever made them.
