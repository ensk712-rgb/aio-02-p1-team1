"""관리자 Trace 조회용 최소 Bearer 토큰 검증."""

from __future__ import annotations

import secrets


class AdminAuthenticationError(ValueError):
    """관리자 인증에 실패했음을 값 노출 없이 나타낸다."""


def verify_admin_token(authorization: str | None, admin_token: str) -> None:
    if not admin_token:
        raise AdminAuthenticationError("관리자 조회 기능이 설정되지 않았습니다.")
    scheme, separator, supplied = (authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not supplied:
        raise AdminAuthenticationError("관리자 인증이 필요합니다.")
    if not secrets.compare_digest(supplied, admin_token):
        raise AdminAuthenticationError("관리자 인증에 실패했습니다.")
