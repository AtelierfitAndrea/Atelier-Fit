# FREE_POSE_TRYON phone rule: _lock_hands flags, PHONE_RULE only in pose mode, head_lock.prepare per-hand paste list, QC hint
import asyncio
import io
import os
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import server  # noqa: E402
import head_lock  # noqa: E402
import tryon_quality  # noqa: E402

BOXES = [[450, 530, 520, 630], [600, 380, 650, 440]]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


@pytest.fixture
def fake_info(monkeypatch):
    def setter(phone):
        async def _fake(path, b):
            return {"boxes": BOXES, "phone": phone}
        monkeypatch.setattr(server, "_hand_info", _fake)
    return setter


# Pose mode + phone hand -> phone hand not pasted, PHONE_RULE appended
def test_pose_phone_hand_not_pasted(fake_info):
    fake_info([True, False])
    boxes, keep, txt, _f = _run(server._lock_hands("p", b"", False, True))
    assert boxes == BOXES and keep == [False, True] and txt == server.PHONE_RULE


# Avatar mode with phone -> all hands pasted, no PHONE_RULE
def test_avatar_mode_unaffected(fake_info):
    fake_info([True, False])
    _b, keep, txt, _f = _run(server._lock_hands("p", b"", False, False))
    assert keep == [True, True] and txt == ""


# Pose without phone -> hands pasted, no rule
def test_pose_no_phone(fake_info):
    fake_info([False, False])
    _b, keep, txt, _f = _run(server._lock_hands("p", b"", False, True))
    assert keep == [True, True] and txt == ""


# Bag -> nothing pasted (free hand may grip handle); phone rule still added in pose
def test_pose_bag_phone(fake_info):
    fake_info([True, False])
    _b, keep, txt, _f = _run(server._lock_hands("p", b"", True, True))
    assert keep == [False, False] and txt == server.PHONE_RULE


def _jpeg(w=600, h=900):
    buf = io.BytesIO()
    Image.fromarray((np.random.rand(h, w, 3) * 255).astype(np.uint8)).save(buf, "JPEG")
    return buf.getvalue()


# prepare: per-hand list -> only kept hands in meta["hands"]; bool still supported
def test_prepare_paste_list():
    b = _jpeg()
    _c, meta = head_lock.prepare(b, False, BOXES, [False, True])
    assert len(meta["hands"]) == 1
    _c, meta = head_lock.prepare(b, False, BOXES, True)
    assert len(meta["hands"]) == 2
    _c, meta = head_lock.prepare(b, False, BOXES, False)
    assert len(meta["hands"]) == 0


# QC hint: render source appends NO smartphone when SMARTPHONE REMOVAL in prompt
def test_qc_hint_present():
    import inspect
    src = inspect.getsource(tryon_quality.render)
    assert '"SMARTPHONE REMOVAL" in prompt' in src and "NO smartphone" in src
    assert server.PHONE_RULE.startswith("SMARTPHONE REMOVAL")


# Retry (iteration 53): preserve_pose stored on docs and POSE_RULE re-prepended on free retry
def test_retry_prepends_pose_rule_source():
    import inspect
    t = inspect.getsource(server._tryon_retry)
    o = inspect.getsource(server._outfit_retry)
    assert "_retry_extra(doc, body.reason, user)" in t and "_retry_extra(doc, body.reason, user)" in o
    owner = server.User(user_id="u", email=server.os.environ["OWNER_EMAILS"].split(",")[0].strip(), name="o")
    other = server.User(user_id="v", email="someone@example.com", name="x")
    assert server.POSE_RULE in server._retry_extra({"preserve_pose": True}, "mani_viso", owner)
    assert server.SURGICAL_RULE in server._retry_extra({}, "mani_viso", owner)
    assert "phone held" not in server._retry_extra({"preserve_pose": True}, "mani_viso", owner)
    assert server._retry_extra({"preserve_pose": True}, "mani_viso", other) == server.RETRY_REASONS["mani_viso"]
    assert '"preserve_pose": req.preserve_pose' in inspect.getsource(server._tryon_generate)
    assert '"preserve_pose": req.preserve_pose' in inspect.getsource(server._outfit_generate_from_uploads)


# PHONE_RULE says it overrides other phone-keeping instructions
def test_phone_rule_overrides_header():
    assert "overrides every other instruction" in server.PHONE_RULE.split("\n")[0]


# Fix prompt allows replacing a missing garment / pulling out tuck / removing phone; QC flags missing garment
def test_fix_prompt_and_qc_missing_garment():
    import inspect
    fp = tryon_quality._fix_prompt("missing garment: shorts", "bottom: shorts")
    assert "missing or not applied" in fp and "pull it OUT" in fp and "smartphone" in fp
    assert "missing garment" in inspect.getsource(tryon_quality._qc)
