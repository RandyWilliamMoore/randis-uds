# Notices

Randis UDS. Copyright (C) 2026 Randy Moore.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 3. It comes with no warranty; see `LICENSE`.

## Additional terms: attribution

These are additional terms under sections 7(b) and 7(c) of the GPL. They apply to every copy, clone or derivative of this program, and to anything built from it.

1. It must attribute Randis UDS at the very beginning of the work, blatantly and conspicuously. The attribution must:
   - say it came from Randis UDS by Randy Moore,
   - say whether it is a copy, clone or derivative,
   - direct people to the original repository: https://github.com/RandyWilliamMoore/randis-uds, and
   - link to the author's support page: https://ko-fi.com/moorescombinatoricsmatrix
2. Where that goes:
   - its interface: at the top, in plain view, every time it runs;
   - its README and other documentation: at the very top;
   - its source files: a notice at the top of each file, as this program's files have.
3. Anyone who discusses it in published content, such as a video, article, post or talk, must openly attribute it the same way, directing people to the original repository and to the support page. This goes at the beginning of the content wherever the content is about the work.
4. A changed version must be marked as changed, and must not claim to be the original.

## Hidden credit mark

Files that Randis UDS makes, and the items in Randis Shop, carry a small credit mark that is not shown on screen. It is declared here so nobody is surprised by it.

- **What it says, and nothing else:** `Made with Randis UDS by Randy Moore - https://github.com/RandyWilliamMoore/randis-uds - https://ko-fi.com/moorescombinatoricsmatrix`
- **What it does not hold:** nothing about you, your machine or your work. No names, IDs, addresses or usage data. It never sends anything anywhere and it locks nothing.
- **Where it sits:** a comment in HTML, SVG, JavaScript, CSS and Python files; a text field (`RandisUDS`) in PNG images; a comment segment in JPEG images; a `RandisUDS` tag in MP3 files.
- **Which files get it:** files a built tab saves out through the app (pictures, songs, pages, code), and a built tab's page, logo or song when it is shipped or published to a shop. Never what you type yourself, and never Notepad, Code editor or PDF saves (`credmark.py`).
- **Why:** it records where the work came from, the same credit the attribution terms above already require.

## Name and logos

The name "Randis UDS™" and the logos in `ui/logo` are not licensed under the GPL. All rights to them are reserved. Under section 7(e) of the GPL, no trademark rights are granted. A changed version must use its own name and logo, and uses the name "Randis UDS" only to say where it came from, as required above.

## Parts by others

These keep their own licenses, which sit next to them in the folder.

| Part | Where | License |
|---|---|---|
| CodeMirror | `ui/vendor/codemirror` | MIT |
| pdf-lib | `ui/vendor/pdf-lib` | MIT |
| EmulatorJS 4.2.3 and its system cores (RetroArch cores: FCEUmm, Snes9x, Gambatte, mGBA, Genesis Plus GX, Mupen64Plus-Next, melonDS, PCSX ReARMed, Mednafen PCE, Stella 2014, ProSystem, Handy, MAME 2003-Plus) | `ui/vendor/emulatorjs` (not in this repo or the installer: fetched once from cdn.emulatorjs.org the first time you play, by `emuserve.py`) | GPL 3.0 (`LICENSE` there); each core keeps its own license, some of them for non-commercial use only, listed at https://github.com/EmulatorJS/EmulatorJS and in the cores' own projects |
| PDF.js and the parts it bundles | `ui/vendor/pdfjs` | Apache 2.0, with BSD, MIT, SIL OFL and CC0 parts; see each `LICENSE*` file there |
| pywebview | installed by setup | BSD 3-Clause |
| bottle, proxy_tools, pythonnet, clr_loader | installed by setup | MIT |
| cffi | installed by setup | MIT-0 |
| pycparser | installed by setup | BSD 3-Clause |
| typing_extensions | installed by setup | PSF License |
| Python | installed by setup | PSF License |
