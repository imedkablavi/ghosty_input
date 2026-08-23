from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ghosty_input import __version__


GITHUB_REPOSITORY = "imedkablavi/ghosty_input"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
USER_AGENT = f"GhostyInput/{__version__}"
DEFAULT_TIMEOUT = 8.0
MAX_RELEASE_JSON_BYTES = 2 * 1024 * 1024
MAX_CHECKSUM_BYTES = 512 * 1024
MAX_PACKAGE_BYTES = 700 * 1024 * 1024


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
    """Compare the project's simple stable/alpha semantic versions.

    Supported examples: 0.6.0, 0.6.0a1, v0.6.0-alpha.2.
    Stable releases sort newer than their prerelease counterparts.
    """

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
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
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
        if name and url.startswith("https://github.com/") and size >= 0:
            result.append(ReleaseAsset(name=name, url=url, size=size))
    return result


def _pick_checksum_asset(assets: Iterable[ReleaseAsset]) -> ReleaseAsset:
    preferred = [
        "SHA256SUMS.txt",
        "SHA256SUMS-Linux.txt",
        "SHA256SUMS-Windows.txt",
    ]
    by_name = {asset.name: asset for asset in assets}
    for name in preferred:
        if name in by_name:
            return by_name[name]
    for asset in assets:
        if "sha256" in asset.name.lower():
            return asset
    raise UpdateError("Release is missing a SHA-256 checksum asset.")


def _pick_platform_asset(assets: Iterable[ReleaseAsset]) -> ReleaseAsset:
    items = list(assets)
    system = platform.system()
    if system == "Windows":
        candidates = [asset for asset in items if asset.name.lower().endswith("setup.exe")]
        if not candidates:
            candidates = [
                asset
                for asset in items
                if "windows" in asset.name.lower() and asset.name.lower().endswith(".exe")
            ]
    elif system == "Linux":
        # Installed Debian-family builds can upgrade through apt by downloading the .deb.
        if Path("/opt/ghosty-input").exists() or shutil.which("dpkg"):
            candidates = [asset for asset in items if asset.name.lower().endswith("_amd64.deb")]
        else:
            candidates = []
        if not candidates:
            candidates = [
                asset
                for asset in items
                if "linux" in asset.name.lower() and asset.name.lower().endswith(".tar.gz")
            ]
    else:
        raise UpdateError(f"Automatic updates are not supported on {system} yet.")

    if not candidates:
        raise UpdateError(f"Release does not contain a compatible {system} installer.")
    asset = sorted(candidates, key=lambda item: item.name)[0]
    if asset.size > MAX_PACKAGE_BYTES:
        raise UpdateError("Update package exceeds the configured safety limit.")
    return asset


def check_for_update(
    *,
    include_prereleases: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> UpdateInfo | None:
    payload = json.loads(
        _request_bytes(LATEST_RELEASE_API, timeout=timeout, limit=MAX_RELEASE_JSON_BYTES).decode(
            "utf-8"
        )
    )
    if not isinstance(payload, dict):
        raise UpdateError("Malformed update response.")
    if payload.get("draft"):
        return None
    prerelease = bool(payload.get("prerelease"))
    if prerelease and not include_prereleases:
        return None

    tag = str(payload.get("tag_name") or "")
    version = _normalize_tag(tag)
    if _version_key(version) <= _version_key(__version__):
        return None

    assets = _assets(payload)
    asset = _pick_platform_asset(assets)
    checksum = _pick_checksum_asset(assets)
    return UpdateInfo(
        current_version=__version__,
        version=version,
        tag=tag,
        html_url=str(payload.get("html_url") or ""),
        body=str(payload.get("body") or ""),
        prerelease=prerelease,
        asset=asset,
        checksum_asset=checksum,
    )


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
    request = urllib.request.Request(
        asset.url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
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
    return package


def launch_installer(package: Path) -> None:
    system = platform.system()
    if system == "Windows":
        if package.suffix.lower() != ".exe":
            raise UpdateError("Windows update is not an executable installer.")
        subprocess.Popen([str(package)], close_fds=True)
        return

    if system == "Linux" and package.name.lower().endswith(".deb"):
        helper = shutil.which("pkexec")
        if helper:
            subprocess.Popen([helper, "apt-get", "install", "-y", str(package)], close_fds=True)
            return
        raise UpdateError(
            "The update was downloaded and verified, but automatic elevation is unavailable. "
            f"Install it manually with: sudo apt install {package}"
        )

    raise UpdateError(
        "This build can check and securely download updates, but in-place installation is not "
        "available for the current package type."
    )


def updater_environment() -> str:
    frozen = bool(getattr(sys, "frozen", False))
    package = "packaged" if frozen else "source"
    return f"{platform.system()} · {platform.machine()} · {package}"
