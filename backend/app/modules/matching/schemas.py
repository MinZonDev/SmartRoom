"""Schemas cho module ghép phòng thông minh (Roommate Matching)."""

from uuid import UUID

from pydantic import BaseModel, Field


class HabitProfile(BaseModel):
    """Vector sở thích/thói quen của một user đang tìm phòng hoặc tìm bạn ở ghép.

    Giá trị để thô (giờ, thang điểm, VND) — engine tự chuẩn hóa khi tính toán.
    """

    user_id: UUID
    full_name: str

    # --- Thói quen (feature dùng tính similarity) ---
    bedtime_hour: float = Field(
        ge=19, le=28, description="Giờ đi ngủ; qua nửa đêm cộng 24 (vd 25.0 = 1h sáng)"
    )
    tidiness: int = Field(ge=1, le=5, description="Độ sạch sẽ ngăn nắp (5 = rất sạch)")
    noise_tolerance: int = Field(ge=1, le=5, description="Chịu được ồn (5 = thoải mái)")
    cooking_per_week: int = Field(ge=0, le=14, description="Số bữa tự nấu mỗi tuần")
    guests_per_month: int = Field(ge=0, le=30, description="Tần suất mời bạn về phòng")
    work_from_home: bool = Field(description="Làm việc tại nhà")
    is_smoker: bool
    has_pet: bool
    budget_vnd: int = Field(gt=0, description="Ngân sách thuê mỗi tháng (VND)")

    # --- Deal-breakers (hard filter, KHÔNG đưa vào vector similarity) ---
    accepts_smoker: bool = True
    accepts_pet: bool = True


class MatchResult(BaseModel):
    """Một gợi ý ghép phòng kèm điểm tương đồng."""

    profile: HabitProfile
    score: float = Field(ge=0, le=1, description="Cosine similarity sau khi áp trọng số")


class MatchRequest(BaseModel):
    """Payload cho API gợi ý (dùng khi gắn router ở giai đoạn sau)."""

    seeker: HabitProfile
    top_k: int = Field(default=5, ge=1, le=20)
