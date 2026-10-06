# Báo cáo Lab: Self evolving Agentic

> Sao chép tệp này thành `report/REPORT.md` (đã làm ở Phần 0) và điền dần qua các Phần của lab. Xóa các dòng hướng dẫn dạng trích dẫn (bắt đầu bằng `>`). Văn phong kỹ thuật, ngắn gọn, mọi nhận định đi kèm số liệu hoặc bằng chứng. Trong buổi học: điền mục 1 đến 7 (bản nháp). Sau buổi học: hoàn thiện mục 8 đến 10.

## 1. Thông tin sinh viên và cấu hình

- Họ tên: Nguyễn Đức Thịnh 
- Mã sinh viên: 2A202602468

- Nhà cung cấp và mô hình (`LAB_MODEL`, không ghi khóa API), nhiệt độ (`LAB_TEMPERATURE`), `recursion_limit`:
- Phiên bản Deep Agents (`pip show deepagents`): 0.7.21; hệ điều hành: Windows 11, chạy shell trong WSL (Ubuntu, Python 3.11.17, venv bằng uv); không dùng Docker.
- Số lần chạy tác vụ đã dùng / ngân sách:
- Commit của tag `freeze`:

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

> Dự đoán điều kiện nào đạt điểm cao nhất trên **tác vụ đánh giá** và vì sao. Nêu căn cứ từ phân loại lỗi (mục 4) và từ tài liệu tham khảo. Điền cả ba dòng; `verify_freeze.py` kiểm tra điều này.

- H1 (subagents so với baseline): `subagents` KHÔNG cao hơn `baseline` về điểm trung bình tác vụ đánh giá (dự đoán chênh lệch ≤ 0,05 hoặc âm), và tốn token gấp 2 đến 3 lần. Căn cứ: trên tác vụ học, `subagents` cho tổng điểm 4/27 so với 5/27 của `baseline`; `code-learn` tốn 224k token so với 64k và kết thúc do vượt giới hạn đệ quy; subagent chỉ thấy prompt được giao nên dễ mất quy tắc. Tài liệu lab ghi chi phí đa tác tử cao hơn đáng kể so với một tác tử.
- H2 (skills-auto so với baseline): `skills-auto` gần bằng `baseline` trên tác vụ đánh giá (chênh lệch ≤ 1 check mỗi tác vụ), và không giúp check quy ước mới. Căn cứ: cả ba lần chạy học đều có `skills_read = 0`, tức skill chưa được đọc; ba skill do curator sinh chỉ bao quát quy ước mã (type hints, changelog, không sửa tests), không bao quát quy tắc dữ liệu và log. Tài liệu SkillEvolBench (theo pseudo-code) cho thấy lợi ích trên tác vụ học thường không chuyển sang tác vụ mới.
- H3 (tác vụ học so với tác vụ đánh giá): với cùng điều kiện, điểm trung bình tác vụ đánh giá thấp hơn tác vụ học, chủ yếu do check quy ước mới (`rule_` mới) mà phản hồi học không có. Căn cứ: ở tác vụ học, `baseline` đạt trung bình khoảng 0,17 (4/10, 0/8, 1/9), và các check `rule_` đều thất bại; quy ước của tác vụ đánh giá không học được từ phản hồi.

## 3. Làm quen Deep Agents (Phần 0.3)

1. Công cụ mặc định: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep` (tệp); `execute` (chạy lệnh shell); `task` (giao việc cho subagent). Công cụ cho phép chạy lệnh là `execute`.
2. Mô tả `task` cho biết subagent `general-purpose` "has access to all tools as the main agent". Mỗi lần gọi là stateless: "the agent sees only the prompt you give it and returns a single final report". Vì vậy subagent không thấy hội thoại của tác tử chính, chỉ thấy prompt được giao.
3. System prompt mặc định là rỗng (`''`). Câu trong mô tả `task`: "Each invocation is stateless by default". Câu trong mô tả `execute`: "Use absolute paths and avoid `cd` so the working directory stays stable".

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

> Chỉ dùng tác vụ học. Mỗi dòng là một check thất bại.

| Tác vụ | Check thất bại | Nhóm lỗi (A-G) | Bằng chứng (trích ngắn từ `detail` hoặc vết) |
|---|---|---|---|
| | | | |

Nhận xét: nhóm lỗi nào chiếm đa số? Skill có thể phòng ngừa nhóm đó không?

## 5. Điều kiện `subagents` (Phần 2.3)

- Các subagent đã định nghĩa (tên, vai trò, lý do thiết kế):
- `subagent_calls` ở từng tác vụ và nhận xét (kể cả trường hợp bằng 0):
- Thông tin thiếu hoặc thừa khi giao việc (nếu có giao việc):
- Ảnh hưởng đến token và thời gian:

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator, số skill bị xóa và lý do:

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai (nêu chỗ sai nếu có) | Độ dài, `description` và `skills_read` ở Phần 3.4 |
|---|---|---|---|
| | | | |

## 7. Kết quả so sánh (Phần 4.3, 4.4)

> Dán nội dung `report/table.md` và kết quả `python scripts/check_breakdown.py`. Nêu các lần chạy có `error` hoặc `skills_modified = true` (nếu có) và cách xử lý.

```text
(dán bảng ở đây)
```

## 8. Phân tích

> Trả lời từng câu bằng số liệu từ mục 7 và bằng chứng từ vết. Kết quả âm hoặc không có khác biệt vẫn hợp lệ nếu được phân tích tốt.

1. So với `baseline`, điều kiện nào cải thiện điểm tác vụ **học**? Điều kiện nào cải thiện điểm tác vụ **đánh giá**? Có điều kiện nào cải thiện tác vụ học nhưng không cải thiện tác vụ đánh giá? Nếu có, đó là dấu hiệu gì?
2. Tách điểm thành check kỹ thuật và check quy ước (`rule_`). Skill do curator sinh giúp nhóm check nào? Check quy ước **mới** của tác vụ đánh giá có được skill giúp không, và vì sao?
3. Dựa vào vết và `skills_read`, giải thích một check mà skill giúp đạt và một check mà skill không giúp (skill chưa được đọc, đọc nhưng không làm theo, skill thiếu hoặc sai).
4. Chi phí: so sánh số token trung bình giữa các điều kiện. Điều kiện nào có hiệu quả tốt nhất theo điểm trên mỗi token? Đa tác tử có đáng chi phí trong thí nghiệm này không?
5. Có dấu hiệu rò rỉ dữ liệu hoặc quá khớp nào trong skill sinh ra không? Bạn đã phòng tránh như thế nào?
6. Nhiễu: so sánh điểm tác vụ học của cùng bộ skill ở Phần 3.4 (đã sao lưu) và sau đóng băng. Chênh lệch bao nhiêu? Nó cho biết điều gì về độ tin cậy của các chênh lệch trong bảng ở mục 7?

## 9. Hạn chế và tính hợp lệ

> Nêu ít nhất 3 hạn chế và ảnh hưởng của từng hạn chế đến kết luận (ví dụ: chỉ 3 tác vụ mỗi vai trò, mỗi cấu hình chạy một lần, nhiễu của mô hình, tác vụ do giảng viên thiết kế sẵn quy ước, chỉ một mô hình).

1.
2.
3.

## 10. Kết luận

> Tối đa 5 câu. Chỉ khẳng định điều số liệu hỗ trợ. Nêu một đề xuất cải tiến tiếp theo.

## Phụ lục

- Lệnh đã chạy (theo thứ tự):
- Thử thách mở rộng (nếu có): hướng chọn, kết quả, nhận xét.
- Ghi chú khác:
