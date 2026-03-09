from pathlib import Path
import importlib.util
import sys


def load_sendgrid_provider_module():
    root = Path(__file__).resolve().parents[2]
    communication_src = root / "services" / "communication-service" / "src"
    shared_src = root / "services" / "shared-python"

    for entry in [str(communication_src), str(shared_src)]:
        if entry not in sys.path:
            sys.path.insert(0, entry)

    path = communication_src / "providers" / "sendgrid_provider.py"
    spec = importlib.util.spec_from_file_location("sendgrid_provider_for_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load sendgrid provider module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sendgrid_provider_returns_sent_for_2xx(monkeypatch) -> None:
    provider = load_sendgrid_provider_module()
    monkeypatch.setattr(provider.settings, "sendgrid_api_key", "key", raising=False)
    monkeypatch.setattr(provider.settings, "sendgrid_from_email", "noreply@example.com", raising=False)

    class FakeResponse:
        status_code = 202
        headers = {"X-Message-Id": "sg-1"}

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def send(self, message):
            return FakeResponse()

    monkeypatch.setattr(provider, "SendGridAPIClient", FakeClient)

    result = provider.send_email("dealer@example.com", "subject", "body")

    assert result.status == "sent"
    assert result.provider_message_id == "sg-1"


def test_sendgrid_provider_returns_error_for_non_2xx(monkeypatch) -> None:
    provider = load_sendgrid_provider_module()
    monkeypatch.setattr(provider.settings, "sendgrid_api_key", "key", raising=False)
    monkeypatch.setattr(provider.settings, "sendgrid_from_email", "noreply@example.com", raising=False)

    class FakeResponse:
        status_code = 500
        headers = {"X-Message-Id": "sg-2"}

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def send(self, message):
            return FakeResponse()

    monkeypatch.setattr(provider, "SendGridAPIClient", FakeClient)

    result = provider.send_email("dealer@example.com", "subject", "body")

    assert result.status == "error"
    assert result.provider_message_id == "sg-2"
