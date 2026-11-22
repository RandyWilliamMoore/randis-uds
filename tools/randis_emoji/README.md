<!-- Randis UDS™ by Randy Moore. Original: https://github.com/RandyWilliamMoore/randis-uds · Support: https://ko-fi.com/moorescombinatoricsmatrix -->
# Randis Emoji

A custom emoji set drawn in code: 75 SVG icons covering mind, senses, science, team and command (Commander Randis, ranks, credits, comms, missions, bounties, legacy), each with a `:shortcode:`. It's one JavaScript file with no other files and no network.

**This file is the original.** `data/_academy_build/build.py` copies it to `ui/randis_emoji.js` (the main app page) and builds it into Intelligence Hijacking, the Randis Toolkit and Randis Academy. Edit it here, then run `python build.py` in `data/_academy_build`.

## Use it on a page

```html
<script src="randis_emoji.js"></script>
<script>RandisEmoji.observe(document.body);</script>
```

After that, any `:brain-bolt:`, `:neuron:` or other shortcode in the page's text shows as the picture, including text added later. It skips inputs, textareas, `code` and `pre`, and anything marked `data-no-emoji`.

## API

| Call | Gives |
|---|---|
| `RandisEmoji.list` | `[{name, tags, group}]` |
| `RandisEmoji.svg(name)` | SVG markup |
| `RandisEmoji.url(name)` | `data:` URL for an `<img>` |
| `RandisEmoji.html(name, px)` | an `<img>` tag |
| `RandisEmoji.render(html)` | the HTML string with shortcodes swapped |
| `RandisEmoji.observe(root)` | keeps swapping shortcodes under `root` |
| `RandisEmoji.png(name, px)` | Promise of a PNG data URL |
| `RandisEmoji.add(name, tags, inner, group)` | adds your own (`inner` = SVG elements on a 64×64 grid) |

## For other Claude Code chats and UDS layers

- To add an emoji, append an `add("name", "group", "search words", '<svg elements>')` line in the file. Draw on a 64×64 grid, use the palette constants at the top (C, V, G, Y, P, O, W, B, R), and stroke with `s(colour, width)`.
- Keep names lowercase with dashes.
- A built tab can't load files from this folder, because tabs are sandboxed. To use the set there, paste the file's contents into the tab's `<script>`.

## Shared with the whole app (v1.1)

Since v1.1 the main app (`ui/app.js`) adds this file and the shared custom emojis (`data/emoji/mine.json`) to every built tab and the duck as they load, so `:shortcodes:` show as pictures on every page of this Randis UDS. Emoji Forge's "Share my emojis with the whole app" button writes `mine.json`. Shared SVGs are checked first: no scripts, links, event handlers or outside references.

## Where they don't show

Phones, other apps and websites only draw the emoji in the official Unicode list. Custom emoji can't be made to appear everywhere for everyone. To use these in Discord, Slack or Teams, download the PNGs from Emoji Forge and upload them as custom emoji in that app.
