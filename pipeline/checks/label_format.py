"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


CHECK = "label_format"


def run(ds, cfg):
    # Mọi ngưỡng lấy từ cfg (không viết cứng): test dùng cfg khác configs/pipeline.yaml.
    p = cfg["label_format"]
    tol, min_px = p["overflow_tol"], p["min_box_px"]
    max_frac, dup_iou = p["max_box_frac"], p["dup_box_iou"]
    n_cls = len(ds.classes)                      # id hợp lệ: 0..n_cls-1

    issues = []
    for lf in ds.label_files():                  # CHỈ ĐỌC file nhãn, không sửa/xoá gì
        stem = lf.stem
        size = ds.image_size(stem)               # (W, H) px, hoặc None nếu ảnh hỏng/không có ảnh
        seen = []                                # các box hợp lệ ở dòng TRƯỚC: (lớp, (cx, cy, w, h))

        # read_label_lines bỏ dòng trống nhưng GIỮ số dòng gốc (đếm từ 1)
        for no, text in ds.read_label_lines(stem) or []:
            def add(sev, code, msg, **extra):
                issues.append(Issue(CHECK, sev, code, stem, msg, no, extra))

            # 1) Đúng 5 cột số? Dòng thiếu cột / 'nan' / chữ -> ValueError, không để script chết
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", f"dòng sai định dạng ({e}): {text.strip()!r}")
                continue                         # dòng hỏng: không kiểm hình học nữa

            # 2) ID lớp nằm trong 0..n_cls-1?
            if not 0 <= c < n_cls:
                add(ERROR, "BAD_CLASS_ID", f"id lớp {c} ngoài 0..{n_cls - 1}")
                continue

            # 3) Box có diện tích?
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", f"box rộng/cao bằng 0 (w={w}, h={h})")
                continue

            # 4) Tràn ảnh: mức tràn lớn nhất trong 4 mép (trái, phải, trên, dưới)
            overflow = max(0 - (x - w / 2), (x + w / 2) - 1, 0 - (y - h / 2), (y + h / 2) - 1)
            if overflow > tol:
                add(ERROR, "BOX_OUT_OF_IMAGE", f"box tràn ảnh {overflow:.4f} (> {tol})",
                    overflow=round(overflow, 6))
                # KHÔNG continue: dòng vẫn parse được, kiểm tiếp lặp/nhỏ/to

            # 5) Box lặp: cùng lớp với một dòng TRƯỚC ĐÓ và IoU > dup_box_iou -> báo ở dòng sau
            box = (x, y, w, h)
            best = max((iou_xywh(box, b) for cc, b in seen if cc == c), default=0.0)
            if best > dup_iou:
                add(ERROR, "DUP_BOX", f"trùng box cùng lớp ở dòng trước (IoU={best:.3f})", iou=round(best, 4))
            seen.append((c, box))

            # 6) Box quá nhỏ (cảnh báo): cạnh ngắn tính theo px; bỏ qua nếu không đọc được kích thước ảnh
            if size:
                W, H = size
                short = min(w * W, h * H)
                if short < min_px:
                    add(WARN, "BOX_TINY", f"cạnh ngắn {short:.1f}px < {min_px}px", short_px=round(short, 2))

            # 7) Box quá to (cảnh báo): diện tích tỉ lệ > max_box_frac
            if w * h > max_frac:
                add(WARN, "BOX_HUGE", f"box chiếm {w * h:.3f} diện tích ảnh (> {max_frac})", frac=round(w * h, 4))

    return issues
