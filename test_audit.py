"""Reproducible local review of Werkzeug static-file boundaries.

All fixtures are synthetic. Werkzeug's in-process WSGI client is used: no
listening socket, external target, or real credential is involved.
"""

from pathlib import Path

import pytest
from werkzeug.middleware.shared_data import SharedDataMiddleware
from werkzeug.test import Client
from werkzeug.wrappers import Request
from werkzeug.wrappers import Response

CSS = b"body { color: navy; }\n"
SQL = b"-- SYNTHETIC BACKUP: no real customer data\n"
ENV = b"DEMO_TOKEN=fictional-not-a-credential\n"
OUTSIDE = b"SYNTHETIC OUTSIDE FILE\n"


@Request.application
def fallback(request):
    if request.path == "/":
        return Response("application homepage", status=200)
    return Response("not found", status=404)


@pytest.fixture
def tree(tmp_path):
    public = tmp_path / "public"
    private = tmp_path / "private"
    clean = tmp_path / "clean-public"
    for directory in (public, private, clean):
        directory.mkdir()
    (public / "nested").mkdir()
    (public / "site.css").write_bytes(CSS)
    (public / "backup.sql").write_bytes(SQL)
    (public / "nested" / "backup.sql").write_bytes(SQL)
    (public / "backup.SQL").write_bytes(SQL)
    (public / ".env").write_bytes(ENV)
    (private / "outside.txt").write_bytes(OUTSIDE)
    (private / "archive.sql").write_bytes(SQL)
    (public / "linked.txt").symlink_to(private / "outside.txt")
    (public / "linked-dir").symlink_to(private, target_is_directory=True)
    (clean / "site.css").write_bytes(CSS)
    return public, private, clean


def client(directory: Path, disallow=None):
    return Client(
        SharedDataMiddleware(fallback, {"/static": str(directory)}, disallow=disallow),
        Response,
    )


def check(client_, path, status, body=None, method="GET"):
    with client_.open(path, method=method) as response:
        assert response.status_code == status
        if body is not None:
            assert response.data == body
        if status == 404:
            assert response.data == b"not found"
        return response.content_length


@pytest.mark.parametrize(
    "path,status,body",
    [
        ("/static/site.css", 200, CSS),
        ("/static/missing.txt", 404, None),
        ("/static/backup.sql", 200, SQL),
        ("/static/nested/backup.sql", 200, SQL),
        ("/static/.env", 200, ENV),
        ("/static/linked.txt", 200, OUTSIDE),
        ("/static/linked-dir/archive.sql", 200, SQL),
    ],
)
def test_baseline_content(tree, path, status, body):
    check(client(tree[0]), path, status, body)


@pytest.mark.parametrize(
    "path",
    [
        "/static/../private/outside.txt",
        "/static/%2e%2e/private/outside.txt",
        "/static/%2e%2e%2fprivate%2foutside.txt",
        "/static/nested/../../private/outside.txt",
        "/static/%252e%252e/private/outside.txt",
        "/static/..%5cprivate%5coutside.txt",
        "/static//etc/passwd",
        "/static-other/site.css",
    ],
)
def test_path_boundary(tree, path):
    # This is Linux/WSL behavior, not a claim about native Windows or proxies.
    check(client(tree[0]), path, 404)


def test_head_exposure(tree):
    assert check(client(tree[0]), "/static/backup.sql", 200, b"", "HEAD") == len(SQL)


@pytest.mark.parametrize(
    "pattern,path,status,body",
    [
        ("*.sql", "/static/backup.sql", 404, None),
        ("*.sql", "/static/nested/backup.sql", 404, None),
        ("*.sql", "/static/backup.SQL", 200, SQL),
        ("*.sql", "/static/.env", 200, ENV),
        ("nested/*", "/static/nested/backup.sql", 200, SQL),
    ],
)
def test_disallow_scope(tree, pattern, path, status, body):
    # disallow receives the basename, not the full relative path.
    check(client(tree[0], pattern), path, status, body)


def test_move_backup_outside_public_root(tree):
    public, private, _ = tree
    public.joinpath("backup.sql").rename(private / "moved-backup.sql")
    app = client(public)
    check(app, "/static/backup.sql", 404)
    check(app, "/static/site.css", 200, CSS)
    check(app, "/", 200, b"application homepage")


def test_moving_backup_is_insufficient_with_existing_symlink(tree):
    public, private, _ = tree
    public.joinpath("backup.sql").rename(private / "moved-backup.sql")
    app = client(public)
    check(app, "/static/backup.sql", 404)
    check(app, "/static/linked-dir/moved-backup.sql", 200, SQL)


@pytest.mark.parametrize(
    "path,status,body",
    [
        ("/", 200, b"application homepage"),
        ("/static/site.css", 200, CSS),
        ("/static/backup.sql", 404, None),
        ("/static/nested/backup.sql", 404, None),
        ("/static/backup.SQL", 404, None),
        ("/static/.env", 404, None),
        ("/static/linked.txt", 404, None),
        ("/static/linked-dir/archive.sql", 404, None),
        ("/static/../private/outside.txt", 404, None),
    ],
)
def test_clean_asset_root(tree, path, status, body):
    # The clean root contains only an explicitly chosen ordinary CSS file.
    check(client(tree[2]), path, status, body)
