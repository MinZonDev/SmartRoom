"""Unit tests cho auth security — bcrypt + JWT."""

from uuid import uuid4

import jwt as pyjwt
import pytest

from app.modules.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


class TestPassword:
    def test_hash_va_verify_dung(self) -> None:
        h = hash_password("mat-khau-bi-mat")
        assert h != "mat-khau-bi-mat"
        assert verify_password("mat-khau-bi-mat", h) is True

    def test_sai_mat_khau(self) -> None:
        h = hash_password("dung")
        assert verify_password("sai", h) is False

    def test_dummy_hash_khi_user_khong_ton_tai(self) -> None:
        """verify với hash=None (chống timing attack) luôn trả False."""
        assert verify_password("bat-ky", None) is False

    def test_hai_lan_hash_khac_nhau(self) -> None:
        """bcrypt salt ngẫu nhiên — cùng mật khẩu ra hash khác nhau."""
        assert hash_password("x" * 8) != hash_password("x" * 8)


class TestJWT:
    def test_roundtrip(self) -> None:
        user_id = uuid4()
        payload = decode_access_token(create_access_token(user_id))
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_token_gia_mao_bi_tu_choi(self) -> None:
        token = create_access_token(uuid4())
        tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_token_ky_bang_secret_khac_bi_tu_choi(self) -> None:
        forged = pyjwt.encode(
            {"sub": str(uuid4()), "type": "access"}, "secret-khac", algorithm="HS256"
        )
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(forged)

    def test_refresh_token_roundtrip(self) -> None:
        user_id = uuid4()
        payload = decode_refresh_token(create_refresh_token(user_id))
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_access_khong_dung_duoc_lam_refresh(self) -> None:
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_refresh_token(create_access_token(uuid4()))

    def test_refresh_khong_dung_duoc_lam_access(self) -> None:
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(create_refresh_token(uuid4()))

    def test_sai_type_bi_tu_choi(self) -> None:
        """Token type != access (vd refresh sau này) không dùng được làm access."""
        from app.core.config import get_settings

        settings = get_settings()
        refresh_like = pyjwt.encode(
            {"sub": str(uuid4()), "type": "refresh"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(refresh_like)
