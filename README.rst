Herdr Selection Actions
=======================

A community plugin that opens selected HTTP(S) URLs and searches selected text.
Not an official Herdr-maintained plugin. No third-party Python packages.

Requirements
------------

* Herdr 0.9.5+ and Python 3.11+ on the server's PATH.
* macOS: uses /usr/bin/open.
* Desktop Linux: xdg-utils (xdg-open), a configured browser, and an X11 or
  Wayland session. Headless servers are rejected with an explanatory notification.
* Windows is not supported.

Install
-------

::

    herdr plugin install DS-argus/herdr-selection-actions

Merge keybindings.example.toml into ~/.config/herdr/config.toml, then run::

    herdr config check && herdr server reload-config

Use your configured Prefix, then Shift+O to open a selected URL, or Shift+S
 to search selected text. Select in copy mode using Prefix, then [, then v.
The plugin does not replace copy mode or change the clipboard. Herdr owns the
copy-mode footer; adding plugin hints there requires a Herdr extension.

Search provider
---------------

Find your configuration directory::

    herdr plugin config-dir ds-argus.selection-actions

Create config.toml there (see config.example.toml)::

    [search]
    provider = "duckduckgo"

Supported values are google and duckduckgo. Missing configuration defaults to
Google. Changes apply on the next search without reloading Herdr. Invalid
configuration is rejected rather than silently sending your text to another
provider. URL opening is independent of search configuration.

Privacy and validation
----------------------

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

Development and tests
---------------------

::

    gh repo clone DS-argus/herdr-selection-actions
    cd herdr-selection-actions
    herdr plugin link "$PWD"
    python3 -m unittest discover -p 'test_*.py' -v

The macOS Herdr/PTY integration test is opt-in::

    RUN_HERDR_INTEGRATION=1 python3 -m unittest discover -p 'test_*.py' -v

It uses an isolated HOME and server, actual copy-mode keys, and a mocked browser
opener. It verifies both actions and preservation of the selection. Platform
unit tests cover macOS and Linux dispatch; a real Linux desktop/browser is not
exercised by these tests. CI runs unit tests on macOS and Ubuntu.

Updating and removing
---------------------

GitHub-managed installations::

    herdr plugin update ds-argus.selection-actions

Linked development checkouts use git pull --ff-only; relink after manifest
changes. When replacing local.open-url, replace its bindings rather than adding
duplicate shortcuts. Remove the two bindings when uninstalling::

    herdr plugin uninstall ds-argus.selection-actions
    herdr config check && herdr server reload-config

For a linked checkout use plugin unlink instead of plugin uninstall.
