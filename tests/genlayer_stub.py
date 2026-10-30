"""Minimal offline stand-in for the genlayer SDK, used only by the unit tests.
It lets the contract logic run in plain Python: web pages and model answers are
set by each test, and strict_eq simply runs the block once."""
import sys, types


class _Addr:
    def __init__(self, h):
        self.as_hex = h


class _Message:
    sender_address = _Addr("0x" + "a" * 40)
    value = 0


class _Public:
    @staticmethod
    def view(f):
        return f

    @staticmethod
    def write(f):
        return f


class _Web:
    page = ""
    fail = False

    def render(self, url, mode="text"):
        if _Web.fail:
            raise Exception("WEBPAGE_LOAD_FAILED 404")
        return _Web.page


class _Nondet:
    web = _Web()
    answer = "OK"
    prompts = []

    def exec_prompt(self, prompt):
        _Nondet.prompts.append(prompt)
        return _Nondet.answer


class _Eq:
    @staticmethod
    def strict_eq(fn):
        return fn()


class gl:
    Contract = object
    message = _Message()
    public = _Public()
    nondet = _Nondet()
    eq_principle = _Eq()


def install():
    mod = types.ModuleType("genlayer")
    mod.gl = gl
    mod.__all__ = ["gl"]
    sys.modules["genlayer"] = mod
    return mod


def as_sender(addr):
    gl.message.sender_address = _Addr(addr)


def set_page(text="", fail=False):
    _Web.page = text
    _Web.fail = fail


def set_answer(answer):
    _Nondet.answer = answer
