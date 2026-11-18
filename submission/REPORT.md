# Báo cáo Day 09 — Phạm Duy Thanh, 2A202603343

## 1. Kết luận trước
**Kết luận: Hold** (mã thoát 10).
- **Vào → ra:**
  - lô raw có 224 ảnh;
  - cửa vào loại 22 ảnh: 2 hỏng, 3 quá nhỏ, 8 trùng byte, 4 gần trùng, 5 rò rỉ test;
  - còn **202 ảnh**, được xuất vào `submission/export/clean_v1`. Đây là **bản nháp**: manifest ghi `decision: Hold`, chưa phát hành.
- **Lý do Hold:** sau 35 thay đổi tự động và 80/80 ảnh được người duyệt, **không còn lỗi bắt buộc** (0 ERROR trong `07_error_list_v3`). Nhưng **38/202 ảnh (18.8%)** còn cảnh báo chưa ai xem, vượt ngưỡng 10%.
- **Ý nghĩa:** dữ liệu không phải làm lại; chỉ thiếu thời gian người duyệt.

## 2. Lỗi và phân việc
Số liệu lấy từ `02_error_list_v1`:
- vòng QC 1 có **36 lỗi bắt buộc** và **153 cảnh báo** trên 202 ảnh;
- cộng thêm 22/224 ảnh bị loại ở cửa vào.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8/224 ảnh | máy (loại ở cửa vào) | Trùng từng byte (md5) nên chắc chắn trùng; giữ ảnh đầu, loại bản sau |
| `LEAK_TEST` | 5/224 ảnh | máy (loại) | Trùng ảnh của tập test; để lại sẽ làm mAP trên test bị ảo |
| `DUP_IMAGE_NEAR` | 4/224 ảnh | máy (loại) | phash ≤ 12, ngưỡng đã calibrate để không xoá nhầm (§3) |
| `BAD_SIZE` | 3/224 ảnh | máy (loại) | Cạnh ngắn 180–226 px, dưới mức 250 px |
| `CORRUPT_IMAGE` | 2/224 ảnh | máy (loại) | Không đọc được ảnh (img_0010, img_0136) |
| `BOX_OUT_OF_IMAGE` | 8 dòng / 8 ảnh | máy (`clip_box`) | Lỗi cú pháp: cắt box về [0,1], giữ nguyên lớp; trước → sau ghi trong `03_fixes.csv` |
| `DUP_BOX` | 7 dòng / 7 ảnh | máy (`drop_line`) | Box cùng lớp có IoU > 0.9 với dòng trước: xoá dòng sau |
| `BAD_CLASS_ID` | 6 dòng / 6 ảnh | máy (`drop_line`) | id 93, 7, 4, −1 nằm ngoài 0..3; không đoán được lớp đúng nên xoá dòng |
| `BOX_ZERO` | 4 dòng / 4 ảnh | máy (`drop_line`) | Rộng hoặc cao bằng 0, nên không phải box |
| `BAD_FORMAT` | 3 dòng / 3 ảnh | máy (`drop_line`) | Có `nan` hoặc thiếu cột |
| `BAD_CLASS_NAME` | 2 tên trong `data.yaml` | máy (`rename_classes`) | `Person`, `Bus` được ghi lại đúng danh sách lớp của dự án |
| `MISSING_LABEL_FILE` | 6/202 ảnh | **người** | Máy không được bịa nhãn, kể cả tạo file rỗng (file rỗng nghĩa là "ảnh nền"). Máy chỉ ghi `needs_label`; người đã gán nhãn cho cả 6 ảnh |
| `POSSIBLE_MISSING` | 53 / 52 ảnh | người | Lỗi ngữ nghĩa: model thấy vật mà nhãn không có box. Model cũng có thể sai, nên chỉ cảnh báo |
| `POSSIBLE_FALSE_POS` | 29 / 27 ảnh | người | Box nhãn không khớp vật nào model thấy |
| `POSSIBLE_LOOSE_BOX` | 28 / 24 ảnh | người | Đúng vật, nhưng box lệch hoặc lỏng |
| `POSSIBLE_WRONG_CLASS` | 18 / 18 ảnh | người | Nhầm car / truck / bus; chỉ người phân xử được |
| `EMPTY_LABEL` | 12/202 ảnh | người | Máy không biết đây là ảnh nền hay ảnh thiếu nhãn |
| `BOX_TINY` | 6 dòng / 4 ảnh | người | Cạnh box dưới 12 px; giữ hay bỏ theo guideline |
| `BOX_HUGE` | 3 / 3 ảnh | người | Box chiếm hơn 95% ảnh |
| `CLASS_RARE` | 4 (cấp dataset) | — (tự hết) | Là hệ quả của `BAD_CLASS_ID` (lớp −1, 4, 7, 93); biến mất khi máy xoá các dòng đó |

**Hàng đợi** (`05_review_queue.csv`) có **125 ảnh**, nhiều hơn ngân sách 80 ảnh.
- **Cách tính điểm ưu tiên:**
  - mỗi cảnh báo đóng góp trọng số của mã nhân `(1 + conf của model)`, với trọng số lấy từ `review.weights`;
  - ảnh có dòng đã bị máy sửa được cộng thêm điểm.
- **Thứ tự đầu hàng:**
  1. `img_0020` đứng đầu với **11.52 điểm**. Ảnh này vừa bị máy xoá dòng, vừa bị model nghi 2 lỗi ngữ nghĩa:

     | Thành phần | Điểm |
     |---|---:|
     | `FIXED_DROP_LINE` | 2 |
     | `WRONG_CLASS` (nhãn truck, model nói bus): 3 × 1.947 | 5.84 |
     | `MISSING`: 2 × 1.841 | 3.68 |

  2. Tiếp theo là **6 ảnh `NEEDS_LABEL`**, mỗi ảnh 10 điểm. Nếu không ai gán nhãn cho chúng thì chắc chắn Rework (§4a), nên chúng phải được xem trước.
  3. Sau đó là các ảnh có `WRONG_CLASS` hoặc `MISSING` với conf cao (trọng số 3 và 2).
  4. `LOOSE_BOX` (1.5) và `BOX_TINY` (0.3) xếp cuối. Ảnh thứ 80 chỉ còn 3.34 điểm (một `MISSING`).
- **Kết quả với ngân sách 80 ảnh:** người xem được **94/123 cảnh báo ngữ nghĩa** (74/103 ảnh):

  | Mã | Đã duyệt / tổng |
  |---|---|
  | `WRONG_CLASS` | **18/18** |
  | `MISSING` | **51/53** |
  | `FALSE_POS` | 13/24 |
  | `LOOSE_BOX` | 12/28 |

  Phần lọt qua chủ yếu là box lỏng và box thừa, vì trọng số thấp. Đây chính là phần tạo ra 38 ảnh còn cảnh báo khiến cổng ra Hold.

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
