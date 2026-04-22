# Nurunote
<!-- README tracks the currently usable desktop features and fresh benchmark numbers. -->

Nurunote is a local-first desktop memo app built with Rust, Tauri v2, SolidJS, TypeScript, and Milkdown.
It works directly on local Markdown files, keeps wiki-links and search local, and stays focused on a fast three-pane note workflow instead of cloud sync or plugin sprawl.

## Recommended IDE Setup

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)

## Development Setup

Install the following tools before running the app:

- Rust toolchain (`rustup`, `cargo`)
- Node.js 20 or later
- `pnpm`
- Tauri v2 prerequisites for your OS

## Development Workflow

1. Install dependencies:

   ```bash
   pnpm install
   ```

2. Start the desktop app in development mode:

   ```bash
   pnpm tauri dev
   ```

3. Build the frontend bundle:

   ```bash
   pnpm build
   ```

4. Run Rust checks:

   ```bash
   cargo check --manifest-path src-tauri/Cargo.toml
   ```

## Current Capabilities

- Vault workflow
  - Open a local directory as a vault through the native folder picker
  - Restore the last vault automatically on launch when the saved path is still valid
  - Auto-select the first note when a vault opens so the editor is immediately usable
  - Recursively list Markdown files and keep empty folders visible in the sidebar
- Notes and folders
  - Create notes in the vault root or directly into a nested path like `folder/subfolder/note`
  - Create empty folders from the UI
  - Rename and delete notes
  - Rename folders and delete empty folders
  - Move notes between folders by drag and drop, including back to the vault root
- Editing
  - Edit note bodies with Milkdown while preserving YAML frontmatter as-is
  - Use Markdown shortcuts, slash commands, and `[[wiki-link]]` autocomplete in the editor
  - Use undo/redo with `Cmd/Ctrl+Z`, `Shift+Cmd/Ctrl+Z`, and `Cmd/Ctrl+Y`
  - Auto-save edits with configurable debounce timing
  - Detect external file changes and avoid self-save races or silent overwrite conflicts
- Navigation and search
  - Resolve wiki-links from relative vault paths and keep backlinks cached in Rust
  - Open linked notes by clicking wiki-links in the editor
  - Search filenames and note bodies through a local Tantivy index
  - Refresh backlinks and search incrementally when the watcher sees vault changes
- Settings and polish
  - Persist theme, save debounce, search debounce, hotkeys, and last vault path locally
  - Switch between light and dark themes
  - Open Settings, Search, Vault picker, and Theme toggle through customizable hotkeys

## Current Limitations

- Graph view is still a stub and is not part of the usable workflow yet
- Export/import, tags, pinned notes, and structured frontmatter editing are not implemented
- Folder deletion is intentionally limited to empty folders for safety
- Search still indexes filename and body only, not YAML frontmatter

## Rust Commands

- `open_vault`
- `open_vault_path`
- `list_files`
- `list_directories`
- `build_link_graph`
- `get_backlinks`
- `search`
- `load_settings`
- `save_settings`
- `report_app_ready`
- `read_file`
- `write_file`
- `create_note`
- `create_folder`
- `delete_note`
- `delete_folder`
- `rename_note`
- `rename_folder`
- `move_note`

## Wiki-Link Rules

- `[[folder/note]]` resolves from the vault root using the note's relative path without the `.md` extension
- `[[note]]` resolves only when the basename is unique across the entire vault
- Ambiguous basenames stay unresolved and are never auto-resolved to the first match

## Search Notes

- Search indexes use the `filename` and `body` fields; note titles come from filenames, not H1 headings
- YAML frontmatter is preserved in the file but excluded from the current search index
- Vault file changes trigger incremental search index updates through the shared watcher

## Settings And Hotkeys

- Settings are stored as JSON under the Tauri app config directory for the current OS
- The settings screen edits the last vault path, theme, save debounce, search debounce, and hotkeys
- Hotkeys are app-scoped and active while the Nurunote window is focused
- Default hotkeys:
  - Search palette: `CmdOrCtrl+P`
  - Settings: `CmdOrCtrl+,`
  - Open vault picker: `CmdOrCtrl+O`
  - Toggle theme: `Alt+Shift+T`

## Performance Snapshot

Measured on 2026-04-09 on an Apple M1 Pro (`arm64`) using the macOS release bundle.

| Metric | Result | Method |
| --- | --- | --- |
| Cold startup to app-ready signal | 348.3 ms average across 5 runs | `NURUNOTE_PERF_STARTUP=1` against the bundled macOS binary with a fresh temporary `HOME` each run |
| Renderer ready after WebView attach | 39.6 ms average across 5 runs | `performance.now()` reported by the frontend on the same startup runs |
| Cold-launch max RSS | 78.4 MiB average across 5 runs | `/usr/bin/time -l` around the bundled macOS binary on the same startup runs |
| Synthetic 1,000-note index build | 231.8 ms | `cargo test --manifest-path src-tauri/Cargo.toml --release perf_benchmark -- --ignored --nocapture` |
| Synthetic 1,000-note search average | 0.13 ms | Same benchmark, 30 repeated searches |
| Synthetic 1,000-note search p95 | 0.14 ms | Same benchmark, 30 repeated searches |

Notes:

- Startup numbers were measured against the bundled binary at `src-tauri/target/release/bundle/macos/Nurunote.app/Contents/MacOS/nurunote`
- The startup benchmark used a fresh temporary `HOME` per run, so it reflects base app startup without restored user state
- Search numbers use the ignored Rust benchmark test in `src-tauri/src/indexer/search.rs`, which generates a synthetic 1,000-note vault
- The frontend bundle is still emitted as one large chunk, so future code-splitting is still one obvious startup optimization

## Benchmark Commands

Search benchmark:

```bash
cargo test --manifest-path src-tauri/Cargo.toml --release perf_benchmark -- --ignored --nocapture
```

Startup benchmark on macOS release bundle:

```bash
tmp_home=$(mktemp -d /tmp/nurunote-bench-home.XXXXXX)
/usr/bin/time -l env HOME="$tmp_home" NURUNOTE_PERF_STARTUP=1 \
  src-tauri/target/release/bundle/macos/Nurunote.app/Contents/MacOS/nurunote
rm -rf "$tmp_home"
```

## Local Build Instructions

### macOS

1. Install Xcode Command Line Tools:

   ```bash
   xcode-select --install
   ```

2. Install Rust, Node.js 20+, and `pnpm`
3. Install frontend dependencies:

   ```bash
   pnpm install
   ```

4. Build the desktop bundle:

   ```bash
   pnpm tauri build
   ```

5. Find the app and DMG under `src-tauri/target/release/bundle/`

### Linux

Ubuntu/Debian packages used by local builds and GitHub Actions:

```bash
sudo apt-get update
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev \
  libappindicator3-dev \
  librsvg2-dev \
  patchelf \
  libgtk-3-dev \
  libglib2.0-dev \
  libssl-dev
```

Then build:

```bash
pnpm install
pnpm tauri build
```

Build artifacts are written to `src-tauri/target/release/bundle/`.

### Windows

1. Install Microsoft Visual Studio C++ Build Tools with the MSVC toolchain
2. Install WebView2 Runtime
3. Install Rust with the MSVC target, Node.js 20+, and `pnpm`
4. Install frontend dependencies:

   ```powershell
   pnpm install
   ```

5. Build the desktop bundle:

   ```powershell
   pnpm tauri build
   ```

6. Installer outputs are written to `src-tauri\target\release\bundle\`

## GitHub Actions Release Workflow

- Workflow file: `.github/workflows/release.yml`
- `v*` tags create a draft GitHub Release with macOS, Linux, and Windows bundles through `tauri-apps/tauri-action`
- Manual `workflow_dispatch` runs build every bundle and upload them as GitHub Actions artifacts
- The workflow also runs `pnpm build` and `cargo check --manifest-path src-tauri/Cargo.toml` before bundling

## Comparison

| Category | Nurunote | Notion | Obsidian |
| --- | --- | --- | --- |
| Primary storage | Local `.md` files | Cloud-first database | Local files |
| Offline ownership | Strong | Limited | Strong |
| Editing model | Local-first Milkdown editor with wiki-links | Collaborative block editor | Markdown-first editor |
| Startup target | Native desktop app with Tauri | Web-heavy desktop shell | Native-ish Electron app |
| Wiki-links | Built in | Limited / indirect | Built in |
| Backlinks | Built in | Limited / indirect | Built in |
| Full-text search | Local Tantivy index | Remote service backed | Local index |
| Theme and hotkeys | Persisted locally and customizable | Theme support, less file-centric customization | Strong customization |
| Collaboration | Not implemented yet | Best-in-class | Plugin-dependent / lighter |
| Data portability | High | Medium | High |
| Positioning | Local-first memo app with Markdown ownership and wiki-link navigation | Team workspace and docs hub | Personal knowledge base with deep extensibility |
