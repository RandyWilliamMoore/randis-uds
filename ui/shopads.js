// Randis UDS. Copyright (C) 2026 Randy Moore. GPLv3 with additional terms: every copy, clone or derivative must attribute this work first and conspicuously. See LICENSE and NOTICE.md. Original: https://github.com/RandyWilliamMoore/randis-uds
"use strict";

const SHOP_AD_COPY = {
  "atelier-fashion-suite": ["Sew what? Sew THIS.", "Atelier takes a garment from napkin doodle to shop shelf. Pattern-making not included in your personality, but it is in the app.", "Get stitched up"],
  "aura-assistant": ["Your desktop called. It's lonely.", "Aura gives it a living, animated assistant with feelings*. *Simulated. Probably.", "Meet Aura"],
  "club-wiki": ["Your club has lore. Write it down before Dave forgets it.", "Club Wiki: a ready-made wiki for clubs, teams and makerspaces.", "Start the lore"],
  "code-editor": ["Ctrl+S your way to greatness.", "Code Editor: HTML, CSS and JS in one small, fast tab. Semicolons sold separately.", "Write some code"],
  "codex-academy": ["Learn to code before the robots learn to you.", "Codex Academy takes you from 'what's a variable' to 'why is prod down'.", "Enroll for $0"],
  "discord-bot-design-suite": ["Build a bot that says 'pong' when you say 'ping'. And more.", "Discord Bot Design Suite: no PhD in YAML required.", "Beep boop"],
  "forge-rd-suite": ["Got an idea in the shower? Bring it to the Forge.", "R&D from wild idea to real product. Towel not included.", "Forge ahead"],
  "free-money-finder": ["FREE MONEY. No, really. This is not that kind of ad.", "Free Money Finder looks for money you might actually be owed. We know. We were suspicious too.", "Find my money"],
  "game-emulator-suite": ["Blow on the cartridge. Emotionally.", "Game Emulator Suite plays the retro games you already own. 13 systems. Zero dust.", "Press Start"],
  "heirloom-boxes": ["Build a box your great-grandkids will fight over.", "Heirloom Boxes: curio boxes and toy chests meant to outlive the Wi-Fi.", "Box it up"],
  "heirloom-design-lab": ["Things they don't make anymore? Make them anymore.", "Heirloom Design Lab: design stuff that lasts longer than your phone contract.", "Design forever"],
  "heritage": ["Find out if you're secretly royalty. (You're not. But still.)", "Heritage: your family tree, with sources, stories and the uncle nobody talks about.", "Climb the tree"],
  "intelligence-hijacking": ["Commander Randis wants YOU... to do your brain push-ups.", "Intelligence Hijacking: brain training led by a hologram who believes in you more than your gym teacher did.", "Report for duty"],
  "life-tree": ["Your to-do list has a to-do list now.", "Life Tree: one giant tree for planning your whole life. Branches go all the way down.", "Get organized-ish"],
  "media-network": ["Run a news network from your bedroom. Pants optional.", "Randis Media Network: your own AI-powered media control room.", "Go on air"],
  "mintworks-exchange": ["To the moon! (Play money. The moon is also fake.)", "Mintworks Exchange: trade crypto and collectibles with zero real dollars lost.", "Lose fake money"],
  "money-lab": ["Make terrible stock picks with ZERO consequences!", "Money Lab: 170 simulated markets and a money school. Your real wallet stays safe.", "Paper trade now"],
  "music-studio": ["Your shower concerts deserve a studio.", "Music Studio: tracks, synths, drums and a piano teacher who never sighs at you.", "Lay down a track"],
  "notepad": ["Introducing: Notepad. It's a notepad.", "No AI. No cloud. No 'smart' anything. Just you and your thoughts. Terrifying.", "Write stuff"],
  "omnisight-xint-suite": ["Open-source intelligence. Closed-source snacks.", "Omnisight xINT Suite: a lawful OSINT workbench for cases, leads and timelines. Trench coat optional.", "Investigate"],
  "pdf-maker": ["Make a PDF. Feel like an accountant. Live the dream.", "PDF Maker turns your words and pictures into a clean PDF in seconds.", "Make it official"],
  "publishing-suite": ["Write one book. Or 4,000. We don't judge.", "Publishing Suite: the whole book factory, from template to series.", "Be an author"],
  "quak-quak": ["Talk to the duck. The duck knows.", "Quak Quak: a rubber duck for debugging out loud. It has never once interrupted anybody.", "Quak"],
  "randis-antivirus": ["Viruses hate this one weird app!", "Randis Antivirus tells you in normal words what it found. No scary pop-ups selling you more antivirus.", "Scan me"],
  "randis-bench-lab": ["Is your AI smart? Let's find out. Gently.", "Randis Bench Lab: design and run benchmarks without crying into a spreadsheet.", "Run the test"],
  "randis-office": ["A whole office. No coworker microwaving fish.", "Randis Office: documents, spreadsheets, slides and more, all in one page.", "Clock in"],
  "randis-paint": ["Bob Ross energy, now on your desktop.", "Randis Paint: happy little pixels. Made entirely by chatting with Randis UDS.", "Paint something"],
  "randis-sound-forge": ["Elevator music? We've got elevator music.", "Randis Sound Forge: royalty-free songs in any genre. Even the genre you just made up.", "Press Make"],
  "repo-scout": ["Someone already built it. Repo Scout knows where.", "It searches GitHub, GitLab, Codeberg and more so you don't have to open 47 tabs.", "Go scouting"],
  "service-member-helper": ["Paperwork, but at ease.", "Service Member Helper: a plain-language toolkit for service members, veterans and families.", "Fall in"],
  "shop-studio": ["Like this shop? Make your own. We won't be jealous. Much.", "Shop Studio: build and run your own online shop, just like this one.", "Open a shop"],
  "sing-in-my-voice": ["Finally, a singer who sounds exactly like you.", "Sing in My Voice: Sound Forge songs sung in your own voice. Your mom will cry. Good tears, probably.", "Start singing"],
  "templeos": ["Experience a legend. 640x480. 16 colors. Zero compromises.", "Run the real TempleOS 5.03 in a safe sandbox. Hymns included.", "Boot it"],
  "the-dispatch": ["Extra! Extra! Your club made the news!", "The Dispatch: a modern newsletter page. Paperboy sold separately.", "Read all about it"],
  "vm-suite": ["Computers inside your computer. Computer-ception.", "VM Suite runs real operating systems inside a tab. Yo dawg.", "Go deeper"],
  "voice-forge": ["Sound like a wizard. Or a giant. Or a toaster.", "Voice Forge: a voice studio where every voice is built from numbers.", "Find your voice"],
  "vr-avatar-designer": ["Be taller in VR. We won't tell.", "VR Avatar Designer: a fully rigged 3D you, with better hair.", "Build my avatar"],
  "vtuber-studio": ["Become an anime. Legally.", "VTuber Studio: design, rig and stream your own original VTuber.", "Go live"],
  "weather": ["It's going to be weather today.", "Weather: the forecast, minus the dramatic music.", "Look outside"],
  "wiki-suite": ["Your own Wikipedia. Citation needed? Never again.", "Wiki Suite: linked pages, templates and categories, all yours.", "Start editing"],
  "battle-tanks-royale": ["Honk honk. That's tank for 'move'.", "Battle Tanks Royale: defend your base from waves of tanks. Parking is still a nightmare.", "Roll out"],
  "bindy-and-louis": ["A binder clip that fixes things. And an arcade game. Yes, both.", "Bindy & Louis: the repair helper you didn't know you needed.", "Clip in"],
  "blockwild": ["Punch trees. Build castles. Repeat until sunrise.", "Blockwild: an endless voxel world, and none of it needs mowing.", "Start digging"],
  "card-master": ["57 card games and none of them is Go Fish. Wait, it is.", "Card Master: 57 classics with rules, 27 you can play right now.", "Deal me in"],
  "castle-mnemosyne": ["Remember everything. In a castle. Like a wizard.", "Castle Mnemosyne: a pixel-art memory palace. Your grocery list has never been so majestic.", "Enter the castle"],
  "coin-flipper": ["Can't decide? Let physics decide.", "Coin Flipper: six ways to flip, with stats for every flip. Heads, you play. Tails, you also play.", "Flip it"],
  "dice-master": ["Roll a d100 for no reason. Feel powerful.", "Dice Master: every die from d4 to d100, plus classic dice games against the computer.", "Roll 'em"],
  "diesel-gen-mechanic-simulator": ["Grease monkey wanted. Must love noise.", "Diesel Gen Mechanic Simulator: fix generators under a scruffy old boss. Smell not simulated.", "Grab a wrench"],
  "fossil-collector": ["Dig up a T. rex. Name it Kevin.", "Fossil Collector: a whole paleontology career. Bones not included. Wait, they are.", "Start digging"],
  "gem-collector": ["Shine bright like a gem you cut yourself.", "Gem Collector: mine rough stones and cut them on a virtual lapping machine.", "Get sparkly"],
  "gilded-hands": ["Chips times Mult equals JOY.", "Gilded Hands: an original poker-hand roguelike. Your poker face is optional.", "Shuffle up"],
  "hotdog-tycoon": ["Hot dogs in YOUR area want to meet you!", "Hotdog Tycoon: start with one stand for Big Sal, end up a wiener empire.", "Relish it"],
  "lanternfall": ["Build a deck. Light the dark. Lose sleep.", "Lanternfall: an original deck-building roguelike. 'One more run' guaranteed.", "Light it up"],
  "lhc-simulator": ["Smash particles. Don't make a black hole. (Probably fine.)", "LHC Simulator: run the Large Hadron Collider from 2012 to High-Luminosity.", "Collide"],
  "mail-sorter": ["You've got mail. SO MUCH mail.", "Mail Sorter: sort it before the pile buries you. Then sort it again.", "Sort it out"],
  "marble-collector": ["You haven't lost your marbles. They're right here.", "Marble Collector: Ringer, Battle, Bullseye and a collection to brag about.", "Knuckle down"],
  "matching-master": ["Your memory called. It forgot why.", "Matching Master: flip cards and match pairs. It keeps getting bigger. Like your brain.", "Flip a pair"],
  "milk-cap-champ": ["POGS ARE BACK. Your 1995 self is screaming.", "Milk Cap Champ: stack 'em, slam 'em, flip 'em.", "SLAM!"],
  "pachinko-player": ["Tokyo pachinko parlor. No smoke. No commute.", "Pachinko Player: rent balls, shoot them in and hit START. Lights included. LOTS of lights.", "Pachinko!"],
  "pong": ["It's Pong. You know what to do.", "Classic Pong, clean and simple. Bloop. Bloop. Bloop.", "Bloop"],
  "rev-the-frog": ["A frog. Rocket boots. The fate of the world.", "REV! The Frog Who Saved the World: an original 3D platformer. Ribbit responsibly.", "Hop to it"],
  "sandwich-master": ["Bread. Stuff. Bread. You're a genius.", "Sandwich Master: build every order bread first. No soggy bottoms.", "Make a sammich"],
  "skateboard-collector": ["Kickflip into your collecting era.", "Skateboard Collector: 60-second sessions, tricks and decks to collect. Zero scraped knees.", "Drop in"],
  "slot-player": ["Win big! (Nothing. You win nothing. It's free.)", "Slot Player: four machines of ding-ding-ding with none of the real-money regret.", "Pull the lever"],
  "topiary-master": ["Shape a hedge like a dolphin. Live your truth.", "Topiary Master: get hired to trim hedges into whatever the client dreams up.", "Get snippy"],
  "randis-uds": ["The app that made every app in this shop. It's apps all the way down.", "Randis UDS: a blank desktop app you change just by asking.", "Learn more"],
};
const SHOP_AD_ANY = [
  ["Doctors HATE this one weird {kind}!", "{name}: {blurb}", "Find out why"],
  ["You won't BELIEVE what {name} does next.", "Number 7 will shock you. There is no number 7.", "See for yourself"],
  ["Congratulations! You're the 1,000,000th visitor!", "Your prize: {name}. It was free anyway.", "Claim my prize"],
  ["Hot new {kind} in your area!", "{name} is just one click away. And it's single.", "Say hi"],
];
const SHOP_AD_QUOTES = [
  "I opened {name} and my houseplants started respecting me.",
  "{name} changed my life. Mostly my Tuesday afternoons.",
  "Five stars. Would click again.",
  "I told my therapist about {name}. Now she uses it too.",
  "My cat walked across the keyboard and opened {name}. Smart cat.",
  "I was skeptical. Then I wasn't. Then I had a snack.",
];
const SHOP_AD_FEET = ["*Free. It's always free. We just like asterisks.", "*Results may vary. Results may also be awesome.", "*No pop-ups were harmed in the making of this ad.",
  "*Ad paid for with exposure.", "*This ad is fake. The item is real. Life is strange.", "*Side effects may include fun."];
const SHOP_AD_PEOPLE = ["Gary, probably real", "Linda, verified human", "A guy named Steve", "Your neighbor (allegedly)", "Dr. Pixel, not a doctor", "Commander Randis, hologram"];

function shopAdsOn() { return localStorage.getItem("udsShopAds") !== "off"; }

function shopAddAds(list, items, onPick) {
  if (!shopAdsOn() || !items.length) return;
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const fill = (s, it) => s.replace(/\{name\}/g, it.name).replace(/\{kind\}/g, it.kind === "games" ? "game" : "app").replace(/\{blurb\}/g, (it.blurb || "").split(/(?<=[.!?])\s/)[0]);
  const ads = items.map(it => {
    const slug = it.item.split("/").pop(), c = SHOP_AD_COPY[slug] || pick(SHOP_AD_ANY);
    return { it, head: fill(c[0], it), sub: fill(c[1], it), cta: fill(c[2], it), quote: fill(pick(SHOP_AD_QUOTES), it), who: pick(SHOP_AD_PEOPLE), foot: pick(SHOP_AD_FEET) };
  }).sort(() => Math.random() - .5);
  let n = 0;
  const slot = () => {
    const box = el("div", { className: "shop-ad-slot" });
    let ad = null, timer = 0, i = n++ % ads.length, hold = false;
    const show = () => {
      const a = ads[i % ads.length]; i += 3;
      const next = shopAdBanner(a, onPick, () => { clearInterval(timer); box.remove(); });
      if (ad) ad.replaceWith(next); else box.appendChild(next);
      ad = next;
    };
    box.addEventListener("mouseenter", () => hold = true);
    box.addEventListener("mouseleave", () => hold = false);
    show();
    timer = setInterval(() => { if (!box.isConnected) return clearInterval(timer); if (!hold && box.offsetParent) show(); }, 9000);
    return box;
  };
  list.insertBefore(slot(), list.firstChild);
  const heads = [...list.querySelectorAll(":scope > h3")];
  if (heads.length > 2) list.insertBefore(slot(), heads[2]);
  else if (heads.length > 1) list.insertBefore(slot(), heads[1]);
  list.appendChild(slot());
}

function shopAdBanner(a, onPick, onClose) {
  const style = Math.floor(Math.random() * 6);
  const ad = el("div", { className: "shop-ad shop-ad-" + style, title: "A fake ad for " + a.it.name + ". Click to see it in the shop." });
  const tag = el("span", { className: "shop-ad-tag" }, "AD");
  const x = el("button", { className: "shop-ad-x", title: "Hide this ad" }, "✕");
  x.addEventListener("click", e => { e.stopPropagation(); onClose(); });
  const body = el("div", { className: "shop-ad-body" });
  if (a.it.logo) { const img = el("img", { className: "shop-ad-logo", src: a.it.logo, alt: "" }); img.onerror = () => img.remove(); ad.appendChild(img); }
  if (style === 0) ad.appendChild(el("div", { className: "shop-ad-burst" }, Math.random() < .5 ? "NEW!" : "FREE!*"));
  if (style === 1) body.appendChild(el("div", { className: "shop-ad-kicker" }, "BUT WAIT, THERE'S MORE!"));
  body.appendChild(el("div", { className: "shop-ad-head" }, a.head));
  if (style === 3) body.appendChild(el("div", { className: "shop-ad-quote" }, `“${a.quote}” — ${a.who}`));
  else body.appendChild(el("div", { className: "shop-ad-sub" }, a.sub));
  if (style === 1) { const pr = el("div", { className: "shop-ad-price" }); pr.append("Was ", el("s", {}, "$49.99"), " now $0.00!"); body.appendChild(pr); }
  if (style === 4) { const t = el("div", { className: "shop-ad-timer" }); let s = 299; const tick = () => { t.textContent = `Offer ends in 00:0${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} (it never ends)`; s = s > 0 ? s - 1 : 299; }; tick(); const id = setInterval(() => ad.isConnected ? tick() : clearInterval(id), 1000); body.appendChild(t); }
  body.appendChild(el("div", { className: "shop-ad-foot" }, a.foot));
  const go = el("span", { className: "shop-ad-cta" }, style === 2 ? "▶ CLICK HERE ◀" : a.cta);
  ad.append(tag, body, go, x);
  ad.addEventListener("click", () => onPick(a.it));
  return ad;
}
