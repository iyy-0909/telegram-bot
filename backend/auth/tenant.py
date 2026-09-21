from contextlib import contextmanager
from contextvars import ContextVar


_tenant_user_id = ContextVar("tenant_user_id", default=None)
_tenant_is_admin = ContextVar("tenant_is_admin", default=False)


def current_tenant_user_id():
    value = _tenant_user_id.get()
    return int(value) if value not in (None, "") else None


def current_tenant_is_admin():
    return bool(_tenant_is_admin.get())


def bind_tenant(user_id=None, *, is_admin=False):
    normalized_user_id = int(user_id) if user_id not in (None, "", 0, "0") else None
    return (
        _tenant_user_id.set(normalized_user_id),
        _tenant_is_admin.set(bool(is_admin)),
    )


def reset_tenant(tokens):
    user_token, admin_token = tokens
    _tenant_is_admin.reset(admin_token)
    _tenant_user_id.reset(user_token)


@contextmanager
def tenant_scope(user_id=None, *, is_admin=False):
    tokens = bind_tenant(user_id, is_admin=is_admin)
    try:
        yield
    finally:
        reset_tenant(tokens)
