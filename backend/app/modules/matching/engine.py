"""Engine gợi ý ghép phòng — kiến trúc Filter-then-Rank.

Tầng 1 (hard filter): loại ứng viên vi phạm deal-breaker 2 chiều
                      (hút thuốc / thú cưng) trước khi chấm điểm.
Tầng 2 (rank)       : MinMax scaling -> áp trọng số -> cosine similarity
                      -> trả về top K.

Engine thuần (numpy + scikit-learn), không phụ thuộc FastAPI/DB —
unit test được độc lập và tái sử dụng trong worker/batch job.
"""

from uuid import UUID

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

from app.modules.matching.schemas import HabitProfile, MatchResult

# Trọng số nghiệp vụ: giờ giấc và độ sạch sẽ là nguồn xung đột lớn nhất
# giữa các roommate nên có trọng số cao nhất.
# TODO(matching): học trọng số từ feedback "match thành công" khi có dữ liệu.
DEFAULT_FEATURE_WEIGHTS: dict[str, float] = {
    "bedtime_hour": 2.0,
    "tidiness": 1.8,
    "guests_per_month": 1.5,
    "budget_vnd": 1.5,
    "noise_tolerance": 1.2,
    "cooking_per_week": 1.0,
    "is_smoker": 1.0,
    "has_pet": 1.0,
    "work_from_home": 0.8,
}


class RoommateMatchingEngine:
    def __init__(self, feature_weights: dict[str, float] | None = None) -> None:
        weights = feature_weights or DEFAULT_FEATURE_WEIGHTS
        self._features: list[str] = list(weights.keys())
        # Nhân feature với sqrt(w): khi cosine tính dot product,
        # mỗi feature đóng góp đúng trọng số w.
        self._sqrt_weights = np.sqrt(np.array(list(weights.values()), dtype=float))

    def find_top_matches(
        self,
        seeker: HabitProfile,
        candidates: list[HabitProfile],
        top_k: int = 5,
    ) -> list[MatchResult]:
        """Trả về tối đa top_k ứng viên hợp nhất, điểm giảm dần."""
        viable = [
            c
            for c in candidates
            if c.user_id != seeker.user_id
            and self._passes_hard_filters(seeker, c)
        ]
        if not viable:
            return []

        # Scale seeker CÙNG ma trận với candidates để chung một thang đo
        matrix = self._vectorize([seeker, *viable])
        scores = cosine_similarity(matrix[:1], matrix[1:])[0]

        ranked = sorted(
            zip(viable, scores), key=lambda pair: pair[1], reverse=True
        )
        return [
            MatchResult(profile=profile, score=round(float(score), 4))
            for profile, score in ranked[:top_k]
        ]

    @staticmethod
    def _passes_hard_filters(seeker: HabitProfile, candidate: HabitProfile) -> bool:
        """Deal-breaker phải kiểm tra 2 CHIỀU: A chấp nhận B và B chấp nhận A."""
        if candidate.is_smoker and not seeker.accepts_smoker:
            return False
        if seeker.is_smoker and not candidate.accepts_smoker:
            return False
        if candidate.has_pet and not seeker.accepts_pet:
            return False
        if seeker.has_pet and not candidate.accepts_pet:
            return False
        return True

    def _vectorize(self, profiles: list[HabitProfile]) -> np.ndarray:
        """Profile -> ma trận đã chuẩn hóa và áp trọng số.

        Scale về [0.1, 1] thay vì [0, 1]: tránh sinh vector toàn 0
        (cosine không xác định với zero vector) mà vẫn giữ nguyên thứ tự.
        """
        raw = np.array(
            [
                [float(getattr(profile, feature)) for feature in self._features]
                for profile in profiles
            ],
            dtype=float,
        )
        scaled = MinMaxScaler(feature_range=(0.1, 1.0)).fit_transform(raw)
        return scaled * self._sqrt_weights


def find_top_roommates(
    seeker: HabitProfile,
    candidates: list[HabitProfile],
    top_k: int = 5,
) -> list[MatchResult]:
    """Hàm tiện dụng cho use-case mặc định (trọng số chuẩn, top 5)."""
    return RoommateMatchingEngine().find_top_matches(seeker, candidates, top_k)


def build_profile(user_id: UUID, full_name: str, **habits: object) -> HabitProfile:
    """Helper rút gọn cho test/mock data."""
    return HabitProfile(user_id=user_id, full_name=full_name, **habits)  # type: ignore[arg-type]
