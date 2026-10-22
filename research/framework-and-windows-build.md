# Framework and the Windows build path

Ticket: #5 Choose the desktop framework and the Windows build path
Date: 2026-08-13

---

## Recommendation

**Tauri v2, built on a GitHub Actions Windows runner, and — if the laboratory computers are centrally managed — signed with a self-signed certificate deployed as a trusted root.**

Cost: **nothing**, in that case. If the computers are not centrally managed, **Azure Artifact Signing at about $9.99 per month**.

---

## 1. Framework: Tauri v2

| | Tauri v2 | Electron |
|---|---|---|
| Installed size | 2–10 MB | 80–200 MB |
| Idle memory | 20–100 MB | Considerably more |
| Rendering engine | WebView2 (the system's own) | Bundles Chromium |
| Language under the interface | Rust | JavaScript |
| Ecosystem maturity | Younger | Older, more proven |

Size is the least important reason. Three things decide it for this application.

### 1a. It can open a document in Word

This is the hard requirement from ticket #8: if a click cannot open the `.docx`, the analyst goes back to the folder and the viewer dies.

Tauri's **opener plugin** does exactly this. `openPath()` opens a file in its default application — a `.docx` opens in Word. There is a matching Rust method, `open_path()`. Access is granted per path pattern through `opener:allow-open-path` in the capability configuration.

This answers most of ticket #9 before it starts.

### 1b. Its permission model is an advantage here, not an obstacle

Tauri restricts file access by default, which sounds like friction for an application whose whole job is reading a folder. It is the opposite.

The **dialog plugin** extends the file system scope automatically to whatever folder the user picks. The **persisted-scope plugin** saves that grant across restarts. So the workflow is: the owner points the viewer at the OneDrive folders once, and it remembers.

The compliance consequence matters more. The viewer can be shown to read **only** the folders it was pointed at, and nothing else on the computer. In a laboratory that will one day be asked what a piece of software can touch, that is a real answer rather than "everything the user can read", which is what Electron gives.

### 1c. WebView2 is already on the machines

Tauri renders through WebView2, which ships with Microsoft Edge and is present on effectively all Windows 10 and 11 machines. Tauri's installer can carry the bootstrapper for any machine that lacks it.

### The cost of choosing Tauri

Rust. The application logic stays JavaScript — the prototype's code carries across — but the shell, the plugins and the build configuration are Rust. That is my problem, not the laboratory's, and it is configuration rather than programming.

---

## 2. Build path: GitHub Actions

**A Mac cannot meaningfully cross-compile a Tauri application for Windows.** Tauri depends on native toolchains, and cross-compilation is not supported. There is a `cargo-xwin` workaround, but it is not a path to stand a laboratory's software on.

The supported answer is to build on a Windows machine. GitHub Actions provides one.

- The repository is already on GitHub.
- `tauri-action` builds for each platform on its own runner using a matrix.
- **Cost: nothing.** The Free plan includes 2,000 minutes a month on private repositories. Windows minutes are deducted at 2×, so a 10–15 minute build costs 20–30 minutes of quota. That is roughly 60 builds a month, free.
- The output lands on the repository's Releases page, which is also the distribution address for the laboratory computers.

This removes the problem I flagged when the repository was first linked.

---

## 3. Signing and SmartScreen — the finding that changes the answer

The original question assumed the viewer would be distributed like public software, and would therefore have to fight SmartScreen. **It does not.** This is internal software for the laboratory's own managed computers.

### If the laboratory computers are centrally managed

Microsoft's own guidance lists this case: a **self-signed certificate** deployed as a trusted root through **Intune or Group Policy** allows managed devices to install the application silently. No SmartScreen warning, no certificate to buy, no renewal.

**Cost: nothing.** This is the recommended path, and it depends on a fact ticket #10 will establish: whether an analyst's account can install software, or whether an administrator must.

### If they are not centrally managed

**Azure Artifact Signing** (formerly Trusted Signing) is Microsoft's recommended service for distribution outside the Store.

- About **$9.99 per month**.
- **No hardware token.** It signs directly from a CI/CD pipeline, including GitHub Actions.
- Available to organisations in the USA — Example Labs Corp qualifies.
- Microsoft verifies the organisation's identity first; allow a few business days.

### What not to buy

**Do not buy an EV certificate.** Until 2024 an EV certificate bypassed SmartScreen instantly, and that is still the common advice online. **Microsoft removed that behaviour in 2024.** An EV certificate now builds reputation exactly like an OV one. Paying $400 or more a year for it buys nothing here.

An **OV certificate** costs $150–300 a year and, since June 2023, requires the private key to sit on a hardware token or HSM — a physical object somebody has to look after and plug in at build time. It is the right answer only for organisations that cannot use Azure Artifact Signing.

### What SmartScreen actually does

Under any of the paid options, reputation accumulates per file over download volume. A new build shows a warning until it has been downloaded enough times. A laboratory with a handful of computers will **never** accumulate that volume. So for this application the paid certificates do not solve the warning — only the managed-device route does.

That is the single most useful thing in this research: **the cheapest option is also the only one that actually removes the warning.**

---

## 4. Drawing the graph

The prototype's renderer — 3D force layout, perspective camera, depth sorting, all written directly on canvas — should carry forward as-is.

It handles the present corpus of 198 nodes and 441 links comfortably, it has already been shaped by four rounds of review, and it adds no dependency. The corpus will not grow by an order of magnitude; adding the missing `EXL-TM` test methods takes it to roughly 210 nodes.

If more visual polish is wanted later, `three.js` and `3d-force-graph` bundle into either framework. That is an upgrade, not a prerequisite.

---

## 5. What this settles for other tickets

- **Ticket #9** (open a document from a node): largely answered. `openPath()` from the opener plugin, with path scope granted through the capability file. What remains is the OneDrive placeholder question — what happens when a file has not been downloaded yet.
- **Ticket #10** now carries more weight than it did. Item 5 — whether an analyst can install software or whether an administrator must — decides between free self-signed distribution and $9.99 a month.

## Sources

- [Code signing options for Windows app developers — Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Tauri opener plugin](https://v2.tauri.app/plugin/opener/)
- [Tauri persisted-scope plugin](https://v2.tauri.app/plugin/persisted-scope/)
- [Tauri command scopes](https://v2.tauri.app/security/scope/)
- [Tauri cross-platform compilation](https://v1.tauri.app/v1/guides/building/cross-platform/)
- [Tauri GitHub Actions distribution](https://v2.tauri.app/distribute/pipelines/github/)
