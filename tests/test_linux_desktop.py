from pathlib import Path

from ghosty_input.core.linux_desktop import desktop_entry


def test_desktop_entry_uses_exact_executable():
    text = desktop_entry(executable=Path("/opt/ghosty-input/GhostyInput"))
    assert 'Exec="/opt/ghosty-input/GhostyInput"' in text
    assert "Name=Ghosty Input" in text
    assert "Terminal=false" in text


def test_autostart_entry_requests_minimized_start():
    text = desktop_entry(
        executable=Path("/opt/ghosty-input/GhostyInput"),
        minimized=True,
    )
    assert 'Exec="/opt/ghosty-input/GhostyInput" --minimized' in text
