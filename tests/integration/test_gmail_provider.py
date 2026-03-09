from pathlib import Path
import importlib.util
import sys


def load_gmail_provider_module():
    root = Path(__file__).resolve().parents[2]
    communication_src = root / "services" / "communication-service" / "src"
    shared_src = root / "services" / "shared-python"

    for entry in [str(communication_src), str(shared_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = communication_src / "providers" / "gmail_provider.py"
    spec = importlib.util.spec_from_file_location("gmail_provider_for_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load gmail provider module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gmail_provider_dry_run_without_credentials(monkeypatch) -> None:
    provider = load_gmail_provider_module()
    monkeypatch.setattr(provider.settings, "gmail_username", None, raising=False)
    monkeypatch.setattr(provider.settings, "gmail_app_password", None, raising=False)
    monkeypatch.setattr(provider.settings, "gmail_from_email", None, raising=False)

    result = provider.send_email_gmail("dealer@example.com", "subject", "body")

    assert result.status == "dry_run"


def test_gmail_provider_sent_when_smtp_succeeds(monkeypatch) -> None:
    provider = load_gmail_provider_module()
    monkeypatch.setattr(provider.settings, "gmail_username", "user@gmail.com", raising=False)
    monkeypatch.setattr(provider.settings, "gmail_app_password", "app-pass", raising=False)
    monkeypatch.setattr(provider.settings, "gmail_from_email", "user@gmail.com", raising=False)

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self):
            return None

        def login(self, username, password):
            assert username == "user@gmail.com"
            assert password == "app-pass"

        def send_message(self, message):
            assert message["To"] == "dealer@example.com"

    monkeypatch.setattr(provider.smtplib, "SMTP", FakeSMTP)

    result = provider.send_email_gmail("dealer@example.com", "subject", "body")

    assert result.status == "sent"


def test_gmail_provider_error_when_smtp_fails(monkeypatch) -> None:
    provider = load_gmail_provider_module()
    monkeypatch.setattr(provider.settings, "gmail_username", "user@gmail.com", raising=False)
    monkeypatch.setattr(provider.settings, "gmail_app_password", "app-pass", raising=False)
    monkeypatch.setattr(provider.settings, "gmail_from_email", "user@gmail.com", raising=False)

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            raise RuntimeError("smtp down")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(provider.smtplib, "SMTP", FakeSMTP)

    result = provider.send_email_gmail("dealer@example.com", "subject", "body")

    assert result.status == "error"
    assert "smtp down" in result.detail
