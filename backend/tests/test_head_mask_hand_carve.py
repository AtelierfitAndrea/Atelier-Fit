"""head_lock.prepare hand carve-out (iteration_49): hand/phone boxes are removed from the head-paste mask
below face_top+0.6*face_h, eyes/nose stay locked; paste_hands=False keeps carving but returns no hands."""
import os
import sys
import numpy as np
import pytest
import requests

sys.path.insert(0, "/app/backend")
import head_lock  # noqa: E402


def _env_url():
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()


API = (os.environ.get("REACT_APP_BACKEND_URL") or _env_url()).rstrip("/") + "/api"
H = {"Authorization": "Bearer pending_test_tok"}
PHONE_BOX = [278, 545, 375, 686]
LOW_HAND = [576, 381, 667, 459]


@pytest.fixture(scope="module")
def avatar():
    p = requests.get(f"{API}/profile/avatar", headers=H).json()["path"]
    r = requests.get(f"{API}/files/{p}", headers=H)
    assert r.status_code == 200 and len(r.content) > 10000
    return r.content


def test_no_hands_mask_has_head(avatar):
    _, meta = head_lock.prepare(avatar, False, [])
    assert meta["face"] is not None and meta["mask"].max() == 255
    assert meta["hands"] == []


def test_phone_carved_eyes_kept(avatar):
    _, base = head_lock.prepare(avatar, False, [])
    _, meta = head_lock.prepare(avatar, False, [PHONE_BOX, LOW_HAND])
    fx, fy, fw, fh = meta["face"]
    m0, m1 = base["mask"].astype(int), meta["mask"].astype(int)
    # eyes/nose band (face_top+0.2..0.5 h) identical
    eye = slice(int(fy + 0.2 * fh), int(fy + 0.5 * fh))
    cols = slice(int(fx + 0.2 * fw), int(fx + 0.8 * fw))
    assert np.abs(m0[eye, cols] - m1[eye, cols]).max() <= 2, "eyes/nose region changed"
    # some mask removed overall (phone overlaps chin)
    removed = int(((m0 > 128) & (m1 < 40)).sum())
    print("removed px", removed, "face", meta["face"], "hands", meta["hands"])
    assert removed > 0
    # nothing removed above y_keep
    y_keep = int(fy + 0.6 * fh)
    above = (m0[: y_keep - 30] > 128) & (m1[: y_keep - 30] < 40)
    assert not above.any()
    assert len(meta["hands"]) == 2


def test_paste_hands_false_still_carves(avatar):
    _, a = head_lock.prepare(avatar, False, [PHONE_BOX], True)
    _, b = head_lock.prepare(avatar, False, [PHONE_BOX], False)
    assert np.array_equal(a["mask"], b["mask"])
    assert b["hands"] == [] and len(a["hands"]) == 1
