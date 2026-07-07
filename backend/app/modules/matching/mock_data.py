"""Mock data + demo chạy thử engine ghép phòng.

Chạy:  python -m app.modules.matching.mock_data

Các persona được thiết kế có chủ đích để kiểm chứng thuật toán:
- Bình  : gần giống hệt An            -> kỳ vọng TOP 1
- Chi   : khá giống, lệch giờ ngủ nhẹ -> kỳ vọng top cao
- Dũng  : HÚT THUỐC (An không nhận)   -> kỳ vọng BỊ LOẠI (hard filter)
- Hà    : nuôi mèo (An OK thú cưng)   -> vẫn được xếp hạng
- Khang : cú đêm + tiệc tùng          -> kỳ vọng điểm thấp
- Linh  : ngăn nắp nhưng ngủ rất sớm  -> điểm trung bình
- Minh  : không nhận người WFH... không, Minh KHÔNG chấp nhận thú cưng
          nhưng An không nuôi -> vẫn qua filter, điểm tùy thói quen
- Ngọc  : budget cao gấp đôi, khách khứa nhiều -> điểm thấp
"""

from uuid import UUID

from app.modules.matching.engine import find_top_roommates
from app.modules.matching.schemas import HabitProfile


def _uid(n: int) -> UUID:
    return UUID(int=n)


# Người đang tìm phòng: sinh viên năm cuối, ngủ ~23h30, sạch sẽ,
# không hút thuốc, không nuôi thú cưng nhưng không ngại thú cưng.
SEEKER = HabitProfile(
    user_id=_uid(1),
    full_name="An (seeker)",
    bedtime_hour=23.5,
    tidiness=4,
    noise_tolerance=2,
    cooking_per_week=5,
    guests_per_month=2,
    work_from_home=False,
    is_smoker=False,
    has_pet=False,
    budget_vnd=3_500_000,
    accepts_smoker=False,
    accepts_pet=True,
)

CANDIDATES: list[HabitProfile] = [
    HabitProfile(
        user_id=_uid(2), full_name="Bình",
        bedtime_hour=23.0, tidiness=4, noise_tolerance=2,
        cooking_per_week=6, guests_per_month=2, work_from_home=False,
        is_smoker=False, has_pet=False, budget_vnd=3_600_000,
    ),
    HabitProfile(
        user_id=_uid(3), full_name="Chi",
        bedtime_hour=24.5, tidiness=5, noise_tolerance=3,
        cooking_per_week=4, guests_per_month=3, work_from_home=False,
        is_smoker=False, has_pet=False, budget_vnd=3_200_000,
    ),
    HabitProfile(
        user_id=_uid(4), full_name="Dũng (hút thuốc)",
        bedtime_hour=23.5, tidiness=4, noise_tolerance=2,
        cooking_per_week=5, guests_per_month=2, work_from_home=False,
        is_smoker=True, has_pet=False, budget_vnd=3_500_000,
    ),
    HabitProfile(
        user_id=_uid(5), full_name="Hà (nuôi mèo)",
        bedtime_hour=23.0, tidiness=4, noise_tolerance=2,
        cooking_per_week=5, guests_per_month=1, work_from_home=True,
        is_smoker=False, has_pet=True, budget_vnd=3_800_000,
    ),
    HabitProfile(
        user_id=_uid(6), full_name="Khang (cú đêm, tiệc tùng)",
        bedtime_hour=27.0, tidiness=2, noise_tolerance=5,
        cooking_per_week=0, guests_per_month=12, work_from_home=False,
        is_smoker=False, has_pet=False, budget_vnd=4_500_000,
    ),
    HabitProfile(
        user_id=_uid(7), full_name="Linh (ngủ sớm)",
        bedtime_hour=21.5, tidiness=5, noise_tolerance=1,
        cooking_per_week=7, guests_per_month=0, work_from_home=True,
        is_smoker=False, has_pet=False, budget_vnd=3_000_000,
    ),
    HabitProfile(
        user_id=_uid(8), full_name="Minh (không nhận thú cưng)",
        bedtime_hour=24.0, tidiness=3, noise_tolerance=3,
        cooking_per_week=3, guests_per_month=4, work_from_home=False,
        is_smoker=False, has_pet=False, budget_vnd=3_400_000,
        accepts_pet=False,
    ),
    HabitProfile(
        user_id=_uid(9), full_name="Ngọc (budget cao, đông khách)",
        bedtime_hour=25.0, tidiness=3, noise_tolerance=4,
        cooking_per_week=1, guests_per_month=10, work_from_home=False,
        is_smoker=False, has_pet=False, budget_vnd=7_000_000,
    ),
]


def main() -> None:
    matches = find_top_roommates(SEEKER, CANDIDATES, top_k=5)

    print(f"\nTop {len(matches)} gợi ý ghép phòng cho {SEEKER.full_name}:")
    print("-" * 56)
    for rank, match in enumerate(matches, start=1):
        print(f"  #{rank}  {match.profile.full_name:<32} score={match.score:.4f}")
    print("-" * 56)

    ranked_names = {m.profile.full_name for m in matches}
    assert "Dũng (hút thuốc)" not in ranked_names, "Hard filter phải loại Dũng!"
    assert matches[0].profile.full_name == "Bình", "Bình phải là top 1!"
    print("Kiểm chứng OK: Dũng bị loại bởi hard filter, Bình đứng top 1.\n")


if __name__ == "__main__":
    main()
