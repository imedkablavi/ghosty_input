import io
import tarfile
from pathlib import Path

import pytest

from ghosty_input.core import update_manager
from ghosty_input.core.update_manager import ReleaseAsset, UpdateError, UpdateInfo


def test_version_ordering_alpha_and_stable():
    assert update_manager._version_key("0.6.0a1") < update_manager._version_key("0.6.0a2")
    assert update_manager._version_key("0.6.0a9") < update_manager._version_key("0.6.0")
    assert update_manager._version_key("0.6.0") < update_manager._version_key("0.7.0a1")
    assert update_manager._normalize_tag("v0.6.0-alpha.2") == "0.6.0a2"


def test_checksum_parser_accepts_sha256sum_format():
    parsed = update_manager._parse_checksums(
        "a" * 64 + "  GhostyInputSetup.exe\n" + "b" * 64 + " *ghosty.deb\n"
    )
    assert parsed["GhostyInputSetup.exe"] == "a" * 64
    assert parsed["ghosty.deb"] == "b" * 64


def _linux_release_payload(*, prerelease: bool = True, complete: bool = True) -> dict:
    assets = [
        {
            "name": "GhostyInput-Linux-x86_64-v0.6.0a2.tar.gz",
            "browser_download_url": (
                "https://github.com/imedkablavi/ghosty_input/releases/download/"
                "v0.6.0a2/GhostyInput-Linux-x86_64-v0.6.0a2.tar.gz"
            ),
            "size": 1024,
        }
    ]
    if complete:
        assets.append(
            {
                "name": "SHA256SUMS-Linux.txt",
                "browser_download_url": (
                    "https://github.com/imedkablavi/ghosty_input/releases/download/"
                    "v0.6.0a2/SHA256SUMS-Linux.txt"
                ),
                "size": 128,
            }
        )
    return {
        "draft": False,
        "prerelease": prerelease,
        "tag_name": "v0.6.0a2",
        "html_url": "https://github.com/imedkablavi/ghosty_input/releases/tag/v0.6.0a2",
        "body": "Alpha update",
        "assets": assets,
    }


def test_auto_channel_accepts_newer_alpha_for_alpha_build(monkeypatch):
    monkeypatch.setattr(update_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_manager.sys, "frozen", False, raising=False)
    candidate = update_manager._release_candidate(_linux_release_payload(), channel="auto")
    assert candidate is not None
    assert candidate.version == "0.6.0a2"
    assert candidate.asset.name.endswith(".tar.gz")
    assert candidate.checksum_asset.name == "SHA256SUMS-Linux.txt"


def test_stable_channel_rejects_alpha_release(monkeypatch):
    monkeypatch.setattr(update_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_manager.sys, "frozen", False, raising=False)
    assert update_manager._release_candidate(_linux_release_payload(), channel="stable") is None


def test_incomplete_release_is_ignored_until_assets_finish_uploading(monkeypatch):
    monkeypatch.setattr(update_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_manager.sys, "frozen", False, raising=False)
    assert (
        update_manager._release_candidate(
            _linux_release_payload(complete=False),
            channel="alpha",
        )
        is None
    )


def test_installation_kind_distinguishes_deb_and_portable(monkeypatch):
    monkeypatch.setattr(update_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(update_manager.sys, "frozen", True, raising=False)
    monkeypatch.setattr(update_manager.sys, "executable", "/opt/ghosty-input/GhostyInput")
    assert update_manager.installation_kind() == "linux-deb"
    monkeypatch.setattr(update_manager.sys, "executable", "/home/test/GhostyInput/GhostyInput")
    assert update_manager.installation_kind() == "linux-portable"


def test_verified_download_rejects_bad_digest(monkeypatch, tmp_path: Path):
    info = UpdateInfo(
        current_version="0.6.0a1",
        version="0.6.0a2",
        tag="v0.6.0a2",
        html_url="https://github.com/imedkablavi/ghosty_input/releases/tag/v0.6.0a2",
        body="",
        prerelease=True,
        asset=ReleaseAsset(
            "ghosty-input_0.6.0a2_amd64.deb",
            "https://github.com/imedkablavi/ghosty_input/releases/download/v0.6.0a2/update.deb",
            4,
        ),
        checksum_asset=ReleaseAsset(
            "SHA256SUMS-Linux.txt",
            "https://github.com/imedkablavi/ghosty_input/releases/download/v0.6.0a2/SHA256SUMS-Linux.txt",
            100,
        ),
    )

    monkeypatch.setattr(
        update_manager,
        "_request_bytes",
        lambda *args, **kwargs: ("0" * 64 + f"  {info.asset.name}\n").encode(),
    )

    def fake_download(asset, destination, *, timeout):
        destination.write_bytes(b"data")

    monkeypatch.setattr(update_manager, "_download_to", fake_download)
    with pytest.raises(UpdateError, match="SHA-256"):
        update_manager.download_verified_update(info, destination_dir=tmp_path)
    assert not (tmp_path / info.asset.name).exists()


def test_portable_archive_rejects_path_traversal(tmp_path: Path):
    archive_path = tmp_path / "update.tar.gz"
    payload = b"bad"
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("GhostyInput/../../escape")
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    with pytest.raises(UpdateError, match="Archive path escapes"):
        update_manager._validate_portable_archive(archive_path)


def test_portable_archive_allows_internal_relative_symlink(tmp_path: Path):
    archive_path = tmp_path / "safe-update.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        root = tarfile.TarInfo("GhostyInput")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        lib = tarfile.TarInfo("GhostyInput/lib/libreal.so")
        payload = b"library"
        lib.size = len(payload)
        archive.addfile(lib, io.BytesIO(payload))
        link = tarfile.TarInfo("GhostyInput/bin/libcurrent.so")
        link.type = tarfile.SYMTYPE
        link.linkname = "../lib/libreal.so"
        archive.addfile(link)
    update_manager._validate_portable_archive(archive_path)


def test_portable_update_script_smoke_tests_before_deleting_current_backup():
    script = update_manager._portable_update_script()
    smoke = "--package-smoke-test"
    final_backup_delete = 'rm -rf -- "$backup"'
    assert smoke in script
    assert 'GHOSTY_EXPECTED_VERSION="$version"' in script
    # The first deletion only removes a stale backup left by an older attempt.
    # The final deletion must happen only after the new binary passes smoke.
    assert script.index(smoke) < script.rindex(final_backup_delete)
    assert 'mv -- "$backup" "$target"' in script
