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


def test_verified_download_rejects_bad_digest(monkeypatch, tmp_path: Path):
    info = UpdateInfo(
        current_version="0.6.0a1",
        version="0.6.0a2",
        tag="v0.6.0-alpha.2",
        html_url="https://github.com/imedkablavi/ghosty_input/releases/tag/v0.6.0-alpha.2",
        body="",
        prerelease=True,
        asset=ReleaseAsset(
            "ghosty-input_0.6.0a2_amd64.deb",
            "https://github.com/example/update.deb",
            4,
        ),
        checksum_asset=ReleaseAsset(
            "SHA256SUMS.txt",
            "https://github.com/example/SHA256SUMS.txt",
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
