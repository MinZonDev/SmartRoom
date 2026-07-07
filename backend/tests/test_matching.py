"""Unit tests cho engine ghép phòng — dùng bộ persona trong mock_data."""

from app.modules.matching.engine import RoommateMatchingEngine, find_top_roommates
from app.modules.matching.mock_data import CANDIDATES, SEEKER


class TestHardFilters:
    def test_nguoi_hut_thuoc_bi_loai(self) -> None:
        """Dũng giống An 100% về thói quen nhưng hút thuốc — phải bị loại."""
        matches = find_top_roommates(SEEKER, CANDIDATES, top_k=len(CANDIDATES))
        names = {m.profile.full_name for m in matches}
        assert "Dũng (hút thuốc)" not in names

    def test_seeker_khong_tu_match_chinh_minh(self) -> None:
        matches = find_top_roommates(SEEKER, [SEEKER, *CANDIDATES], top_k=20)
        assert all(m.profile.user_id != SEEKER.user_id for m in matches)

    def test_khong_co_ung_vien(self) -> None:
        assert find_top_roommates(SEEKER, [], top_k=5) == []


class TestRanking:
    def test_profile_giong_nhat_dung_top1(self) -> None:
        matches = find_top_roommates(SEEKER, CANDIDATES, top_k=5)
        assert matches[0].profile.full_name == "Bình"

    def test_diem_giam_dan_va_trong_khoang_0_1(self) -> None:
        matches = find_top_roommates(SEEKER, CANDIDATES, top_k=5)
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)
        assert all(0 <= s <= 1 for s in scores)

    def test_top_k_gioi_han_ket_qua(self) -> None:
        assert len(find_top_roommates(SEEKER, CANDIDATES, top_k=2)) == 2

    def test_trong_so_tuy_chinh(self) -> None:
        """Engine chạy được với bộ trọng số khác (chỉ 1 feature)."""
        engine = RoommateMatchingEngine(feature_weights={"bedtime_hour": 1.0})
        matches = engine.find_top_matches(SEEKER, CANDIDATES, top_k=3)
        assert len(matches) == 3
