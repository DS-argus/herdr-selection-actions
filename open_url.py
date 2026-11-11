#!/usr/bin/env python3
"""Open selected HTTP(S) URLs or explicitly search text on the server's Mac."""
import ipaddress
import json
import os
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urlencode, urlsplit


class SelectionError(ValueError):
    pass


def validate_url(text):
    if not isinstance(text, str) or not text.strip():
        raise SelectionError("먼저 http:// 또는 https:// 주소 하나를 선택해 주세요.")
    # Strip only ordinary surrounding spaces. Do not silently join wrapped lines
    # or let urlsplit discard control characters before validation.
    url = text.strip(" ")
    if len(url) > 8192:
        raise SelectionError("선택한 주소가 너무 깁니다.")
    if any(char.isspace() or unicodedata.category(char).startswith("C") for char in url):
        raise SelectionError("공백·줄바꿈 없이 URL 하나만 선택해 주세요.")
    if "\\" in url or any(char in url for char in '<>"'):
        raise SelectionError("주소 이외의 기호를 제외하고 URL만 선택해 주세요.")
    if not re.match(r"\Ahttps?://", url, re.IGNORECASE):
        raise SelectionError("http:// 및 https:// 주소만 열 수 있습니다.")
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
        raise SelectionError("호스트·포트가 올바른 URL인지 확인해 주세요. 인증정보가 포함된 주소는 열지 않습니다.") from error
    return url


def selected_text():
    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON", "{}"))
    except json.JSONDecodeError as error:
        raise SelectionError("Herdr 선택 정보를 읽을 수 없습니다.") from error
    if not isinstance(context, dict):
        raise SelectionError("Herdr 선택 정보가 올바르지 않습니다.")
    return context.get("selected_text")


def selected_url():
    return validate_url(selected_text())


def open_selected_url():
    url = selected_url()
    # No shell, eval, clipboard, selection mutation, or browser URL extraction.
    subprocess.run(["/usr/bin/open", url], check=True, timeout=10, capture_output=True)


def search_url(text):
    if not isinstance(text, str) or not text.strip():
        raise SelectionError("검색할 텍스트를 먼저 선택해 주세요.")
    if len(text) > 2048:
        raise SelectionError("검색은 2048자 이하로 선택해 주세요.")
    if any(unicodedata.category(char).startswith("C") and char not in "\t\n\r" for char in text):
        raise SelectionError("제어문자가 포함된 선택 내용은 검색하지 않습니다.")
    query = " ".join(text.split())
    return "https://www.google.com/search?" + urlencode({"q": query})


def search_selected_text():
    url = search_url(selected_text())
    subprocess.run(["/usr/bin/open", url], check=True, timeout=10, capture_output=True)

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
            raise SelectionError("알 수 없는 선택 동작입니다.")
    except SelectionError as error:
        notify(str(error))
        return 1
    except (OSError, subprocess.SubprocessError):
        # Do not log the selected URL: query strings can contain credentials.
        notify("브라우저를 열지 못했습니다. macOS 기본 브라우저 설정을 확인해 주세요.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) == 2 else ""))
