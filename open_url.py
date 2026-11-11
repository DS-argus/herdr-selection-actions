#!/usr/bin/env python3
"""Explicit selection actions for macOS and desktop Linux without shell evaluation."""
import ipaddress
import json
import os
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urlencode, urlsplit
from pathlib import Path
import shutil
import tomllib

SEARCH_PROVIDERS = {
    "google": "https://www.google.com/search",
    "duckduckgo": "https://duckduckgo.com/",
}


class SelectionError(ValueError):
    pass

def search_provider():
    directory = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    if not directory:
        return "google"
    try:
        with (Path(directory) / "config.toml").open("rb") as handle:
            config = tomllib.load(handle)
    except FileNotFoundError:
        return "google"
    except (OSError, tomllib.TOMLDecodeError):
        raise SelectionError("Cannot read plugin config.toml. Check syntax and permissions.") from None
    if set(config) - {"search"}:
        raise SelectionError("Unknown config section; only [search] is supported.")
    search = config.get("search", {})
    if not isinstance(search, dict) or set(search) - {"provider"}:
        raise SelectionError("Use [search] with a provider setting.")
    provider = search.get("provider", "google")
    if not isinstance(provider, str) or provider not in SEARCH_PROVIDERS:
        raise SelectionError("Search provider must be google or duckduckgo.")
    return provider


def open_browser(url):
    if sys.platform == "darwin":
        executable = "/usr/bin/open"
    elif sys.platform.startswith("linux"):
        executable = shutil.which("xdg-open")
        if not executable:
            raise SelectionError("Install xdg-utils and configure a desktop browser to open links.")
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise SelectionError("No graphical Linux session. Remote client browser opening is not supported.")
    else:
        raise SelectionError("This plugin supports macOS and desktop Linux only.")
    subprocess.run([executable, url], check=True, timeout=10, capture_output=True)


def validate_url(text):
    if not isinstance(text, str) or not text.strip():
        raise SelectionError("Select one HTTP(S) URL first.")
    # Strip only ordinary surrounding spaces. Do not silently join wrapped lines
    # or let urlsplit discard control characters before validation.
    url = text.strip(" ")
    if len(url) > 8192:
        raise SelectionError("The selected URL is too long.")
    if any(char.isspace() or unicodedata.category(char).startswith("C") for char in url):
        raise SelectionError("Select one URL without spaces or line breaks.")
    if "\\" in url or any(char in url for char in '<>"'):
        raise SelectionError("Select the URL without surrounding markup.")
    if not re.match(r"\Ahttps?://", url, re.IGNORECASE):
        raise SelectionError("Only HTTP(S) URLs are allowed.")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port  # Validate bracketed hosts and numeric port range.
        if not host or parts.username is not None or parts.password is not None:
            raise ValueError("missing host or embedded credentials")
        if parts.netloc.endswith(":") or port == 0:
            raise ValueError("invalid port")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            ascii_host = host.encode("idna").decode("ascii").rstrip(".")
            labels = ascii_host.split(".")
            if len(ascii_host) > 253 or any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in labels
            ):
                raise ValueError("invalid host")
    except (ValueError, UnicodeError) as error:
        raise SelectionError("Invalid host, port, or embedded credentials.") from error
    return url


def selected_text():
    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
    except json.JSONDecodeError as error:
        raise SelectionError("Cannot read the Herdr selection context.") from error
    if not isinstance(context, dict):
        raise SelectionError("Invalid Herdr selection context.")
    return context.get("selected_text")


def selected_url():
    return validate_url(selected_text())


def open_selected_url():
    url = selected_url()
    # No shell, eval, clipboard, selection mutation, or browser URL extraction.
    open_browser(url)


def search_url(text, provider="google"):
    if provider not in SEARCH_PROVIDERS:
        raise SelectionError("Search provider must be google or duckduckgo.")
    if not isinstance(text, str) or not text.strip():
        raise SelectionError("Select some text to search first.")
    if len(text) > 2048:
        raise SelectionError("Select no more than 2048 characters to search.")
    if any(unicodedata.category(char).startswith("C") and char not in "\t\n\r" for char in text):
        raise SelectionError("The selection contains unsupported control characters.")
    query = " ".join(text.split())
    return SEARCH_PROVIDERS[provider] + "?" + urlencode({"q": query})


def search_selected_text():
    url = search_url(selected_text(), search_provider())
    open_browser(url)

def notify(message):
    print(f"Selection actions: {message}", file=sys.stderr)
    try:
        subprocess.run(
            [os.environ.get("HERDR_BIN_PATH", "herdr"), "notification", "show",
             "Selection actions", "--body", message],
            timeout=5, capture_output=True, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        # The original error remains in the plugin log even if toast delivery fails.
        pass


def main(action="open"):
    try:
        if action == "open":
            open_selected_url()
        elif action == "search":
            search_selected_text()
        else:
            raise SelectionError("Unknown selection action.")
    except SelectionError as error:
        notify(str(error))
        return 1
    except (OSError, subprocess.SubprocessError):
        # Do not log the selected URL: query strings can contain credentials.
        notify("Could not open the browser. Check your desktop browser settings and opener installation.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ""))
