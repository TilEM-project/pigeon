import logging
from pigeon.utils import setup_logging


def test_log_file_writes_and_rotates(tmp_path):
    f = tmp_path / "svc.log"
    setup_logging(log_file=str(f), log_file_max_bytes=200, log_file_backups=2)
    logging.getLogger("x").warning("hello-disk")
    for h in logging.getLogger().handlers:
        h.flush()
    assert f.exists() and "hello-disk" in f.read_text()


def test_log_levels_dict_applied():
    setup_logging(log_levels={"noisy.mod": "ERROR"})
    assert logging.getLogger("noisy.mod").level == logging.ERROR


def test_setup_logging_is_idempotent():
    logger = setup_logging("idem.test")
    count = len(logger.handlers)
    setup_logging("idem.test")
    assert len(logger.handlers) == count


def test_explicit_log_levels_override_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "conflict.mod=DEBUG")
    setup_logging(log_levels={"conflict.mod": "ERROR"})
    assert logging.getLogger("conflict.mod").level == logging.ERROR


def test_bad_dict_level_warns_and_skips(caplog):
    target = "badlevel.mod"
    logging.getLogger(target).setLevel(logging.NOTSET)
    with caplog.at_level(logging.WARNING):
        setup_logging("badlevel.logger", log_levels={target: "NOTALEVEL"})
    assert logging.getLogger(target).level == logging.NOTSET
    assert any("NOTALEVEL" in r.message for r in caplog.records)
