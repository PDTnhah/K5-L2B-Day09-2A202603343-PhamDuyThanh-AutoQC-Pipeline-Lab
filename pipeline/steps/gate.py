"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from collections import Counter

from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    # Chỉ ĐỌC issues và trả dict, không đụng tới file nào. Ngưỡng lấy từ cfg, không viết cứng.
    hold_at = cfg["gate"]["warn_ratio_hold"]
    stems = set(image_stems)                       # set để tra "ảnh có trong lô không" cho nhanh
    reviewed = set(reviewed or ())
    n_images = len(stems)

    # 1) Lỗi bắt buộc: đếm TẤT CẢ (kể cả lỗi ở data.yaml / <dataset>).
    #    KHÔNG lọc theo `reviewed`: người đã xem ảnh cũng không xoá được lỗi bắt buộc.
    errors = [i for i in issues if i.severity == ERROR]
    n_errors = len(errors)

    # 2) Ảnh còn cảnh báo: đếm số ẢNH khác nhau (set), không đếm số issue.
    #    Bỏ cảnh báo cấp dataset (image không phải ảnh trong lô) và ảnh người đã duyệt.
    warn_images = {i.image for i in issues
                   if i.severity == WARN and i.image in stems and i.image not in reviewed}
    n_warn_images = len(warn_images)

    # 3) Tỉ lệ = số ảnh còn cảnh báo / tổng số ảnh; lô rỗng thì 0 (tránh chia cho 0).
    #    Quyết định trên CÙNG con số in ra báo cáo (đã làm tròn) để báo cáo và kết luận không lệch nhau.
    warn_ratio = round(n_warn_images / n_images, 4) if n_images else 0

    # 4) Cây quyết định: lỗi bắt buộc -> Rework; tỉ lệ cảnh báo >= ngưỡng -> Hold; còn lại -> Release.
    reasons = []
    if n_errors:
        decision = "Rework"
        top = ", ".join(f"{code}×{n}" for code, n in Counter(i.code for i in errors).most_common(5))
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (ERROR) chưa sửa: {top}.")
        reasons.append("Lỗi bắt buộc chặn pipeline, kể cả ở ảnh người đã duyệt.")
    elif warn_ratio >= hold_at:
        decision = "Hold"
        reasons.append(f"Không còn lỗi bắt buộc, nhưng {n_warn_images}/{n_images} ảnh ({warn_ratio:.1%}) "
                       f"còn cảnh báo chưa người duyệt ≥ ngưỡng {hold_at:.0%}.")
    else:
        decision = "Release"
        reasons.append(f"Không còn lỗi bắt buộc; {n_warn_images}/{n_images} ảnh ({warn_ratio:.1%}) "
                       f"còn cảnh báo chưa duyệt < ngưỡng {hold_at:.0%}.")
    if reviewed:
        reasons.append(f"Đã bỏ qua cảnh báo của {len(reviewed & stems)} ảnh người đã duyệt.")

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
