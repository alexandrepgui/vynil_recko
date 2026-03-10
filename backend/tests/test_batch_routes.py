"""Tests for batch routes (POST /api/batch, GET /api/batch/*, PATCH review)."""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth import User, get_current_user
from conftest import TEST_USER_ID
from repository import Batch, BatchItem
from routes.batch import _process_batch, _reprocess_item


@pytest.fixture()
def mock_repo():
    repo = MagicMock()
    repo.saved_records = []
    repo.save_search_record.side_effect = lambda r: repo.saved_records.append(r)
    repo.load_oauth_tokens.return_value = None
    return repo


@pytest.fixture()
def client(mock_repo, mock_jwt_user):
    from deps import get_repo
    from main import app

    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.pop(get_repo, None)


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


# ── POST /api/batch ──────────────────────────────────────────────────────────


def test_create_batch_rejects_non_zip(client):
    resp = client.post(
        "/api/batch",
        files={"file": ("photos.tar", io.BytesIO(b"data"), "application/gzip")},
    )
    assert resp.status_code == 400
    assert "zip" in resp.json()["detail"].lower()


def test_create_batch_rejects_zip_without_images(client):
    zip_bytes = _make_zip({"readme.txt": b"hello"})
    resp = client.post(
        "/api/batch",
        files={"file": ("archive.zip", io.BytesIO(zip_bytes), "application/zip")},
    )
    assert resp.status_code == 422
    assert "No JPEG" in resp.json()["detail"]


def test_create_batch_success(client, mock_repo):
    zip_bytes = _make_zip({"label.jpg": b"fake-jpeg", "cover.png": b"fake-png"})
    with (
        patch("routes.batch.save_upload_image", return_value="/api/uploads/x.jpg"),
        patch("routes.batch._process_batch"),
    ):
        resp = client.post(
            "/api/batch",
            files={"file": ("batch.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_images"] == 2
    assert "batch_id" in data
    assert mock_repo.save_batch.call_count == 1
    assert mock_repo.save_item.call_count == 2
    # Verify user_id is set on batch
    batch_arg = mock_repo.save_batch.call_args[0][0]
    assert batch_arg.user_id == TEST_USER_ID


def test_create_batch_skips_macosx_entries(client, mock_repo):
    zip_bytes = _make_zip({
        "label.jpg": b"ok",
        "__MACOSX/label.jpg": b"skip",
        "subdir/": b"",
    })
    with (
        patch("routes.batch.save_upload_image", return_value="/api/uploads/x.jpg"),
        patch("routes.batch._process_batch"),
    ):
        resp = client.post(
            "/api/batch",
            files={"file": ("batch.zip", io.BytesIO(zip_bytes), "application/zip")},
        )
    assert resp.status_code == 200
    assert resp.json()["total_images"] == 1


# ── GET /api/batch/{batch_id} ───────────────────────────────────────────────


def test_get_batch_found(client, mock_repo):
    batch = Batch(batch_id="b1", user_id=TEST_USER_ID, total_images=3)
    mock_repo.find_batch.return_value = batch
    resp = client.get("/api/batch/b1")
    assert resp.status_code == 200
    assert resp.json()["batch_id"] == "b1"
    mock_repo.find_batch.assert_called_once_with("b1", TEST_USER_ID)


def test_get_batch_not_found(client, mock_repo):
    mock_repo.find_batch.return_value = None
    resp = client.get("/api/batch/missing")
    assert resp.status_code == 404


# ── GET /api/batch/{batch_id}/items ──────────────────────────────────────────


def test_get_batch_items(client, mock_repo):
    items = [
        BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID, image_filename="a.jpg"),
        BatchItem(item_id="i2", batch_id="b1", user_id=TEST_USER_ID, image_filename="b.jpg"),
    ]
    mock_repo.find_items_by_batch.return_value = items
    resp = client.get("/api/batch/b1/items")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_batch_items_with_review_filter(client, mock_repo):
    mock_repo.find_items_by_batch.return_value = []
    resp = client.get("/api/batch/b1/items?review_status=accepted")
    assert resp.status_code == 200
    mock_repo.find_items_by_batch.assert_called_once_with("b1", TEST_USER_ID, review_status="accepted")


# ── PATCH /api/batch/{batch_id}/items/{item_id} ─────────────────────────────


def test_review_batch_item_success(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID)
    resp = client.patch(
        "/api/batch/b1/items/i1",
        json={"review_status": "accepted", "accepted_release_id": 123},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    mock_repo.update_item_review.assert_called_once_with("i1", "accepted", 123)


def test_review_batch_item_not_found(client, mock_repo):
    mock_repo.find_item.return_value = None
    resp = client.patch(
        "/api/batch/b1/items/i1",
        json={"review_status": "accepted"},
    )
    assert resp.status_code == 404


def test_review_batch_item_wrong_batch(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(item_id="i1", batch_id="other", user_id=TEST_USER_ID)
    resp = client.patch(
        "/api/batch/b1/items/i1",
        json={"review_status": "accepted"},
    )
    assert resp.status_code == 404


# ── GET /api/review/items ────────────────────────────────────────────────────


def test_get_all_review_items(client, mock_repo):
    mock_repo.find_all_items.return_value = [
        BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID),
    ]
    resp = client.get("/api/review/items")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_all_review_items_filtered(client, mock_repo):
    mock_repo.find_all_items.return_value = []
    resp = client.get("/api/review/items?review_status=skipped")
    assert resp.status_code == 200
    mock_repo.find_all_items.assert_called_once_with(TEST_USER_ID, review_status="skipped", status=None)


def test_get_all_review_items_filtered_by_status(client, mock_repo):
    mock_repo.find_all_items.return_value = []
    resp = client.get("/api/review/items?status=error")
    assert resp.status_code == 200
    mock_repo.find_all_items.assert_called_once_with(TEST_USER_ID, review_status=None, status="error")


def test_get_all_review_items_filtered_by_both(client, mock_repo):
    mock_repo.find_all_items.return_value = []
    resp = client.get("/api/review/items?review_status=wrong&status=completed")
    assert resp.status_code == 200
    mock_repo.find_all_items.assert_called_once_with(TEST_USER_ID, review_status="wrong", status="completed")


# ── PATCH /api/review/items/{item_id} ───────────────────────────────────────


def test_review_item_success(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID)
    resp = client.patch(
        "/api/review/items/i1",
        json={"review_status": "skipped"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_review_item_not_found(client, mock_repo):
    mock_repo.find_item.return_value = None
    resp = client.patch(
        "/api/review/items/i1",
        json={"review_status": "accepted"},
    )
    assert resp.status_code == 404


# ── POST /api/review/items/{item_id}/undo ───────────────────────────────────


def test_undo_review_success(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID)
    resp = client.post("/api/review/items/i1/undo")
    assert resp.status_code == 200
    mock_repo.update_item_review.assert_called_once_with("i1", "unreviewed", None)


def test_undo_review_not_found(client, mock_repo):
    mock_repo.find_item.return_value = None
    resp = client.post("/api/review/items/i1/undo")
    assert resp.status_code == 404


# ── _process_batch (background task) ────────────────────────────────────────


def _make_fake_response():
    """Create a minimal mock SearchResponse."""
    mock_resp = MagicMock()
    mock_resp.label_data.model_dump.return_value = {"albums": ["Test"]}
    result = MagicMock()
    result.title = "Artist - Album"
    result.model_dump.return_value = {"title": "Artist - Album"}
    mock_resp.results = [result]
    mock_resp.strategy = "default"
    mock_resp.debug = None
    mock_resp.total = 1
    return mock_resp


def test_process_batch_success():
    repo = MagicMock()
    fake_resp = _make_fake_response()
    items = [("item1", b"jpeg-data", "image/jpeg")]
    filenames = {"item1": "label.jpg"}

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", return_value=fake_resp),
        patch("routes.batch.time.sleep"),
    ):
        _process_batch("b1", items, filenames, user_id="u1")

    repo.update_item_status.assert_called_once_with("item1", "processing")
    repo.update_item_completed.assert_called_once()
    repo.increment_batch_processed.assert_called_once_with("b1")
    repo.update_batch_status.assert_called_once_with("b1", "completed")
    repo.save_search_record.assert_called_once()


def test_process_batch_item_failure():
    repo = MagicMock()
    items = [("item1", b"jpeg-data", "image/jpeg")]
    filenames = {"item1": "label.jpg"}

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", side_effect=RuntimeError("boom")),
        patch("routes.batch.time.sleep"),
    ):
        _process_batch("b1", items, filenames, user_id="u1")

    repo.update_item_error.assert_called_once_with("item1", "Search pipeline error. Check server logs for details.")
    repo.increment_batch_failed.assert_called_once_with("b1")
    repo.update_batch_status.assert_called_once_with("b1", "completed")


def test_process_batch_telemetry_save_failure():
    """Telemetry save failure should not break the batch."""
    repo = MagicMock()
    repo.save_search_record.side_effect = RuntimeError("db down")
    fake_resp = _make_fake_response()
    items = [("item1", b"jpeg-data", "image/jpeg")]
    filenames = {"item1": "label.jpg"}

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", return_value=fake_resp),
        patch("routes.batch.time.sleep"),
    ):
        _process_batch("b1", items, filenames, user_id="u1")

    # Batch should still complete despite telemetry failure
    repo.update_batch_status.assert_called_once_with("b1", "completed")


def test_process_batch_validation_error():
    """ValueError should store the original message (our own validation)."""
    repo = MagicMock()
    items = [("item1", b"jpeg-data", "image/jpeg")]
    filenames = {"item1": "label.jpg"}

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", side_effect=ValueError("Could not extract album")),
        patch("routes.batch.time.sleep"),
    ):
        _process_batch("b1", items, filenames, user_id="u1")

    repo.update_item_error.assert_called_once_with("item1", "Could not extract album")
    repo.increment_batch_failed.assert_called_once_with("b1")


# ── Retry / reprocess ──────────────────────────────────────────────────────


def test_retry_item_success(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(
        item_id="i1", batch_id="b1", user_id=TEST_USER_ID, image_url="/api/uploads/test-user-123/i1.jpg",
    )
    with (
        patch("routes.batch.UPLOADS_DIR") as mock_dir,
        patch("routes.batch.invalidate_cache"),
        patch("routes.batch.get_repo", return_value=mock_repo),
        patch("routes.batch.process_single_image", return_value=_make_fake_response()),
    ):
        mock_path = MagicMock()
        mock_path.is_file.return_value = True
        mock_path.read_bytes.return_value = b"jpeg-data"
        mock_path.suffix = ".jpg"
        mock_dir.__truediv__ = MagicMock(return_value=mock_path)

        resp = client.post("/api/review/items/i1/retry")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    # Route sets "pending", then background task sets "processing"
    assert mock_repo.update_item_status.call_args_list == [
        (("i1", "pending"),),
        (("i1", "processing"),),
    ]


def test_retry_item_not_found(client, mock_repo):
    mock_repo.find_item.return_value = None
    resp = client.post("/api/review/items/i1/retry")
    assert resp.status_code == 404


def test_retry_item_no_image(client, mock_repo):
    mock_repo.find_item.return_value = BatchItem(item_id="i1", batch_id="b1", user_id=TEST_USER_ID, image_url=None)
    resp = client.post("/api/review/items/i1/retry")
    assert resp.status_code == 422


def test_reprocess_item_success():
    repo = MagicMock()
    fake_resp = _make_fake_response()

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", return_value=fake_resp),
    ):
        _reprocess_item("i1", b"jpeg-data", "image/jpeg", batch_id="b1", user_id="u1")

    repo.update_item_status.assert_called_once_with("i1", "processing")
    repo.update_item_completed.assert_called_once()


def test_reprocess_item_validation_error():
    repo = MagicMock()

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", side_effect=ValueError("bad label")),
    ):
        _reprocess_item("i1", b"jpeg-data", "image/jpeg", user_id="u1")

    repo.update_item_error.assert_called_once_with("i1", "bad label")


def test_reprocess_item_unexpected_error():
    repo = MagicMock()

    with (
        patch("routes.batch.get_repo", return_value=repo),
        patch("routes.batch.process_single_image", side_effect=RuntimeError("boom")),
    ):
        _reprocess_item("i1", b"jpeg-data", "image/jpeg", user_id="u1")

    repo.update_item_error.assert_called_once_with("i1", "Search pipeline error. Check server logs for details.")
