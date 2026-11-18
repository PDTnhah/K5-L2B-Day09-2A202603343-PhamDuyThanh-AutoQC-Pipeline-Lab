"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401
  

CHECK = "second_opinion"


def _name(ds, c):
    return ds.classes[c] if 0 <= c < len(ds.classes) else str(c)


def _label_boxes(ds, stem):
    """[(số dòng GỐC, lớp, (cx, cy, w, h))] của các dòng hợp lệ.
    Không dùng ds.valid_boxes vì nó làm mất số dòng (cần cho POSSIBLE_FALSE_POS)."""
    out = []
    for no, text in ds.read_label_lines(stem) or []:
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError:
            continue                                   # dòng hỏng: label_format đã báo, ở đây chỉ bỏ qua
        if 0 <= c < len(ds.classes):
            out.append((no, c, (x, y, w, h)))
    return out


def run(ds, cfg, preds=None):
    # CHỈ ĐỌC nhãn + dự đoán đã lưu; không sửa file. Mọi ngưỡng lấy từ cfg (Bước 3 sẽ calibrate `conf`).
    p = cfg["second_opinion"]
    conf_thr, min_area = p["conf"], p["min_area_px"]
    fp_conf, iou_missing = p["fp_conf"], p["iou_missing"]
    iou_match, iou_loose = p["iou_match"], p["iou_loose"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")          # yolo26l, đọc từ data/cache (không cần GPU)

    issues = []
    for img in ds.image_files():                       # thứ tự issue: theo ảnh trước
        stem = img.stem
        if stem not in preds or ds.read_label_lines(stem) is None:
            continue                                   # không có dự đoán / chưa có file nhãn: bỏ qua
        size = ds.image_size(stem)
        if size is None:
            continue                                   # ảnh không mở được: check `images` lo, ở đây không đoán
        W, H = size
        labels = _label_boxes(ds, stem)
        # Dự đoán của model: [lớp, conf, cx, cy, w, h] -> (lớp, conf, box)
        rows = [(int(r[0]), float(r[1]), tuple(r[2:6])) for r in preds[stem] if len(r) >= 6]

        def add(code, msg, line=None, **extra):
            issues.append(Issue(CHECK, WARN, code, stem, msg, line, extra))   # TẤT CẢ chỉ là cảnh báo

        # ---- A) Mỗi dự đoán ĐÁNG TIN (conf đủ cao, vật đủ lớn) -> tối đa MỘT issue, theo thứ tự dự đoán
        for rc, conf, rbox in rows:
            if conf < conf_thr or rbox[2] * W * rbox[3] * H < min_area:
                continue                               # model không chắc / vật quá nhỏ (guideline không gán)
            # cands: nhãn MỌI lớp chồng lên dự đoán này đủ nhiều (IoU >= iou_missing)
            cands = [(iou, lc) for _, lc, lbox in labels if (iou := iou_xywh(rbox, lbox)) >= iou_missing]
            if not cands:
                # (1) model thấy vật mà nhãn không có box nào ở đó
                add("POSSIBLE_MISSING", f"model thấy {_name(ds, rc)} (conf {conf:.2f}) nhưng nhãn không có box",
                    conf=round(conf, 4), model_cls=rc)
                continue
            same = [iou for iou, lc in cands if lc == rc]
            if same:
                # (2) đã có nhãn cùng lớp phủ vật này: chỉ cờ nếu box lỏng/lệch
                best = max(same)
                if best < iou_loose:
                    add("POSSIBLE_LOOSE_BOX", f"{_name(ds, rc)}: box nhãn lệch/lỏng so với model (IoU {best:.2f})",
                        conf=round(conf, 4), iou=round(best, 4))
                continue                               # IoU đủ cao -> đồng ý, im lặng (kể cả có nhãn khác lớp chồng lên)
            # (3) chỉ có nhãn KHÁC lớp ở đó
            best, lc = max(cands)
            if best >= iou_match:
                add("POSSIBLE_WRONG_CLASS", f"nhãn là {_name(ds, lc)} nhưng model nói {_name(ds, rc)} "
                    f"(conf {conf:.2f}, IoU {best:.2f})", conf=round(conf, 4), iou=round(best, 4),
                    label_cls=lc, model_cls=rc)
            # IoU trong [iou_missing, iou_match): mơ hồ -> không cờ gì

        # ---- B) Mỗi box nhãn không khớp vật nào model thấy (conf >= fp_conf, KHÔNG lọc diện tích) -> FALSE_POS
        fp_boxes = [rbox for _, conf, rbox in rows if conf >= fp_conf]
        for no, lc, lbox in labels:                    # theo số dòng
            best = max((iou_xywh(lbox, rbox) for rbox in fp_boxes), default=0.0)
            if best < iou_missing:
                add("POSSIBLE_FALSE_POS", f"box {_name(ds, lc)} ở dòng {no} không khớp vật nào model thấy "
                    f"(IoU tốt nhất {best:.2f})", line=no, iou=round(best, 4))

    return issues
