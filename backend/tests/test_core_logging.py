from app.core_logging import format_exception_safely, redact


def test_redact_removes_secrets():
    assert redact("key=abcd1234 here", ["abcd1234"]) == "key=[REDACTED] here"
    assert redact("nothing", [None, ""]) == "nothing"


def test_format_exception_redacts():
    try:
        raise RuntimeError("leaked s3cr3t-value")
    except RuntimeError as e:
        out = format_exception_safely(e, ["s3cr3t-value"])
    assert "Traceback" in out and "s3cr3t-value" not in out and "[REDACTED]" in out
