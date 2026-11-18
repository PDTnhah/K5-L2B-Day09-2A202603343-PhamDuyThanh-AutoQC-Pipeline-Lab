"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}       # dòng hỏng -> xoá dòng
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}                                         # box tràn -> cắt về [0,1]
REMOVE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}                 # + mọi DUP_IMAGE_* -> xoá ảnh


def _is_remove(code):
    return code in REMOVE_CODES or code.startswith("DUP_IMAGE_")


def _rec(image, line, action, before, after):
    """Một dòng của 03_fixes.csv: bằng chứng máy đã sửa gì (trước -> sau)."""
    return {"image": image, "line": line, "action": action, "before": before, "after": after}


def fix(ds, issues, cfg):
    # Chỉ xử lý lỗi bắt buộc; cảnh báo (WARN) là việc của người, KHÔNG đụng tới.
    errors = [i for i in issues if i.severity == ERROR]
    fixes = []

    # ---- 1) Lỗi cấp ẢNH: xoá ảnh + nhãn khỏi `ds` (bản làm việc, KHÔNG phải data/raw)
    removed = set()
    for i in errors:
        if not _is_remove(i.code) or i.image in removed:
            continue                                   # mỗi ảnh chỉ xoá + ghi log 1 lần
        removed.add(i.image)                           # nhớ lại để bỏ qua issue dòng của ảnh này
        img, lab = ds.image_path(i.image), ds.label_path(i.image)
        if img is None and not lab.exists():
            continue                                   # đã xoá từ trước: bỏ qua êm (idempotent)
        if img is not None:
            img.unlink()
        if lab.exists():
            lab.unlink()
        fixes.append(_rec(i.image, None, "remove_image",
                          img.name if img is not None else "(không có ảnh)", f"(đã xoá: {i.code})"))

    # ---- 2) data.yaml sai tên lớp: ghi lại `names` đúng cfg["classes"] (một lần dù có nhiều issue)
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        data = {}
        if ds.yaml_path.exists():
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        before = data.get("names")
        want = {k: name for k, name in enumerate(cfg["classes"])}     # giữ kiểu dict `0: car` như file gốc
        if ds.yaml_names() != want:                    # đã đúng rồi thì không ghi (idempotent)
            data["names"] = want
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            fixes.append(_rec("data.yaml", None, "rename_classes", str(before), str(want)))

    # ---- 3) Ảnh chưa có file nhãn: KHÔNG bịa nhãn, KHÔNG tạo file rỗng (rỗng = "ảnh nền") -> chuyển người gán
    seen_missing = set()
    for i in errors:
        if i.code != "MISSING_LABEL_FILE" or i.image in removed or i.image in seen_missing:
            continue
        seen_missing.add(i.image)
        if not ds.label_path(i.image).exists():        # vẫn còn thiếu thật thì mới ghi
            fixes.append(_rec(i.image, None, "needs_label", "(không có file)", "chuyển người gán"))

    # ---- 4) Lỗi DÒNG: gom theo file -> {số dòng GỐC: {các mã lỗi}}, sửa xong ghi file MỘT lần
    by_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and i.code in DROP_CODES | CLIP_CODES:
            by_file[i.image][int(i.line)].add(i.code)

    for stem in sorted(by_file):
        path = ds.label_path(stem)
        if stem in removed or not path.exists():
            continue                                   # ảnh vừa bị xoá / không còn nhãn: bỏ qua êm
        todo = by_file[stem]
        # Đánh số y hệt ds.read_label_lines: enumerate từ 1 trên MỌI dòng (kể cả dòng trống)
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        out, changed = [], False
        for no, text in enumerate(raw_lines, 1):
            codes = todo.get(no)
            if not codes:
                out.append(text)                       # dòng không lỗi (hoặc dòng trống): giữ nguyên
                continue
            changed = True
            if codes & DROP_CODES:
                # Xoá dòng THẮNG: một dòng dính 2 lỗi (vd. tràn + lặp) chỉ ghi 1 fix drop_line, không clip
                fixes.append(_rec(stem, no, "drop_line", text.strip(), f"(xoá: {'+'.join(sorted(codes))})"))
                continue
            # Chỉ còn BOX_OUT_OF_IMAGE: cắt 4 mép về [0,1], giữ nguyên lớp
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError:
                # issue cũ không khớp nội dung file: KHÔNG đoán, giữ nguyên dòng; vòng QC sau sẽ báo BAD_FORMAT
                out.append(text)
                continue
            x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
            y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
            nw, nh = x2 - x1, y2 - y1
            if nw <= 0 or nh <= 0:
                # box nằm hẳn ngoài ảnh: cắt xong không còn diện tích -> xoá dòng thay vì ghi box rỗng
                fixes.append(_rec(stem, no, "drop_line", text.strip(), "(xoá: box nằm ngoài ảnh, cắt xong rỗng)"))
                continue
            new = f"{c} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"
            out.append(new)
            fixes.append(_rec(stem, no, "clip_box", text.strip(), new))
        if changed:
            path.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")   # ghi lại MỘT lần cho cả file

    return fixes
