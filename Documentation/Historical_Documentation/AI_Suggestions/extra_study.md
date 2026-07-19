# clodcapture — Deep Analysis & Multi-Provider Porting Guide

*Based on commit `a4b00fb`, manifest version 2.5.0. ~1,345 lines of hand-written, dependency-free JavaScript.*

---

## Part 0 — What this thing actually is, in one paragraph

clodcapture is a **Manifest V3 Chrome extension** that solves one problem: Claude.ai conversations die when the context window fills, and there's no good way to carry a thread forward. It solves it by (a) silently scraping your full conversation JSON out of Claude's own private REST API using your browser's session cookies, (b) storing that JSON locally in IndexedDB, and (c) letting you *re-inject* a distilled/summarized version of any past conversation into the composer box of a brand-new chat — so the new Claude session starts already knowing where you left off.

Everything else — the spider mascot, the GitHub backup, the timeline scrubber, the "keys" — is scaffolding around that core loop.

The core loop is worth naming explicitly, because it's the thing you'll be re-implementing three times:

```
DETECT (you opened a chat)
  → FETCH (pull the conversation from the provider's API)
    → STORE (IndexedDB)
      → DISTILL (strip to role/text pairs)
        → SUMMARIZE (optional LLM call)
          → INJECT (type it into a new chat's composer)
```

**Your porting job is: swap DETECT, FETCH, DISTILL, and INJECT per provider. STORE and SUMMARIZE stay the same.** Hold that thought — everything below builds to it.

---

## Part 1 — Chrome Extension Architecture (the concepts you must own)

If you don't have this model in your head, the code will look like arbitrary spaghetti. It isn't; it's shaped by hard platform constraints.

### 1.1 The four execution contexts

A Chrome extension is not one program. It is **several isolated programs that can only talk by passing messages.** clodcapture uses four:

| Context | File(s) | Where it runs | Can it touch the page DOM? | Can it call `chrome.*` APIs? |
|---|---|---|---|---|
| **Service worker** (background) | `background.js` | Its own headless worker, no DOM at all | ❌ | ✅ (all of them) |
| **Content script** | `content.js`, `fab.js`, `spine.js`, `keys.js` | *Inside the claude.ai tab* | ✅ | ⚠️ Only a subset (`storage`, `runtime`) |
| **Popup** | `popup.html`, `popup.js`, `spider.js` | A tiny ephemeral webpage when you click the toolbar icon | ❌ (only its own DOM) | ✅ (most) |
| **The page itself** | Claude's own React app | The tab | ✅ | ❌ |

This split is the **single most important thing to understand**, and it explains ~80% of the code's structure.

### 1.2 Isolated Worlds — the subtlety that trips everyone up

Content scripts run in the same DOM as the page but in a **separate JavaScript heap**. `fab.js` can call `document.querySelector` and get Claude's real `<div>`s. But it *cannot* see Claude's React internals, its Redux store, its `window.__NEXT_DATA__`, or any JS variable the page defined. Two parallel universes sharing one DOM.

This is why the extension **cannot just read the conversation out of React state.** It has to go around — through the network API (`background.js`) — to get the data. And it's why injecting text into the composer is so awkward (see §3.5).

> Vestigial evidence of a former workaround: `content.js` line 3 listens for `window.postMessage({type:'__bj_tok'})`. `postMessage` is the standard escape hatch for page↔content-script communication. Nothing in the current repo ever *sends* that message — this is dead code from an earlier design where a script was injected into the page's real world (probably to hook `fetch` and steal token counts from Claude's own responses). Worth knowing the technique exists; you may need it for Gemini.

### 1.3 The service worker is *ephemeral*

In MV2, the background page lived forever. **In MV3 it does not.** Chrome kills the service worker after ~30 seconds of idle and restarts it when an event fires. Consequences visible in this code:

- **You cannot rely on in-memory state.** Look at `let _db=null` and `let _idxCache=null` in `background.js` — these are caches that *evaporate* on worker death and are lazily rebuilt (`openDB()`, `getIndex()`). That's not sloppiness, that's the required pattern.
- **You cannot use `setTimeout` for long delays.** Hence `chrome.alarms.create("bg_sync",{periodInMinutes:30})` — alarms are the MV3-sanctioned way to wake a dead worker on a schedule.
- **Top-level code runs on every wake-up.** `captureExistingTabs()` is called at module scope *and* on `onInstalled`/`onStartup` — a belt-and-braces re-entry pattern.

### 1.4 The permission model

```json
"permissions": ["storage","unlimitedStorage","tabs","alarms","cookies","downloads","clipboardWrite","clipboardRead","scripting"],
"host_permissions": ["https://claude.ai/*","https://api.anthropic.com/*","https://api.github.com/*"]
```

Two distinct kinds:

- **`permissions`** = API capabilities. `cookies` lets it read your claude.ai session cookie. `downloads` lets it write files. `scripting` lets the popup force-inject `content.js` into a tab on demand (`popup.js` → `chrome.scripting.executeScript`).
- **`host_permissions`** = *which origins the extension can make credentialed cross-origin requests to.* This is the load-bearing one. **Extensions with host permission for an origin are exempt from CORS** — the service worker can `fetch("https://claude.ai/api/...")` and the browser won't block it. A normal webpage could never do this.

> 🔑 **For your fork, `host_permissions` will need to grow to include `https://chatgpt.com/*`, `https://chat.openai.com/*`, and `https://gemini.google.com/*`.** Note this triggers a new permission prompt for existing users and a fresh Chrome Web Store review, since you're asking to read data from more sites.

### 1.5 Message passing (the extension's nervous system)

Every cross-context interaction is a message. The pattern in this repo:

```js
// sender (popup.js, fab.js — both use an identical helper)
var send=function(type,data){
  return new Promise(function(r){
    chrome.runtime.sendMessage(Object.assign({type:type},data||{}), r);
  });
};

// receiver (background.js)
chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
  if(msg.type==="get_index"){ getIndex().then(reply); return true; }  // ← the `return true`!
  ...
});
```

**`return true` is critical and non-obvious.** It tells Chrome "I'm going to call `reply()` asynchronously, keep the message channel open." Forget it, and your `await send(...)` silently resolves to `undefined`. You'll hit this bug. Everybody does.

`background.js` is essentially **one giant switch statement acting as the app's RPC server** — ~25 message types. This is the extension's real API surface:

| Message | What it does |
|---|---|
| `capture` | Fetch + store a conversation |
| `get_index` / `get_state` | Metadata for the UI |
| `get_distilled` / `get_distilled_range` | Role/text pairs, optionally sliced |
| `get_spine` | Per-message stats (chars, previews) for the timeline UI |
| `generate_key` / `get_key` / `continue_with_key` | LLM-generated summary cards |
| `continue_chat` | The main "resume this session" text builder |
| `grab` / `sync` / `export_one` / `export_keys` / `import_keys` | File I/O |
| `gh_push_all` / `gh_validate` | GitHub backup |
| `get_context_usage` | Token counting |
| `remove` / `clear` / `refresh_all` | Housekeeping |

### 1.6 Sender trust

```js
function isTrusted(sender){ return sender.id===chrome.runtime.id; }
function isPopup(sender){ return !sender.tab && sender.id===chrome.runtime.id; }
```

Any *webpage* can `chrome.runtime.sendMessage` to a known extension ID if the extension declares `externally_connectable` — this one doesn't, so `onMessage` only receives internal messages. But `isPopup` adds a second tier: destructive ops (`remove`, `clear`, `gh_push_all`) require `!sender.tab`, i.e. the message came from the popup, not from a content script running on a page. **This is a defense against a compromised/XSS'd claude.ai page nuking your archive or exfiltrating your GitHub token.** Good instinct. Preserve it.

---

## Part 2 — File-by-file walkthrough

### `manifest.json` — the wiring diagram

```json
"content_scripts": [{
  "matches": ["https://claude.ai/*"],
  "js": ["content.js","fab.js","spine.js","keys.js"],
  "css": ["fab.css","spine.css"],
  "run_at": "document_idle"
}]
```

Four scripts, injected in order, sharing one isolated world. They communicate through **globals on `window`** — a poor man's module system:

- `fab.js` exposes `window.__ccToast`, `window.__ccReopenList`
- `spine.js` exposes `window.__ccSpine`
- `keys.js` exposes `window.__ccKeys` and **monkey-patches `window.__ccRenderItemHook`**, which `fab.js` calls when rendering each list row

That last one is a plugin hook: `fab.js` renders a row, then calls `__ccRenderItemHook(el, id)` if it exists, and `keys.js` uses that to bolt on tag pills and long-press multi-select. It's a decent little extension point — but the load order in the manifest is now load-bearing. Rearrange it and things break silently.

### `background.js` — the engine (~104 dense lines, do not be fooled by the line count)

**Auth (the clever bit):**

```js
async function getCookieHeader(url){
  const cookies=await chrome.cookies.getAll({url});
  const now=Date.now()/1000;
  return cookies.filter(c=>!c.expirationDate||c.expirationDate>now)
                .map(c=>c.name+"="+c.value).join("; ");
}
async function authFetch(url){
  const cookie=await getCookieHeader(url);
  const r=await fetch(url,{headers:{"Cookie":cookie}});
  ...
}
```

The concept: **the extension impersonates you.** It doesn't need an API key or an OAuth flow, because you're already logged into claude.ai and the browser holds a valid session cookie. `chrome.cookies` (with the `cookies` permission + host permission) lets the extension read it and replay it.

> ⚠️ **Technical caveat worth verifying yourself:** `Cookie` is on the [forbidden header names](https://developer.mozilla.org/en-US/docs/Glossary/Forbidden_header_name) list — `fetch()` is generally supposed to strip it. In practice, extension service-worker fetches to hosts in `host_permissions` typically get cookies attached *automatically* by Chrome anyway, so this works regardless of whether the explicit header survives. Verify with DevTools before you rely on either mechanism for a new provider. This is exactly the sort of thing that is stable-until-it-isn't.

**The endpoint:**

```js
const Q="?tree=True&rendering_mode=messages&render_all_tools=true&consistency=eventual";
// GET https://claude.ai/api/organizations/{orgUuid}/chat_conversations/{chatId} + Q
```

This is a **private, undocumented, reverse-engineered API.** No contract, no versioning, no stability guarantee. Anthropic can change it tomorrow. Every provider port will involve the same archaeology, and the same fragility. Internalize this: **you are building on sand, deliberately, and you need to design so that when one provider's sand shifts, only one adapter file breaks.**

Note `getOrg()` — Claude namespaces conversations under an organization UUID, so there's a preliminary call to `/api/organizations`, cached in `chrome.storage.local` for 24h. **This is Claude-specific ceremony that ChatGPT and Gemini don't have.** Your adapter interface needs to tolerate providers that require a bootstrap/handshake step and providers that don't.

**Storage — two tiers, deliberately:**

| Tier | API | What's in it | Why |
|---|---|---|---|
| Hot metadata | `chrome.storage.local` under key `_index` | `{chatId: {name, message_count, captured_at, updated_at, tags}}` | Small; popup needs it instantly on every open |
| Cold payloads | **IndexedDB** (`brainjar` db, `chats` store) | Full raw conversation JSON strings | Can be megabytes; `chrome.storage.local` has a ~10MB quota (lifted by `unlimitedStorage`, but IDB is still the right tool for blobs) |

Understanding *why* there are two stores — and not just one — is a real architectural lesson. **Never make your fast path pay for your slow data.**

Also: `chrome.storage.local` is used as a grab-bag keyed namespace: `_org`, `_index`, `_key_{chatId}`, `_spine_range_{chatId}`, `_ctx_{chatId}`, `_fab_pos`, `apiKey`, `ghToken`, `ghRepo`, `ghAutoSync`. There's no schema. **When you add providers you will need to namespace these** (see Part 5).

**`distill()` — the normalization boundary. This is the most important function in the repo for your purposes:**

```js
function distill(raw){
  const data=typeof raw==="string"?JSON.parse(raw):raw;
  const msgs=(data.chat_messages||[]).flatMap(msg=>{
    const role=msg.sender==="human"?"human":"assistant";
    const text=(msg.content||[])
      .filter(c=>c.type==="text"&&(c.text||"").trim())
      .map(c=>c.text.trim()).join("\n\n");
    return text?[{role,text}]:[];
  });
  return {title:data.name||"session", created_at:data.created_at, messages:msgs};
}
```

Look at what it does: takes Claude's *specific, weird* JSON shape (`chat_messages[].sender`, `content[].type==='text'`) and flattens it to a **provider-agnostic** `{title, created_at, messages:[{role,text}]}`.

**That output shape is already your universal interchange format.** Everything downstream — `get_spine`, `generate_key`, `continue_chat`, `get_context_usage` — consumes *distilled* data, not raw data. The author accidentally (or deliberately) built the exact seam you need. **The port is largely: give each provider its own `distill()` and its own `fetchRaw()`, and leave the rest alone.**

**Capture triggers — belt, braces, and a second belt:**

1. `content.js` patches `history.pushState`/`replaceState` (see §3.1) → sends `capture` on SPA nav
2. `background.js` listens to `chrome.tabs.onUpdated` → catches full page loads
3. `chrome.alarms` every 30 min → walks the full conversation list and refreshes everything
4. `onInstalled` / `onStartup` / module load → `captureExistingTabs()`

Redundant on purpose. SPAs are slippery; missing a capture is worse than a wasted one. There's a debounce in `capture()`: skip if captured <30s ago and `updated_at` is unchanged.

**Zero-dependency flexing:** `buildZip()` is a hand-rolled ZIP writer (local file headers, central directory, EOCD record, a from-scratch CRC-32) using STORE mode (no compression). `dl()` base64-encodes content into a `data:` URI and hands it to `chrome.downloads`. Both exist to avoid pulling in JSZip. Admirable, and also 30 lines you never have to look at again.

### `content.js` — navigation detection + composer injection (7 lines, minified, dense)

Its two jobs:

**1. SPA navigation detection.** Claude.ai is a single-page app. Clicking a conversation does *not* fire a page load — it calls `history.pushState()` and re-renders. There is **no native event** for that. So:

```js
var _push=history.pushState;
history.pushState=function(){ _push.apply(this,arguments); checkNav(); };
```

**Monkey-patching the History API.** This is *the* canonical technique for observing SPA route changes from outside the app, and you will use it for all three providers. It also patches `replaceState`, listens to `popstate` (back/forward button), and listens to `visibilitychange` (tab refocus → force a re-check).

**2. Composer injection.** See §3.5 below — it's important enough for its own section.

### `fab.js` — the floating spider button

A draggable FAB (position persisted to `chrome.storage.local._fab_pos`), a dropdown panel with search (`#tag` prefix filters by tag), and the "context sweep": an SVG spider whose **color drains to grayscale** as your context window fills, via an animated `clipPath` over a `feColorMatrix saturate=0` filter. Genuinely nice piece of design — an ambient, glanceable signal instead of a number.

Note `updateRing()` polls `get_context_usage` every 30s. Also `SHOW_RE=/^https:\/\/claude\.ai\/(chat|new)/` gates visibility — **another hardcoded provider assumption.**

### `spine.js` — the timeline scrubber

Renders the conversation as a vertical bar where each message is a tick sized proportionally to its character count, with two draggable handles to select a range (plus "Last 10 / Last 25 / 2nd half / All" quick chips). Live token estimate, color-coded (amber >50k, red >150k). "Go with N messages" then builds a prompt containing *only that slice* and injects it.

**Concept: this is manual context curation.** Rather than summarize, let the user surgically pick which parts of history matter. Range persisted per-chat to `_spine_range_{chatId}`.

### `keys.js` — "portable chat keys"

The most conceptually interesting feature. From `_0/idea3-portable-keys.yaml`:

> *"A trading card for each conversation — compact, structured, machine-readable. The AI reads the card, not the book."*

`generate_key` sends the distilled chat to **Claude Haiku** with a system prompt demanding strict JSON:

```json
{"summary":"...","entities":{"people":[],"tools":[],"files":[],"decisions":[]},
 "arc":"...","tags":["max 5"],"last_state":"...","next_step":"..."}
```

Stored at `_key_{chatId}`. Tags get merged back into `_index` so the FAB search can filter by `#tag`.

Then `continue_with_key` lets you **long-press to multi-select up to 5 chats** and stitch their *keys* (not their full transcripts) into a single primer prompt. That's the difference between spending 200k tokens re-loading three conversations and spending ~600. **Summarization-as-compression is the whole idea, and it's the most portable part of this codebase** — it operates purely on distilled data and has zero provider coupling.

### `popup.js` + `popup.html` + `spider.js`

The toolbar UI: connection status, context gauge (SVG dashed ring), Copy / Save File / Export All buttons, a searchable chat list, and a settings panel for the Anthropic API key and GitHub repo/token. `spider.js` is a canvas-rendered animated spider on a glowing web that recoils when you click it. Pure whimsy; ~130 lines of `CanvasRenderingContext2D`. Ignore it for porting.

`popup.js` also demonstrates `chrome.scripting.executeScript({target:{tabId},files:['content.js']})` — force-injecting the content script from the popup, in case the page loaded before the extension did. (`content.js` guards against double-injection with `window.__ccHandler`.)

---

## Part 3 — The techniques worth stealing

### 3.1 History API monkey-patching

Already covered — but internalize it. There is no `onRouteChange` event in the browser. You patch `pushState`/`replaceState`, listen to `popstate`, and (for the paranoid) add a `MutationObserver` on `<title>` or a URL polling `setInterval` as a fallback. **You'll want the fallback for Gemini**, which is aggressive about its own routing.

### 3.2 Cookie-borrowed API access

`chrome.cookies` + `host_permissions` + `fetch` = you can call any private API the logged-in user could call. This is the entire foundation of the extension. It's also the thing most likely to break per-provider (see Part 6).

### 3.3 Two-tier storage

Hot index in `chrome.storage.local`, cold blobs in IndexedDB. Learn IndexedDB's promise-wrapping ceremony (`openDB` / `dbPut` / `dbGet` in `background.js` is a clean minimal example) or just use [`idb`](https://github.com/jakearchibald/idb) in your fork.

### 3.4 MV3 service worker lifecycle discipline

Cache lazily, never assume liveness, use `chrome.alarms` not `setInterval` for anything over ~30s.

### 3.5 **Composer injection — read this twice**

This is the hardest, jankiest, most provider-specific part of the codebase, and it's where you'll spend the most debugging time.

The problem: Claude's composer is a **ProseMirror** rich-text editor (a `contenteditable` div, not a `<textarea>`). React/ProseMirror maintain their *own* internal document model. If you do `el.textContent = "hello"`, the text appears on screen and then **vanishes** on the next render, because React's virtual DOM doesn't know about it. There is no state change. The send button stays disabled.

You must make the editor believe **a human did it**. The code's escalating ladder:

```js
// 1. Find it — three fallback selectors, because the DOM churns
var el = document.querySelector('[contenteditable="true"].ProseMirror')
      || document.querySelector('[contenteditable="true"][data-placeholder]')
      || document.querySelector('[role="textbox"][contenteditable="true"]');

// 2. Temporarily strip aria-hidden from ancestors (content.js only) —
//    focus() silently fails inside an aria-hidden subtree
while(anc && anc!==document.body){
  if(anc.hasAttribute('aria-hidden')){ hidden.push([anc, anc.getAttribute('aria-hidden')]);
                                       anc.removeAttribute('aria-hidden'); }
  anc=anc.parentElement;
}

// 3. Focus, wait for React to settle
el.focus({preventScroll:true});
await new Promise(r=>setTimeout(r,80));

// 4. THE TRICK: synthesize a real paste event with a real DataTransfer payload
var dt=new DataTransfer();
dt.setData('text/plain', text);
el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
el.dispatchEvent(new InputEvent('input',{bubbles:true}));

// 5. Fallback: the deprecated-but-still-works execCommand
await new Promise(r=>setTimeout(r,150));
if(!el.textContent.trim()) document.execCommand('insertText',false,text);

// 6. Last resort (fab.js/spine.js): copy to clipboard, tell the user to Cmd+V
if(!el){ await navigator.clipboard.writeText(text); toast('Copied - paste with Cmd+V'); }
```

The **synthetic `ClipboardEvent` with a populated `DataTransfer`** is the key insight. ProseMirror has a real paste handler; feed it a real-looking paste and it parses the content into its internal model properly. This is far more robust than faking keystrokes.

Also note `waitForComposer()` — after `window.location.href='https://claude.ai/new'`, the content scripts are destroyed and re-injected on the new page, so there's a polling loop (15 attempts × 200ms) waiting for the composer to mount before injecting.

> 🔑 **Every provider has a different editor.** ChatGPT uses a plain `<textarea id="prompt-textarea">` in some versions and a ProseMirror `contenteditable` in others. Gemini uses a Quill-based `contenteditable` (`rich-textarea .ql-editor`). **The paste-event trick generally works for all of them**, but the selectors and the "is it ready" check absolutely do not transfer. This must be per-adapter.

### 3.6 Trust boundaries in message passing

Don't let a webpage-adjacent context (content script) trigger destructive or credential-touching operations. `isPopup(sender)` is the guard. Keep it.

---

## Part 4 — Sharp edges and bugs I found (read before you fork)

Fixing these is a great way to learn the codebase, and several *must* be fixed before a multi-provider version works.

1. **`continue_with_key` sends a message to itself.** In `background.js`, when a key is missing, it does `chrome.runtime.sendMessage({type:'generate_key',...})` — **but a service worker's own `onMessage` listener does not fire for messages it sends itself.** That call is dead. It's masked by an inline fallback right after, so you get a crude first-message/last-message summary instead of an LLM-generated key. Fix: call `generateKey(chatId)` as a plain function. (Refactoring the message switch into named functions is the right move anyway.)

2. **Read-modify-write race on `_index`.** `putIndex()` does `getIndex()` → mutate → `chrome.storage.local.set()`. Two concurrent captures (very plausible during the 30-min alarm sweep, or with multiple tabs) can drop an entry. Fix with a promise-chained write queue or a mutex.

3. **`_idxCache` is never invalidated on external writes.** `generate_key` writes `_index` directly via `chrome.storage.local.set({_index:idx})` while `_idxCache` holds a stale copy. Because it mutates the same object reference, it *happens* to work — which is worse than an outright bug, because it will break the moment someone refactors.

4. **Secrets in plaintext.** `apiKey` and `ghToken` (a GitHub PAT with repo-write scope!) live unencrypted in `chrome.storage.local`. Any other extension with `storage` permission cannot read them (storage is per-extension), but they're plainly visible in the extension's own devtools and in a profile backup. Consider `chrome.storage.session` for the API key, or at minimum a scary warning.

5. **Dead code:** the `__bj_tok` postMessage listener in `content.js`. Nothing sends it.

6. **Implicit global `event`.** `popup.js`'s `continueChat()` references the deprecated global `event` object. Works in Chrome, is a landmine.

7. **Hardcoded `200000` context window** in two places. Not even true across Claude models, let alone across GPT-4o (128k), Gemini 1.5 Pro (2M), etc. Must become a per-provider constant.

8. **`chars/3.5` token estimate.** Fine for Claude/English. Roughly OK elsewhere. Just know it's a heuristic.

9. **No message-ordering guarantee in `distill`.** It trusts the API's array order. Claude's API returns a `tree=True` structure — branched conversations (from message edits/regenerations) may not linearize the way you expect. **ChatGPT's API definitely returns a `mapping` tree with a `current_node` pointer and you MUST walk the parent chain to get the active branch.** This is a real, concrete difference that will bite you.

---

## Part 5 — The refactor: how to make this multi-provider

### 5.1 Find the seams

Grep for the provider coupling. Here is the complete list of Claude-specific surface:

| File | Coupling |
|---|---|
| `manifest.json` | `host_permissions`, `content_scripts.matches` |
| `background.js` | `Q` query string, `CHAT_RE` (UUID format), `getOrg()`, `fetchRaw()` path, `api()` base URL, `distill()` field names, `200000` window, `/api/organizations/.../chat_conversations` list endpoint |
| `content.js` | `RE` (chat URL regex), composer selectors |
| `fab.js` | `CHAT_RE`, `SHOW_RE`, `'https://claude.ai/new'`, composer selectors |
| `spine.js` | `CHAT_RE`, `'https://claude.ai/new'`, composer selectors |
| `keys.js` | `'https://claude.ai/new'`, composer selectors |

Provider-**agnostic** (leave alone): IndexedDB layer, ZIP builder, download helpers, GitHub sync, the entire `key` generation/stitching system, the spine UI logic, the FAB UI, the popup shell.

That ratio — a handful of regexes, one fetch function, one field-mapping function, and one DOM selector set — is why this is a very tractable port. **The author built a Claude-shaped app around a provider-agnostic core without quite noticing.**

### 5.2 The Adapter pattern

Define one interface. Implement it three times.

```js
// providers/types.js  (documentation only, it's plain JS)
/**
 * @typedef {Object} Provider
 * @property {string}   id                      // 'claude' | 'chatgpt' | 'gemini'
 * @property {string}   label
 * @property {string[]} hostMatches             // for manifest generation
 * @property {number}   contextWindow           // e.g. 200000
 *
 * // --- DETECT (runs in content script) ---
 * @property {(url:string) => string|null} chatIdFromUrl
 * @property {(url:string) => boolean}     shouldShowFab
 * @property {string}   newChatUrl               // where "continue" navigates to
 *
 * // --- FETCH (runs in service worker) ---
 * @property {() => Promise<any>}          bootstrap        // org lookup / token grab / no-op
 * @property {(id:string) => Promise<string>} fetchRaw      // returns raw JSON string
 * @property {() => Promise<{id:string}[]>}   listChats     // for the 30-min sweep
 *
 * // --- DISTILL (pure function, runs anywhere) ---
 * @property {(raw:string) => {title:string, created_at:string, messages:{role:'human'|'assistant', text:string}[]}} distill
 *
 * // --- INJECT (runs in content script) ---
 * @property {() => Element|null} findComposer
 */
```

Then a registry:

```js
// providers/index.js
import claude from './claude.js';
import chatgpt from './chatgpt.js';
import gemini from './gemini.js';

export const PROVIDERS = { claude, chatgpt, gemini };

export function providerForUrl(url){
  return Object.values(PROVIDERS).find(p => p.hostMatches.some(h => matches(url,h))) || null;
}
```

Every call site becomes `const p = providerForUrl(url); p.fetchRaw(id)` instead of a hardcoded Claude call.

> **MV3 note:** service workers support ES modules via `"background":{"service_worker":"background.js","type":"module"}`. Content scripts do **not** support `import` directly — you either bundle (esbuild/rollup — worth adding; this repo's zero-dep purity is charming but will fight you at three providers) or use `chrome.runtime.getURL` + dynamic `import()`, or just concatenate the provider files into the content script list and use globals as the repo already does.

### 5.3 Namespace your storage

Today's keys are provider-blind and will collide. Chat IDs from different providers could theoretically clash, and `_index` merging three providers' chats without a `provider` field means you can't route "continue" correctly.

Minimum change:

```js
// index entries gain a provider field
_index = { "claude:abc-123": {provider:'claude', name, ...},
           "chatgpt:def-456": {provider:'chatgpt', name, ...} }

// keys become
_key_claude_abc-123
_spine_range_chatgpt_def-456

// IndexedDB: either separate object stores per provider, or prefixed keys.
// Prefixed keys are simpler and let you keep one `chats` store.
```

Bump `DB_VER` and write an `onupgradeneeded` migration that rewrites existing keys with a `claude:` prefix. (**IndexedDB migrations are a real skill** — `onupgradeneeded` is the only place you can create/alter object stores, and it runs inside a `versionchange` transaction. Test it against a populated DB.)

### 5.4 Cross-provider continuation — the actual killer feature

Once the index carries a `provider` field and `distill()` is normalized, you get something the original can't do: **capture a Claude conversation and continue it inside ChatGPT.** The "key" (`{summary, entities, arc, last_state, next_step}`) is a portable, model-agnostic artifact by construction. That's a genuinely differentiated feature, and it falls out of the architecture almost for free.

The one wrinkle: `generate_key` currently hardcodes a call to `api.anthropic.com` with Claude Haiku. You'll want a pluggable *summarizer* — the summarizing model doesn't have to be the same vendor as either the source or destination chat. Let the user pick (Anthropic key, OpenAI key, Gemini key, or the free no-key fallback).

---

## Part 6 — Per-provider reconnaissance (and honest warnings)

⚠️ **Everything below is a starting hypothesis, not a spec.** These are private, undocumented, actively-defended endpoints. **My knowledge has a cutoff and these change frequently — you must verify each one yourself in DevTools before writing a line of code.** The *method* for verifying is the durable skill; the specific endpoints are disposable.

### How to do the recon (do this first, for each provider)

1. Open the provider, log in, open a conversation.
2. DevTools → Network → filter XHR/Fetch → reload.
3. Find the request that returns the conversation content. Look at its URL, method, and **request headers** — especially `Authorization` and any anti-bot tokens.
4. Right-click → **Copy as fetch** → paste into console → confirm it works standalone.
5. Now the key question: **does it work from the extension service worker with only cookies?** If it needs a `Bearer` token or a challenge token, you need an extra step.
6. Inspect the response JSON. Map its shape to `{role, text}`. Watch for tree structures.

### Claude (the baseline — already done)
- Cookie auth. ✅ Simplest of the three.
- Requires an org UUID bootstrap.
- Response: `chat_messages[]`, `sender: 'human'|'assistant'`, `content[]` blocks.

### ChatGPT (`chatgpt.com`)
**Expect: medium difficulty.**
- Cookies alone are likely **not** enough. ChatGPT's backend API typically wants an `Authorization: Bearer <accessToken>`, where the token is obtained by hitting the session endpoint (`/api/auth/session`) — which *is* cookie-authenticated. So: **cookie → session endpoint → bearer token → conversation endpoint.** That's your `bootstrap()`.
- The conversation endpoint is generally `/backend-api/conversation/{id}`, with a list at `/backend-api/conversations?offset=0&limit=N`.
- **Cloudflare / anti-bot:** POST requests (sending messages) are gated behind challenge tokens. **GETs for reading conversations are usually much less defended** — and reading is all you need. This is a meaningful advantage of the "capture" design: you never have to *send* through the API, only through the DOM.
- **⚠️ The tree problem.** The conversation response is a `mapping` object: `{ [nodeId]: {id, message, parent, children[]} }` plus a `current_node`. To get the linear active conversation you must **start at `current_node` and walk `parent` pointers to the root, then reverse.** Naively iterating `Object.values(mapping)` gives you every abandoned edit/regeneration branch, out of order. Your `distill()` must do the walk.
- Roles live at `message.author.role` (`user`|`assistant`|`system`|`tool`), text at `message.content.parts[]` (for `content_type:'text'`). Filter out system/tool nodes and empty parts.
- Composer: historically `#prompt-textarea`. It has been both a `<textarea>` and a ProseMirror `contenteditable` at different times. **Write the selector as a fallback chain and expect to maintain it.**
- New chat URL: `https://chatgpt.com/` (root) or `/?model=...`.

### Gemini (`gemini.google.com`)
**Expect: hard. This is the one that will cost you a weekend.**
- Google does **not** expose a clean REST conversation API. The frontend talks over **`batchexecute`** — a Google-internal RPC transport that POSTs URL-encoded, nested-JSON-in-a-string payloads to `/_/BardChatUi/data/batchexecute?rpcids=...` and returns a `)]}'`-prefixed, deeply-nested, positionally-indexed array. There are no field names. It is genuinely hostile to reverse-engineer, and it is not stable.
- It also requires an `at` token (an XSRF token scraped from the page's inline `WIZ_global_data`) and correct `f.req` encoding.
- **My honest recommendation: do not fight `batchexecute` for v1.** Instead, use the **DOM-scraping fallback path** for Gemini:
  - Content script reads the rendered conversation directly out of the page (`user-query` / `model-response` custom elements, or whatever the current class names are).
  - Scroll to load the full history (Gemini virtualizes/lazy-loads), or use a `MutationObserver` to accumulate messages as they render.
  - Emit the same normalized `{role, text}[]` shape.
- **This is a strong argument for a second seam in your adapter interface:** a provider should be able to declare `strategy: 'api' | 'dom'`. API providers implement `fetchRaw()`; DOM providers implement `scrapeConversation()` in the content script and message the result *up* to the service worker for storage. Same `distill()` contract, same storage, same everything downstream. **Design for this from day one** — retrofitting a DOM strategy into an API-only architecture is painful.
- Composer: Quill-based, roughly `rich-textarea .ql-editor[contenteditable="true"]`. The paste trick should work.
- Gemini's URLs look like `/app/{hexid}` rather than UUIDs — so `CHAT_RE` must be per-provider (it already needs to be).

### Summary table

| | Auth | Read strategy | Data shape | Composer | Difficulty |
|---|---|---|---|---|---|
| **Claude** | Cookies | REST `/api/.../chat_conversations/{id}` | Flat `chat_messages[]` | ProseMirror | 🟢 done |
| **ChatGPT** | Cookies → bearer token | REST `/backend-api/conversation/{id}` | **Tree** (`mapping` + `current_node`) | textarea *or* ProseMirror | 🟡 medium |
| **Gemini** | Cookies + `at` XSRF token | `batchexecute` RPC — **or DOM scrape** | Positional arrays / DOM | Quill `.ql-editor` | 🔴 hard |

---

## Part 7 — A concrete plan

**Phase 0 — Understand by breaking.** Load the extension unpacked. Open `chrome://extensions` → "Inspect views: service worker" to get a devtools console *for the background script* (this is not obvious and you will need it constantly). Add `console.log` inside `capture()` and `distill()`. Watch it fire as you navigate claude.ai. Trigger every message type from the popup and watch the RPC traffic. **Do not write code until you've watched the existing loop run end-to-end.**

**Phase 1 — Refactor in place, no new providers.** Extract `providers/claude.js` implementing the interface from §5.2. Make `background.js` route through `providerForUrl()`. Namespace storage keys and write the IndexedDB migration. **Ship this and confirm nothing regressed.** You now have a multi-provider architecture with exactly one provider — which is the safest possible place to be standing.

**Phase 2 — Add ChatGPT (API strategy).** Do the DevTools recon. Implement `bootstrap()` (session → bearer), `fetchRaw()`, and the **tree-walking `distill()`**. Add host permissions and content-script matches. Fix the composer selectors. Test capture → key → continue *within* ChatGPT.

**Phase 3 — Cross-provider continue.** Now capture a Claude chat and continue it in ChatGPT. This is your differentiator. Make the summarizer model configurable.

**Phase 4 — Add Gemini (DOM strategy).** Introduce the `strategy: 'dom'` branch. Content script scrapes, messages up to the SW, SW stores. Accept that this will be the most brittle adapter and design the failure mode (a clear "couldn't read this conversation" toast, not a silent crash).

**Phase 5 — Hardening.** Fix the bugs in Part 4. Add a bundler. Add tests for each `distill()` against saved JSON fixtures — **fixture-based tests on `distill()` are the single highest-value tests in this codebase**, because that's where provider drift will silently corrupt your data.

---

## Part 8 — Your learning checklist

Things you should be able to explain from memory before you're comfortable here:

- [ ] The four extension contexts and what each can/can't do
- [ ] Isolated worlds — why a content script can't read React state
- [ ] Why `return true` in `onMessage` matters
- [ ] Why the MV3 service worker dies, and the three patterns for coping (lazy caches, alarms, re-entrant top-level init)
- [ ] `permissions` vs `host_permissions`, and why host permissions exempt you from CORS
- [ ] Monkey-patching `history.pushState` to detect SPA navigation
- [ ] Borrowing session cookies via `chrome.cookies` to call a private API
- [ ] IndexedDB basics: `onupgradeneeded`, object stores, transactions, and versioned migrations
- [ ] Why you can't just set `.textContent` on a React/ProseMirror editor — and why a synthetic `ClipboardEvent` + `DataTransfer` works
- [ ] Tree-vs-list conversation models (and why ChatGPT's `current_node` walk is mandatory)
- [ ] The Adapter pattern, and specifically: what is the narrowest interface that separates "provider" from "everything else"

**Docs worth actually reading:** Chrome's [Extensions MV3 overview](https://developer.chrome.com/docs/extensions/mv3/), the [service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers) page, and MDN on [IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API) and [DataTransfer](https://developer.mozilla.org/en-US/docs/Web/API/DataTransfer).

---

## Closing note on ethics & fragility

Two things to go in clear-eyed on:

1. **You are consuming private APIs and scraping DOM from services whose ToS may prohibit automated access.** This extension only ever reads data *the logged-in user already owns and can see*, and stores it locally — which is the most defensible possible position, and is roughly the same posture as a "download my data" button. But be deliberate about it, keep it read-only, keep the data local, and don't build anything that sends messages on the user's behalf through the private APIs (the DOM-injection approach for *writing* is both more robust and more defensible — note the original author already made this choice, whether by accident or design).

2. **This will break.** Not "if." Claude, OpenAI, and Google will all change their internals. The architecture's whole job is to ensure that when one does, exactly one file needs fixing, the failure is loud and legible, and your users' already-captured data is untouched. **Design for graceful decay, not for permanence.**

Good luck. The core idea here — *conversations are data you should own, and context is a portable artifact* — is a genuinely good one, and it deserves to work across all three.
