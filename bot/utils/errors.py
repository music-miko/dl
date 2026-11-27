# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.errors import AccessTokenExpired, AccessTokenInvalid, Unauthorized

token_errors = (AccessTokenInvalid, AccessTokenExpired, Unauthorized)


def describe_error(e: Exception) -> str:
    code = getattr(e, "ID", None) or getattr(e, "MESSAGE", None)
    return str(code) if code else f"{type(e).__name__}: {e}"
