from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from ghosty_input import __version__


GITHUB_REPOSITORY = "imedkablavi/ghosty_input"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=20"
RELEASE_DOWNLOAD_PREFIX = f"https://github.com/{GITHUB_REPOSITORY}/releases/download/"
USER_AGENT = f"GhostyInput/{__version__}"
GITHUB_API_VERSION = "2026-03-10"
DEFAULT_TIMEOUT = 8.0
MAX_RELEASE_JSON_BYTES = 4 * 1024 * 1024
MAX_CHECKSUM_BYTES = 512 * 1024
MAX_PACKAGE_BYTES = 700 * 1024 * 1024
UPDATE_CHANNELS = {"auto", "stable", "alpha"}


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    name: str
    url: str
    size: int


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current_version: str
    version: str
    tag: str
    html_url: str
    body: str
    prerelease: bool
    asset: ReleaseAsset
    checksum_asset: ReleaseAsset

    @property
    def available(self) -> bool:
        return _version_key(self.version) > _version_key(self.current_version)


def _version_key(value: str) -> tuple[int, int, int, int, int]:
    """Compare the project's stable and alpha semantic versions."""

    raw = value.strip().lower().lstrip("v")
    raw = raw.replace("-alpha.", "a").replace("-alpha", "a")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:a(\d+))?", raw)
    if not match:
        raise UpdateError(f"Unsupported release version: {value}")
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    alpha = match.group(4)
    if alpha is None:
        return major, minor, patch, 1, 0
    return major, minor, patch, 0, int(alpha)


def _normalize_tag(tag: str) -> str:
    raw = tag.strip().lstrip("v")
    raw = raw.replace("-alpha.", "a").replace("-alpha", "a")
    _version_key(raw)
    return raw


def _read_limited(response, limit: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared:
        try:
            if int(declared) > limit:
                raise UpdateError(f"Update payload exceeds safety limit ({limit} bytes).")
        except ValueError:
            pass
    data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError(f"Update payload exceeds safety limit ({limit} bytes).")
    return data


def _request_bytes(url: str, *, timeout: float, limit: int) -> bytes:
    is_api = url.startswith("https://api.github.com/")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json" if is_api else "application/octet-stream",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise UpdateError(f"Update server returned HTTP {response.status}.")
            return _read_limited(response, limit)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"Update server returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"Unable to reach the update server: {exc.reason}") from exc
    except TimeoutError as exc:
        raise UpdateError("Update check timed out.") from exc


def _assets(payload: dict) -> list[ReleaseAsset]:
    result: list[ReleaseAsset] = []
    for item in payload.get("assets") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        url = str(item.get("browser_download_url") or "")
        try:
            size = int(item.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        if name and url.startswith(RELEASE_DOWNLOAD_PREFIX) and 0 < size <= MAX_PACKAGE_BYTES:
            result.append(ReleaseAsset(name=name, url=url, size=size))
    return result


def installation_kind() -> str:
    if not bool(getattr(sys, "frozen", False)):
        return "source"
    system = platform.system()
    if system == "Windows":
        return "windows-installer"
    if system == "Linux":
        # Use POSIX lexical path semantics explicitly. This keeps classification
        # deterministic in cross-platform tests and matches Linux frozen paths.
        executable = PurePosixPath(str(sys.executable))
        try:
            executable.relative_to(PurePosixPath("/opt/ghosty-input"))
        except ValueError:
            return "linux-portable"
        return "linux-deb"
    return "unsupported"


def _pick_platform_asset(assets: Iterable[ReleaseAsset], *, kind: str | None = None) -> ReleaseAsset:
    items = list(assets)
    selected_kind = kind or installation_kind()
    system = platform.system()

    if selected_kind == "windows-installer" or (selected_kind == "source" and system == "Windows"):
        candidates = [asset for asset in items if asset.name.lower().endswith("setup.exe")]
    elif selected_kind == "linux-deb":
        candidates = [asset for asset in items if asset.name.lower().endswith("_amd64.deb")]
    elif selected_kind in {"linux-portable", "source"} and system == "Linux":
        candidates = [
            asset
            for asset in items
            if "linux" in asset.name.lower() and asset.name.lower().endswith(".tar.gz")
        ]
    else:
        raise UpdateError(f"Automatic updates are not supported for {selected_kind}.")

    if not candidates:
        raise UpdateError(f"Release does not contain a compatible {selected_kind} package.")
    return sorted(candidates, key=lambda item: item.name)[0]


def _pick_checksum_asset(
    assets: Iterable[ReleaseAsset], *, package: ReleaseAsset
) -> ReleaseAsset:
    items = list(assets)
    by_name = {asset.name: asset for asset in items}
    lower_package = package.name.lower()
    if lower_package.endswith(".deb") or "linux" in lower_package:
        preferred = ("SHA256SUMS-Linux.txt", "SHA256SUMS.txt")
    elif lower_package.endswith(".exe") or "windows" in lower_package:
        preferred = ("SHA256SUMS-Windows.txt", "SHA256SUMS.txt")
    else:
        preferred = ("SHA256SUMS.txt",)
    for name in preferred:
        if name in by_name:
            return by_name[name]
    for asset in items:
        if "sha256" in asset.name.lower():
            return asset
    raise UpdateError("Release is missing a SHA-256 checksum asset.")


def _channel_accepts(channel: str, prerelease: bool) -> bool:
    if channel not in UPDATE_CHANNELS:
        raise UpdateError(f"Unsupported update channel: {channel}")
    if channel == "stable":
        return not prerelease
    if channel == "alpha":
        return True
    current_is_prerelease = _version_key(__version__)[3] == 0
    return current_is_prerelease or not prerelease


def _release_candidate(payload: dict, *, channel: str) -> UpdateInfo | None:
    if payload.get("draft"):
        return None
    prerelease = bool(payload.get("prerelease"))
    if not _channel_accepts(channel, prerelease):
        return None
    try:
        tag = str(payload.get("tag_name") or "")
        version = _normalize_tag(tag)
    except UpdateError:
        return None
    if _version_key(version) <= _version_key(__version__):
        return None

    assets = _assets(payload)
    try:
        package = _pick_platform_asset(assets)
        checksum = _pick_checksum_asset(assets, package=package)
    except UpdateError:
        return None
    return UpdateInfo(
        current_version=__version__,
        version=version,
        tag=tag,
        html_url=str(payload.get("html_url") or ""),
        body=str(payload.get("body") or ""),
        prerelease=prerelease,
        asset=package,
        checksum_asset=checksum,
    )


def check_for_update(*, channel: str = "auto", timeout: float = DEFAULT_TIMEOUT) -> UpdateInfo | None:
    payload = json.loads(
        _request_bytes(RELEASES_API, timeout=timeout, limit=MAX_RELEASE_JSON_BYTES).decode("utf-8")
    )
    if not isinstance(payload, list):
        raise UpdateError("Malformed update response.")
    candidates = [
        candidate
        for item in payload
        if isinstance(item, dict)
        if (candidate := _release_candidate(item, channel=channel)) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: _version_key(item.version))


def _parse_checksums(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
        if match:
            result[Path(match.group(2).strip()).name] = match.group(1).lower()
    return result


def _download_to(asset: ReleaseAsset, destination: Path, *, timeout: float) -> None:
    if asset.size > MAX_PACKAGE_BYTES:
        raise UpdateError("Update package exceeds the configured safety limit.")
    request = urllib.request.Request(asset.url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise UpdateError(f"Update download returned HTTP {response.status}.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_PACKAGE_BYTES:
                        raise UpdateError("Downloaded update exceeds the configured safety limit.")
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"Update download returned HTTP {exc.code}.") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"Unable to download update: {exc.reason}") from exc


def _normalize_archive_path(path: PurePosixPath) -> PurePosixPath:
    if path.is_absolute():
        raise UpdateError(f"Unsafe absolute path in update archive: {path}")
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise UpdateError(f"Archive path escapes package root: {path}")
            parts.pop()
        else:
            parts.append(part)
    normalized = PurePosixPath(*parts)
    if not normalized.parts or normalized.parts[0] != "GhostyInput":
        raise UpdateError(f"Archive path escapes GhostyInput root: {path}")
    return normalized


def _validate_portable_archive(package: Path) -> None:
    try:
        with tarfile.open(package, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise UpdateError("Portable update archive is empty.")
            for member in members:
                member_path = _normalize_archive_path(PurePosixPath(member.name))
                if member.ischr() or member.isblk() or member.isfifo():
                    raise UpdateError(f"Unsafe special file in update archive: {member.name}")
                if member.issym():
                    link = PurePosixPath(member.linkname)
                    if link.is_absolute():
                        raise UpdateError(f"Unsafe absolute link in update archive: {member.name}")
                    _normalize_archive_path(member_path.parent / link)
                elif member.islnk():
                    _normalize_archive_path(PurePosixPath(member.linkname))
    except (tarfile.TarError, OSError) as exc:
        raise UpdateError(f"Unable to inspect portable update archive: {exc}") from exc


def download_verified_update(
    info: UpdateInfo,
    *,
    destination_dir: Path | None = None,
    timeout: float = 30.0,
) -> Path:
    checksum_text = _request_bytes(
        info.checksum_asset.url,
        timeout=timeout,
        limit=MAX_CHECKSUM_BYTES,
    ).decode("utf-8")
    checksums = _parse_checksums(checksum_text)
    expected = checksums.get(info.asset.name)
    if not expected:
        raise UpdateError(f"No checksum found for {info.asset.name}.")

    root = destination_dir or Path(tempfile.mkdtemp(prefix="ghosty-input-update-"))
    root.mkdir(parents=True, exist_ok=True)
    package = root / info.asset.name
    _download_to(info.asset, package, timeout=timeout)

    digest = hashlib.sha256()
    with package.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest().lower()
    if actual != expected:
        package.unlink(missing_ok=True)
        raise UpdateError(
            "Downloaded update failed SHA-256 verification. "
            f"Expected {expected}, got {actual}."
        )
    if package.name.lower().endswith(".tar.gz"):
        _validate_portable_archive(package)
    return package


def _portable_update_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail
archive="$1"
target="$2"
parent_pid="$3"
binary_name="$4"
version="$5"
parent="$(dirname -- "$target")"
staging="$(mktemp -d "${parent}/.ghosty-update.XXXXXX")"
backup="${parent}/.GhostyInput-backup-${version}"
cleanup() { rm -rf -- "$staging"; }
trap cleanup EXIT
while kill -0 "$parent_pid" 2>/dev/null; do sleep 0.2; done
tar --no-same-owner --no-same-permissions -xzf "$archive" -C "$staging"
new_root="${staging}/GhostyInput"
test -x "${new_root}/${binary_name}"
rm -rf -- "$backup"
mv -- "$target" "$backup"
if mv -- "$new_root" "$target"; then
  if GHOSTY_EXPECTED_VERSION="$version" "${target}/${binary_name}" --package-smoke-test >/dev/null 2>&1; then
    "${target}/${binary_name}" >/dev/null 2>&1 &
    rm -rf -- "$backup"
    rm -f -- "$archive"
    exit 0
  fi
fi
rm -rf -- "$target"
mv -- "$backup" "$target"
"${target}/${binary_name}" >/dev/null 2>&1 &
exit 1
"""


def launch_installer(package: Path, *, version: str) -> None:
    kind = installation_kind()
    if kind == "source":
        raise UpdateError(
            "This is a source checkout. The release was downloaded and verified, but source "
            "trees are not replaced automatically."
        )
    if kind == "windows-installer":
        if package.suffix.lower() != ".exe":
            raise UpdateError("Windows update is not an executable installer.")
        subprocess.Popen([str(package)], close_fds=True)
        return
    if kind == "linux-deb":
        if not package.name.lower().endswith(".deb"):
            raise UpdateError("Linux package update is not a Debian package.")
        helper = shutil.which("pkexec")
        if not helper:
            raise UpdateError(
                "The update was downloaded and verified, but automatic elevation is unavailable. "
                f"Install it manually with: sudo apt install {shlex.quote(str(package))}"
            )
        subprocess.Popen([helper, "apt-get", "install", "-y", str(package)], close_fds=True)
        return
    if kind == "linux-portable":
        if not package.name.lower().endswith(".tar.gz"):
            raise UpdateError("Portable Linux update is not a tar.gz archive.")
        _validate_portable_archive(package)
        target = Path(sys.executable).resolve().parent
        binary_name = Path(sys.executable).name
        helper = package.parent / "apply-ghosty-update.sh"
        helper.write_text(_portable_update_script(), encoding="utf-8")
        helper.chmod(0o700)
        subprocess.Popen(
            [
                "/usr/bin/env",
                "bash",
                str(helper),
                str(package),
                str(target),
                str(os.getpid()),
                binary_name,
                version,
            ],
            close_fds=True,
            start_new_session=True,
        )
        return
    raise UpdateError(f"Automatic updates are not supported for {kind}.")


def updater_environment() -> str:
    return f"{platform.system()} · {platform.machine()} · {installation_kind()}"
