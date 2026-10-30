"""Offline unit tests for contracts/site_proof.py.
Run from the repository root:  python tests/test_site_proof.py"""
import json, os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import genlayer_stub as stub

stub.install()
spec = importlib.util.spec_from_file_location("site_proof", os.path.join(HERE, "..", "contracts", "site_proof.py"))
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

OWNER = "0x" + "1" * 32 + "230adfbb"
OTHER = "0x" + "2" * 40
THIRD = "0x" + "3" * 40


def fresh():
    stub.as_sender(OWNER)
    stub.set_page("")
    stub.set_answer("OK")
    c = sp.SiteProof()
    c.register_site("MoonBaker", "https://example.org/moonbaker", "Meme coin for home bakers who share recipes")
    return c


def rec(c, i=0):
    return json.loads(c.get_record(i))


def raises(fn, text):
    try:
        fn()
    except Exception as e:
        assert text in str(e), f"expected '{text}', got '{e}'"
        return
    raise AssertionError(f"expected error '{text}'")


def test_register_and_verify_line():
    c = fresh()
    r = rec(c)
    assert r["status"] == "PENDING"
    assert r["verify_line"] == "siteproof:0:230adfbb"
    assert c.get_verify_line(0) == "siteproof:0:230adfbb"


def test_input_validation():
    c = fresh()
    stub.as_sender(OTHER)
    raises(lambda: c.register_site("X", "https://a.b", "long enough text"), "Project name")
    raises(lambda: c.register_site("Name", "http://a.b", "long enough text"), "https://")
    raises(lambda: c.register_site("Name", "https://a.b", "short"), "Description")


def test_one_pending_per_owner():
    c = fresh()
    raises(lambda: c.register_site("Second", "https://example.org/2", "Another project page here"), "pending")


def test_broken_link_is_no_website_not_a_crash():
    c = fresh()
    stub.set_page(fail=True)
    c.verify_site(0)
    assert rec(c)["status"] == "REJECTED" and rec(c)["reason"] == "NO_WEBSITE"


def test_missing_verify_line_is_no_proof_without_model_call():
    c = fresh()
    stub.set_page("MoonBaker home page, no proof here")
    before = len(stub._Nondet.prompts)
    c.verify_site(0)
    assert rec(c)["reason"] == "NO_PROOF"
    assert len(stub._Nondet.prompts) == before, "model must not be called without proof"


def test_owner_retry_after_fixing_page():
    c = fresh()
    stub.set_page("MoonBaker page")
    c.verify_site(0)
    stub.as_sender(OTHER)
    raises(lambda: c.verify_site(0), "Only the owner")
    stub.as_sender(OWNER)
    stub.set_page("MoonBaker page siteproof:0:230adfbb")
    c.verify_site(0)
    r = rec(c)
    assert r["status"] == "VERIFIED" and r["retries"] == 1
    assert c.is_verified(0) is True


def test_retry_limit():
    c = fresh()
    stub.set_page("no proof")
    c.verify_site(0)
    for _ in range(3):
        c.verify_site(0)
    raises(lambda: c.verify_site(0), "No retries left")


def test_model_verdicts_and_fail_closed():
    for answer, expected in [("IMPERSONATION", "IMPERSONATION"), ("MISMATCH.", "MISMATCH"),
                             ("SCAM_SIGNS", "SCAM_SIGNS"), ("maybe ok?", "SCAM_SIGNS")]:
        c = fresh()
        stub.set_page("page siteproof:0:230adfbb")
        stub.set_answer(answer)
        c.verify_site(0)
        r = rec(c)
        assert r["status"] == "REJECTED" and r["reason"] == expected, (answer, r["reason"])


def test_recheck_clears_or_flags():
    c = fresh()
    stub.set_page("page siteproof:0:230adfbb")
    c.verify_site(0)
    stub.as_sender(OTHER)
    raises(lambda: c.recheck_site(0, "bad"), "5-200")
    c.recheck_site(0, "Page now promises guaranteed profit")
    assert rec(c)["status"] == "VERIFIED"
    assert "UNVERIFIED" in stub._Nondet.prompts[-1] and "guaranteed profit" in stub._Nondet.prompts[-1]
    raises(lambda: c.recheck_site(0, "again please"), "already")
    stub.as_sender(THIRD)
    stub.set_answer("SCAM_SIGNS")
    c.recheck_site(0, "Asks users to send crypto for double back")
    r = rec(c)
    assert r["status"] == "FLAGGED" and r["reason"] == "SCAM_SIGNS"
    assert c.is_verified(0) is False
    assert [h["kind"] for h in r["history"]] == ["verify", "recheck", "recheck"]


def test_removed_verify_line_flags_on_recheck():
    c = fresh()
    stub.set_page("page siteproof:0:230adfbb")
    c.verify_site(0)
    stub.set_page("page without the line")
    stub.as_sender(OTHER)
    c.recheck_site(0, "Owner proof line was removed")
    assert rec(c)["status"] == "FLAGGED" and rec(c)["reason"] == "NO_PROOF"


def test_cancel_and_lookup():
    c = fresh()
    stub.as_sender(OTHER)
    raises(lambda: c.cancel_site(0), "Only the owner")
    stub.as_sender(OWNER)
    c.cancel_site(0)
    assert rec(c)["reason"] == "CANCELLED"
    assert json.loads(c.find_by_url("https://example.org/moonbaker"))["id"] == 0
    assert c.find_by_url("https://nothing.example") == ""
    assert c.get_record(99) == "" and c.is_verified(99) is False


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
