import pytest
from instagrapi.exceptions import LoginRequired

from xownloader_server.errors import PreviewUnavailable
from xownloader_server.instagram import InstagramSessionManager


class _FakeClient:
    def __init__(self, *, login_error=None, dump_settings_error=None):
        self.login_error = login_error
        self.dump_settings_error = dump_settings_error
        self.login_calls = 0
        self.login_verification_codes = []
        self.loaded_settings_path = None
        self.dumped_settings_path = None

    def load_settings(self, path):
        self.loaded_settings_path = path

    def dump_settings(self, path):
        if self.dump_settings_error is not None:
            raise self.dump_settings_error
        self.dumped_settings_path = path

    def login(self, username, password, verification_code=""):
        self.login_calls += 1
        self.login_verification_codes.append(verification_code)
        if self.login_error is not None:
            raise self.login_error
        return True

    def totp_generate_code(self, seed):
        return "totp-for-" + seed


def _manager(tmp_path, *, client=None, cooldown_seconds=300.0, clock=None, totp_seed=None):
    client = client or _FakeClient()
    manager = InstagramSessionManager(
        "nasa",
        "hunter2",
        tmp_path / "session.json",
        client_factory=lambda: client,
        totp_seed=totp_seed,
        cooldown_seconds=cooldown_seconds,
        clock=clock or (lambda: 0.0),
    )
    return manager, client


def test_ensure_ready_logs_in_and_persists_session(tmp_path):
    manager, client = _manager(tmp_path)
    result = manager.ensure_ready()
    assert result is client
    assert client.login_calls == 1
    assert client.dumped_settings_path == tmp_path / "session.json"


def test_ensure_ready_loads_existing_session_file_first(tmp_path):
    session_path = tmp_path / "session.json"
    session_path.write_text("{}")
    manager, client = _manager(tmp_path)
    manager.ensure_ready()
    assert client.loaded_settings_path == session_path


def test_ensure_ready_skips_load_when_no_session_file_exists(tmp_path):
    manager, client = _manager(tmp_path)
    manager.ensure_ready()
    assert client.loaded_settings_path is None


def test_ensure_ready_reuses_authenticated_client_without_relogging_in(tmp_path):
    manager, client = _manager(tmp_path)
    manager.ensure_ready()
    manager.ensure_ready()
    assert client.login_calls == 1


def test_ensure_ready_raises_preview_unavailable_on_login_failure(tmp_path):
    client = _FakeClient(login_error=LoginRequired("nope"))
    manager, _ = _manager(tmp_path, client=client)
    with pytest.raises(PreviewUnavailable, match="session is invalid"):
        manager.ensure_ready()


def test_ensure_ready_enters_cooldown_after_login_failure(tmp_path):
    client = _FakeClient(login_error=LoginRequired("nope"))
    clock = {"now": 0.0}
    manager, _ = _manager(tmp_path, client=client, clock=lambda: clock["now"])
    with pytest.raises(PreviewUnavailable):
        manager.ensure_ready()
    with pytest.raises(PreviewUnavailable):
        manager.ensure_ready()
    assert client.login_calls == 1


def test_ensure_ready_retries_login_after_cooldown_expires(tmp_path):
    client = _FakeClient(login_error=LoginRequired("nope"))
    clock = {"now": 0.0}
    manager, _ = _manager(
        tmp_path, client=client, cooldown_seconds=300.0, clock=lambda: clock["now"]
    )
    with pytest.raises(PreviewUnavailable):
        manager.ensure_ready()
    clock["now"] = 301.0
    with pytest.raises(PreviewUnavailable):
        manager.ensure_ready()
    assert client.login_calls == 2


def test_ensure_ready_survives_unwritable_session_path(tmp_path):
    client = _FakeClient(dump_settings_error=PermissionError("denied"))
    manager, _ = _manager(tmp_path, client=client)
    result = manager.ensure_ready()
    assert result is client
    assert client.dumped_settings_path is None
    # Login succeeded, so a second call must not log in again even though
    # persistence failed.
    manager.ensure_ready()
    assert client.login_calls == 1


def test_ensure_ready_passes_totp_code_when_seed_configured(tmp_path):
    manager, client = _manager(tmp_path, totp_seed="SEED123")
    manager.ensure_ready()
    assert client.login_verification_codes == ["totp-for-SEED123"]


def test_ensure_ready_strips_spaces_from_totp_seed(tmp_path):
    manager, client = _manager(tmp_path, totp_seed="SEED 123 456")
    manager.ensure_ready()
    assert client.login_verification_codes == ["totp-for-SEED123456"]


def test_ensure_ready_passes_empty_code_without_totp_seed(tmp_path):
    manager, client = _manager(tmp_path)
    manager.ensure_ready()
    assert client.login_verification_codes == [""]


def test_invalidate_forces_relogin_and_starts_cooldown(tmp_path):
    clock = {"now": 0.0}
    manager, client = _manager(tmp_path, clock=lambda: clock["now"])
    manager.ensure_ready()
    manager.invalidate()
    with pytest.raises(PreviewUnavailable):
        manager.ensure_ready()
    assert client.login_calls == 1
