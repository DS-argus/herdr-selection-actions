# Herdr Selection Actions

A community plugin that opens selected HTTP(S) URLs and searches selected text.
Not an official Herdr-maintained plugin. No third-party Python packages.

## Requirements

- Herdr 0.9.5+ and Python 3.11+ on the server's PATH.
- macOS: uses `/usr/bin/open`.
- Desktop Linux: `xdg-utils` (`xdg-open`), a configured browser, and an X11 or
  Wayland session. Headless servers are rejected with an explanatory notification.
- Windows is not supported.

## Quick start

### 1. Install

```sh
herdr plugin install DS-argus/herdr-selection-actions
```

Installation registers the actions. **It does not add keyboard shortcuts or
modify your Herdr configuration.** Python must be available as `python3`.

### 2. Add keyboard shortcuts

Add these entries to `~/.config/herdr/config.toml` (or your custom Herdr
configuration file). Keep existing settings; do not replace the file.
Choose different keys if these are already assigned.

```toml
[[keys.command]]
key = "prefix+shift+o"
type = "plugin_action"
command = "ds-argus.selection-actions.open"
description = "Open selected HTTP(S) URL"

[[keys.command]]
key = "prefix+shift+s"
type = "plugin_action"
command = "ds-argus.selection-actions.search"
description = "Search selected text"
```

These bindings enable the shortcuts, not just their help descriptions.
`prefix` uses your Herdr prefix (Ctrl+B by default, or your customized key).
The same snippet is available in [keybindings.example.toml](keybindings.example.toml).

### 3. Validate and reload

```sh
herdr config check && herdr server reload-config
```

### 4. Select text and try it

With the default copy-mode binding:

1. Press Prefix, then `[` to enter copy mode.
2. Move to the text, press `v`, and extend the selection.
3. Press Prefix, release it, then **Shift+O** to open a selected HTTP(S) URL,
   or **Shift+S** to search the selected text.

For example, select `https://example.com` and use Prefix, then Shift+O.
Search defaults to Google; choosing another provider below is optional.
The plugin preserves your clipboard. Herdr owns the copy-mode footer;
these custom shortcuts are not automatically added to that footer.

## Search provider

Find your configuration directory:

```sh
herdr plugin config-dir ds-argus.selection-actions
```

The plugin does not create its optional configuration file automatically.
Create `config.toml` in the directory printed above, not in the plugin checkout
and not in Herdr's main config (see [config.example.toml](config.example.toml)):

```toml
[search]
provider = "duckduckgo"
```

Supported values are `google` and `duckduckgo`. Missing configuration defaults to
Google. Changes apply on the next search without reloading Herdr. Invalid
configuration is rejected rather than silently sending your text to another
provider. URL opening is independent of search configuration.

## Privacy and validation

Search sends the selection to the chosen provider only on explicit invocation.
Do not search secrets or private code. There is no automatic search fallback.
Search normalizes whitespace, encodes one query parameter, rejects control
characters, and limits input to 2048 characters.

URL opening permits HTTP(S) only, rejects credentials, invalid hosts/ports,
control characters, internal whitespace and multiline selections. Ordinary
surrounding spaces are trimmed. Select the URL itself, not Markdown wrappers.
Validation does not establish that a website is safe.

Commands receive argument arrays without shell evaluation. The plugin does not
store selections or include selected URLs in its own error messages. Browser
history, OS process arguments and Herdr logging are outside that guarantee.
Errors are English and follow Herdr's global notification settings.

Opening happens on the machine running the Herdr server, not automatically on
an SSH client's computer. File opening and remote-client browser forwarding are
not implemented.

## Development and tests

```sh
gh repo clone DS-argus/herdr-selection-actions
cd herdr-selection-actions
herdr plugin link "$PWD"
python3 -m unittest discover -p 'test_*.py' -v
```

The macOS Herdr/PTY integration test is opt-in:

```sh
RUN_HERDR_INTEGRATION=1 python3 -m unittest discover -p 'test_*.py' -v
```

It uses an isolated HOME and server, actual copy-mode keys, and a mocked browser
opener. It verifies both actions and preservation of the selection. Platform
unit tests cover macOS and Linux dispatch; a real Linux desktop/browser is not
exercised by these tests. CI runs unit tests on macOS and Ubuntu.

## Updating and removing

GitHub-managed installations:

```sh
herdr plugin update ds-argus.selection-actions
```

Linked development checkouts use `git pull --ff-only`; relink after manifest
changes. When replacing `local.open-url`, replace its bindings rather than adding
duplicate shortcuts. Remove the two bindings when uninstalling:

```sh
herdr plugin uninstall ds-argus.selection-actions
herdr config check && herdr server reload-config
```

For a linked checkout use `plugin unlink` instead of `plugin uninstall`.
