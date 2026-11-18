# Báo cáo Day 09 — <Họ và tên>, <MSHV>

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | `DUP_IMAGE_NEAR` 1.00 / 0.50 (3/6) → 1.00 / 0.67 (4/6); `DUP_IMAGE_EXACT` giữ 1.00 / 1.00 | Cờ = **xoá ảnh**, nên ưu tiên precision. Trên raw, cặp trùng thật xa nhất có phash = 10 (img_0186 ≈ img_0061: bản thu nhỏ, nhãn khớp 100%); cặp gộp nhầm đầu tiên xuất hiện ở 16. Chọn 12 ở giữa khoảng trống; 10–14 cho cùng kết quả trên raw: loại 17 ảnh (8 EXACT, 5 LEAK_TEST, 4 NEAR). |
| `second_opinion.conf` | 0.25 | **0.6** | `WRONG_CLASS` 0.56 / 0.83 → 0.62 / 0.83; `MISSING` 0.50 / 1.00 → 0.57 / 1.00; `LOOSE_BOX` 0.29 / 0.40 → 0.20 / 0.20; `FALSE_POS` 0.31 / 1.00 (không đổi, vì dùng `fp_conf` cố định) | Chỉ là cảnh báo cho người, nên ưu tiên recall. 0.6 là mức cao nhất còn giữ recall `MISSING` 8/8 và `WRONG_CLASS` 5/6 (2 lỗi đắt nhất), trong khi precision tăng; đổi lại mất 1/5 `LOOSE_BOX` (trọng số thấp, vốn là điểm mù). Trên raw: hàng đợi 143 → 125 ảnh; ảnh còn cảnh báo chưa duyệt 58 → 38/202. **Không chọn 0.8** dù nó ra Release (16/202 = 7.9%): recall `MISSING` trên calib tụt 1.00 → 0.75; trên raw, số `POSSIBLE_MISSING` trong `07_error_list_v3` tụt 13 → 1. Hàng đợi nhỏ đi vì checker ngừng nhìn, không phải vì nhãn sạch, nên đó là Release giả. |

**Một chỗ calibration có thể đánh lừa: `phash_dist = 16` là giá trị tốt nhất trên calib nhưng gộp nhầm trên raw.**
- **Trên calib:** 16 có F1 `DUP_IMAGE_NEAR` cao nhất bảng (1.00 / 0.83 / 0.91).
- **Trên raw, số ảnh bị loại ở bước 1:**

  | `phash_dist` | 2–4 | 10–14 | 16 | 18 | 20 |
  |---|---:|---:|---:|---:|---:|
  | Ảnh bị loại (/224) | 14 | 17 | 26 | 60 | 134 |

- **8/9 ảnh mới bị loại ở mức 16 không giống ảnh "gốc":**
  - tương quan điểm ảnh (ảnh xám 64×64) chỉ từ −0.25 đến 0.46, và nhãn không khớp;
  - vd. img_0011 vs img_0008: tương quan 0.20, 0% box khớp; img_0013 vs test/test_087: −0.25;
  - đó là ảnh khác nhau bị coi là trùng hoặc rò rỉ test.
  - Ảnh còn lại (img_0084 vs img_0074: tương quan 0.75, 71% box khớp, cùng tỉ lệ khung 3:4) nhiều khả năng là trùng thật nhưng biến đổi mạnh. Mức 12 bỏ sót nó; đây là điểm mù đã biết (mục 4). Muốn bắt nó thì phải chấp nhận xoá nhầm 8 ảnh khác.
- **Vì sao calib không lộ ra lỗi này:**
  - Precision 1.00 trên calib chỉ dựa trên 6 cặp gần trùng trong 39 ảnh. Raw có 224 ảnh, so với 140 ảnh tham chiếu test/val, nên số cặp so sánh lớn hơn nhiều.
  - Calib **không có ca `LEAK_TEST`**, nên bảng sweep không đo được báo động giả loại này. Ở mức 20, 22/39 ảnh calib bị gắn nhầm `LEAK_TEST`. Trong đó có 2/3 ảnh trùng byte, vì LEAK được ưu tiên trước EXACT, nên recall `EXACT` tụt 1.00 → 0.33. Trong bảng, đó là dấu hiệu duy nhất của 22 FP vô hình này.
- **Bằng chứng ngược (mức 12 chỉ loại ảnh trùng thật):**
  - img_0101 là bản cắt 90% vùng giữa của test/test_039 (tương quan 0.97);
  - img_0223 là bản thu nhỏ của img_0077 (tương quan 0.99, nhãn khớp 100%).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release? (b) Dùng AI viết code? Ghi 3 dòng: prompt chính, cách bạn kiểm code AI, 1 lần AI sai. Không dùng: ghi "không dùng".

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
