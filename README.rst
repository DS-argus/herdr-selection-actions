Herdr Selection Actions
=======================

A community plugin for opening a selected HTTP(S) URL or explicitly searching
selected text with Google. This is not an official Herdr-maintained plugin.

Requirements
------------

* macOS, Herdr 0.9.5 or newer, and Python 3.11+ on Herdr's PATH.
* No third-party Python packages or build step.
* Only Herdr 0.9.5 has been integration-tested so far.

Install
-------

This repository is private. Clone with authenticated GitHub access, then link::

    gh repo clone DS-argus/herdr-selection-actions
    cd herdr-selection-actions
    herdr plugin link "$PWD"

Merge ``keybindings.example.toml`` into ``~/.config/herdr/config.toml``::

    herdr config check && herdr server reload-config

If replacing ``local.open-url``, replace its two existing bindings rather than
adding duplicate keys. Linking this plugin does not change your configuration
or remove the old plugin automatically.

Use
---

Enter Herdr copy mode (Prefix, then ``[``), begin selection with ``v``, and select:

* Prefix, then Shift+O: open exactly one HTTP(S) URL.
* Prefix, then Shift+S: search the selected text with Google.

Prefix means your configured Herdr prefix, not a hardcoded Ctrl+A.
The copy-mode footer is owned by Herdr and cannot be extended by this plugin.
The plugin does not remap bare copy-mode keys or replace copy mode.

Security and privacy
--------------------

URL opening accepts only HTTP(S), rejects credentials, invalid hosts/ports,
control characters, internal whitespace and multiline selections. Only ordinary
surrounding spaces are trimmed. Select the URL itself, not Markdown wrappers.

Search is a separate explicit action: it normalizes whitespace, URL-encodes one
query parameter, rejects control characters and limits input to 2048 characters.
Selected text is sent to Google through your browser only when search is invoked.
Do not search secrets or private code. There is no automatic search fallback.

The opener receives one argument without shell evaluation. The plugin does not
read or overwrite your clipboard, store selections, or include selected URLs in
its own error messages. Browser history, OS process arguments, and Herdr's own
logging are outside this guarantee.

Opening happens on the Mac running the Herdr server. Remote client browser
opening, file opening, configurable search providers and footer hints are not
implemented. Python URL validation does not establish that a website is safe.

Development
-----------

Run unit tests::

    python3 -m unittest discover -p 'test_*.py' -v

Run the opt-in Herdr/PTY test on macOS::

    RUN_HERDR_INTEGRATION=1 python3 -m unittest discover -p 'test_*.py' -v

The integration test uses a temporary HOME and named server. It exercises real
copy-mode selection and both shortcuts, including reusing the same selection.
Only browser opening is replaced with an argument recorder; it sends no search
traffic and does not touch your active Herdr session.

Update a linked installation with ``git pull --ff-only``. Source changes apply
on the next action; after manifest changes, run ``herdr plugin link "$PWD"`` again.
To uninstall, remove the two keybindings and run::

    herdr plugin unlink ds-argus.selection-actions
    herdr config check && herdr server reload-config

Publishing
----------

A future public repository can support ``herdr plugin install
DS-argus/herdr-selection-actions --ref <tag>``. Marketplace discovery uses the
``herdr-plugin`` topic; private repositories are not publicly discoverable.
No release tag or marketplace registration has been created yet.
