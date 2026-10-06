# Báo cáo Lab: Self evolving Agentic

## 1. Thông tin sinh viên và cấu hình

- Họ tên: Nguyễn Đức Thịnh
- Mã sinh viên: 2A202602468

- Nhà cung cấp và mô hình: OpenAI, `openai:gpt-4o-mini` (khóa lưu trong `.env`, không ghi ở đây); nhiệt độ `LAB_TEMPERATURE=0`; `recursion_limit=60`; timeout 120 giây, 2 lần thử lại cho mỗi lần gọi API.
- Phiên bản Deep Agents: 0.7.21; hệ điều hành: Windows 11, shell của tác tử chạy trong WSL (Ubuntu, Python 3.11.17, venv bằng uv); không dùng Docker.
- Số lần chạy tác vụ đã dùng: 22 lần hoàn tất (9 học, 3 baseline đánh giá, 4 subagents đánh giá gồm 1 lần chạy sớm bị ghi đè, 6 skills-auto cuối) và 1 lần dừng giữa chừng (subagents/data-eval). Ngân sách gợi ý: 30.
- Commit của tag `freeze`: `1780e86`. Commit giả thuyết: `1dfc77f`.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

- H1 (subagents so với baseline): `subagents` KHÔNG cao hơn `baseline` về điểm trung bình tác vụ đánh giá (dự đoán chênh lệch ≤ 0,05 hoặc âm), và tốn token gấp 2 đến 3 lần. Căn cứ: trên tác vụ học, `subagents` cho tổng điểm 4/27 so với 5/27 của `baseline`; `code-learn` tốn 224k token so với 64k và kết thúc do vượt giới hạn đệ quy; subagent chỉ thấy prompt được giao nên dễ mất quy tắc. Tài liệu lab ghi chi phí đa tác tử cao hơn đáng kể so với một tác tử.
- H2 (skills-auto so với baseline): `skills-auto` gần bằng `baseline` trên tác vụ đánh giá (chênh lệch ≤ 1 check mỗi tác vụ), và không giúp check quy ước mới. Căn cứ: cả ba lần chạy học đều có `skills_read = 0`, tức skill chưa được đọc; ba skill do curator sinh chỉ bao quát quy ước mã (type hints, changelog, không sửa tests), không bao quát quy tắc dữ liệu và log. Tài liệu SkillEvolBench (theo pseudo-code) cho thấy lợi ích trên tác vụ học thường không chuyển sang tác vụ mới.
- H3 (tác vụ học so với tác vụ đánh giá): với cùng điều kiện, điểm trung bình tác vụ đánh giá thấp hơn tác vụ học, chủ yếu do check quy ước mới (`rule_` mới) mà phản hồi học không có. Căn cứ: ở tác vụ học, `baseline` đạt trung bình khoảng 0,17 (4/10, 0/8, 1/9), và các check `rule_` đều thất bại; quy ước của tác vụ đánh giá không học được từ phản hồi.

## 3. Làm quen Deep Agents (Phần 0.3)

1. Công cụ mặc định: `ls`, `read_file`, `write_file`, `edit_file`, `delete`, `glob`, `grep` (tệp); `execute` (chạy lệnh shell); `task` (giao việc cho subagent). Công cụ cho phép chạy lệnh là `execute`.
2. Mô tả `task` cho biết subagent `general-purpose` "has access to all tools as the main agent". Mỗi lần gọi là stateless: "the agent sees only the prompt you give it and returns a single final report". Vì vậy subagent không thấy hội thoại của tác tử chính, chỉ thấy prompt được giao.
3. System prompt mặc định là rỗng (`''`). Câu trong mô tả `task`: "Each invocation is stateless by default". Câu trong mô tả `execute`: "Use absolute paths and avoid `cd` so the working directory stays stable".

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

Dữ liệu: `baseline` trên 3 tác vụ học (22 check thất bại). Nhóm: A bỏ qua đặc tả, B không kiểm chứng, D bỏ sót dữ liệu bẩn/định dạng, E quy ước tổ chức (`rule_`), F báo cáo sai sự thật.

| Tác vụ | Check thất bại | Nhóm | Bằng chứng |
|---|---|---|---|
| code-learn | tests_not_modified | A | "the original files in tests/ must not be modified" (tác tử đã sửa tests) |
| code-learn | csv_quoting_follows_docstring | A | `to_csv_row` trả về `'Desk, large "oak",10.00,2'`, không đúng docstring |
| code-learn | parse_price_all_formats | D | "wrong for: ['(12.00)']" (số âm dạng ngoặc chưa xử lý) |
| code-learn | rule_type_hints, rule_regression_tests, rule_changelog | E | Trích `RULE:` trong `detail` (type hints, `tests/test_regressions.py`, `CHANGELOG.md` mục `## Unreleased`) |
| data-learn | north_q1_revenue, north_q1_orders, top_region, missing_amount_orders, duplicate_rows_removed | F, B | Vết: `ModuleNotFoundError: No module named 'pandas'`; sau đó tác tử ghi tay `0.0, 0, "West", 0, 0` vào `answer.json` và báo đã phân tích xong. Tệp chỉ đọc 100/102 dòng, không kiểm chứng lại |
| data-learn | rule_money_in_cents, rule_meta_block, rule_clean_csv | E | Trích `RULE:` (tiền theo cent, khối `meta`, `workspace/clean.csv` không được tạo) |
| logs-learn | entry_count, timestamps_utc, exception_fields, repeat_counts, counts_by_service | D | "wrong number of entries (got 10)"; "4/25 timestamps match"; 21 giá trị `exception` và `repeat_count` sai |
| logs-learn | rule_service_names, rule_sorted_errors, rule_schema_header | E | Trích `RULE:` (tên dịch vụ, thứ tự sắp xếp, `schema_version`) |

Đếm: A 2, B/F 5, D 6, E 9 (tổng 22). Lỗi kỹ thuật (A, B, D, F) chiếm 13/22, lỗi quy ước (E) chiếm 9/22. Không có nhóm nào chiếm tuyệt đối. Điều này khác kỳ vọng của GUIDE (lỗi chủ yếu là E): với mô hình này, lỗi kỹ thuật ở tác vụ dữ liệu và log là chính. Nguyên nhân chung là tác tử không đọc kỹ đề, không kiểm chứng kết quả, và trong sandbox không có pandas.

Nhận xét: skill do curator sinh có thể phòng nhóm E trong code (type hints, changelog) nhưng không phòng được nhóm D/F ở dữ liệu và log, vì curator không nhận được phản hồi đủ rõ cho các lỗi đó.

## 5. Điều kiện `subagents` (Phần 2.3)

- Các subagent đã định nghĩa: `explorer` (đọc tài liệu, chỉ báo cáo sự thật, không sửa tệp), `implementer` (thực hiện thay đổi, chạy kiểm tra), `reviewer` (kiểm tra độc lập từng quy tắc, tính lại số liệu, không sửa tệp). Mô tả `description` viết theo hành động: khi nào gọi.
- `subagent_calls`: tác vụ học `data-learn` 1 lần (`implementer`); các tác vụ còn lại 0 lần, kể cả 3 tác vụ đánh giá. Với lần 0, tác tử chính tự quyết định không giao việc dù `SUBAGENTS_NOTE` khuyến khích; trong các lần chạy này, tác tử làm trực tiếp bằng công cụ tệp và shell.
- Thông tin khi giao việc: lời giao của `data-learn` có đủ 5 trường số liệu của đề nhưng không nhắc quy ước đầu ra (tiền theo cent, khối `meta`, `clean.csv`), nên 3 check `rule_` thất bại. Subagent báo `north_q1_revenue: 0.0` và `duplicate_rows_removed: 4`, còn tác tử chính chuyển tiếp mà không kiểm tra lại. Điểm: 1/8, cao hơn `baseline` (0/8) ở đúng một check.
- Token và thời gian: trung bình tác vụ học 92.981 token so với 36.490 (2,5 lần); tác vụ đánh giá 207.546 so với 118.409 (1,75 lần). `code-learn` mất 88 giây so với 40 giây và vượt giới hạn đệ quy.

## 6. Self-evolving: skill do curator sinh (Phần 3)

- Số lần chạy curator: 2. Lần 1 không ghi skill nào vì mô hình đặt `name` bằng dấu gạch dưới, trong khi bộ kiểm tra chỉ chấp nhận chữ thường và dấu gạch ngang. Tôi sửa prompt để nêu rõ định dạng tên (mã của lab, không sửa tay skill). Lần 2 ghi 3 skill. Số skill bị xóa: 0.

| Skill | Tổng quát hay riêng cho tác vụ học? | Đúng hay sai | Độ dài, `description`, `skills_read` |
|---|---|---|---|
| `check-test-files-not-modified` | Tương đối tổng quát: quy tắc "không sửa tests/" | Hướng đúng (tạo tệp test mới). Bước 2 (sao lưu) không cần; "during updates" mơ hồ | 9 dòng; `description` nêu tình huống "sửa tests"; `skills_read` 0 |
| `document-changelog-updates` | Riêng cho tác vụ học: chứa đúng quy ước `## Unreleased` và định dạng bullet của Acme | Đúng với quy ước đã học; không áp dụng được cho tác vụ đánh giá vì quy ước đó khác | 9 dòng; `description` chung chung ("ensure all changes are documented"); `skills_read` 0 |
| `enforce-type-annotations` | Tổng quát: kiểm tra annotation cho hàm công khai | Đúng. Bước 5 ("chạy static type checker") có thể không có sẵn trong sandbox | 9 dòng; `description` nêu rõ hàm công khai; `skills_read` 0 |

Không skill nào bao quát quy tắc dữ liệu hay log. Không có skill nào bị đọc (xem 4.4 bên dưới).

## 7. Kết quả so sánh (Phần 4.3, 4.4)

Bảng `report/table.md` (chạy `python -m lab.compare`):

| Task | baseline | subagents | skills-auto |
|---|---|---|---|
| code-learn | 4/10 | 2/10 | 4/10 |
| data-learn | 0/8 | 1/8 | 0/8 |
| logs-learn | 1/9 | 1/9 | 1/9 |
| code-eval | 1/11 | 1/11 | 2/11 |
| data-eval | 0/9 | 0/9 | 0/9 |
| logs-eval | 1/10 | 1/10 | 1/10 |
| **Mean score - learning tasks** | 0.17 | 0.15 | 0.17 |
| **Mean score - evaluation tasks** | 0.06 | 0.06 | 0.09 |
| **Mean tokens per run** | 77,450 | 150,263 | 203,301 |
| **Runs that read a skill** | 0/6 | 0/6 | 0/6 |

`python scripts/check_breakdown.py` (sau khi có tag `freeze`):

```text
condition     role    technical  house rules  mean tokens  read a skill
baseline      eval      2/18         0/12         118,409      0/3
baseline      learn     5/18         0/9           36,490      0/3
subagents     eval      2/18         0/12         207,546      0/3
subagents     learn     4/18         0/9           92,981      0/3
skills-auto   eval      3/18         0/12         227,945      0/3
skills-auto   learn     5/18         0/9          178,657      0/3
```

Lần chạy có lỗi (`GraphRecursionError`, vượt 60 bước) và không bị treo: `baseline/code-eval`, `subagents/code-learn`, `subagents/code-eval`, `subagents/data-eval`, `skills-auto/data-eval`, `skills-auto/data-learn`. Tất cả đều được tính điểm như bình thường, không loại bỏ. `skills_modified = false` ở mọi lần chạy; `verify_freeze.py` báo OK.

Xử lý sự cố ghi nhận: (a) lần `subagents/data-eval` đầu tiên bị treo khoảng 9 phút rồi bị tôi dừng; không có log nên chưa xác định nguyên nhân (nghi ngờ một lần gọi API không có timeout). Sau khi thêm log từng bước và timeout cho mô hình, lần chạy lại hoàn tất bình thường (kết quả trong bảng); không có bằng chứng xác nhận nguyên nhân gốc. (b) `skills/auto/README.md` bị đổi kiểu xuống dòng sau khi đóng băng (CRLF do Git trên Windows). Nội dung không đổi; tôi đưa file về đúng bản đóng băng và `verify_freeze.py` báo OK. (c) Kết quả `baseline` tác vụ đánh giá được chạy trước khi thêm timeout và log; logic tác tử không đổi.

## 8. Phân tích

1. **Học và đánh giá:** không điều kiện nào cải thiện tác vụ học so với `baseline` (0,17): `subagents` 0,15, `skills-auto` 0,17 (sau đóng băng; bản sao lưu trước đó cũng 4/10, 0/8, 1/9, không đổi). Trên đánh giá, chỉ `skills-auto` cao hơn (0,09 so với 0,06), và chênh lệch là 1 check ở `code-eval`. Không có điều kiện nào tốt trên học nhưng kém trên đánh giá; chênh lệch này quá nhỏ để kết luận.
2. **Check kỹ thuật và quy ước:** trên mọi điều kiện, check `rule_` đạt 0/9 (học) và 0/12 (đánh giá). Ngay cả quy ước đã học (`rule_changelog`, `rule_type_hints`) cũng không đạt ở `skills-auto` (0/9 `rule_` trên học). Skill không giúp check quy ước mới của đánh giá; lý do chính là không skill nào được đọc.
3. **Vết và `skills_read`:** `skills_read = 0` trong toàn bộ 6 lần chạy `skills-auto` (học và đánh giá). Ví dụ `skills-auto/code-learn`: 5 lệnh đầu là `glob` và 4 lần `read_file` trên mã nguồn, không đọc `skills/`, dù prompt yêu cầu đọc SKILL.md trước tiên. Harness vẫn nạp skill vào system prompt (đã kiểm tra bằng test). Vì vậy skill không được dùng, và kết quả `skills-auto` gần với `baseline`. Không có check nào được skill giúp đạt có bằng chứng.
4. **Chi phí:** token trung bình đánh giá là 118k (`baseline`), 208k (`subagents`), 228k (`skills-auto`). Điểm đánh giá trên 100k token: `baseline` 0,56 (2 check đạt / 355k token), `subagents` 0,32 (2 / 623k), `skills-auto` 0,44 (3 / 684k). `baseline` hiệu quả nhất. Đa tác tử không đáng chi phí trong thí nghiệm này: không cải thiện điểm và tốn gấp 1,75 lần; `data-eval` và `data-learn` của `skills-auto` vượt giới hạn đệ quy với 430–460k token.
5. **Rò rỉ và quá khớp:** không tìm thấy rò rỉ. Curator không nhận dữ liệu tác vụ đánh giá (chỉ đọc `role == "learn"`), và `validate_skill` loại mọi skill có chứa định danh của tác vụ đánh giá. Tôi không mở tệp đánh giá trước khi đóng băng. Skill `document-changelog-updates` có nguy cơ quá khớp (quy ước riêng của tác vụ học), nhưng vì quy ước đánh giá khác nên không gây lợi ích giả.
6. **Nhiễu:** cùng bộ skill, điểm học sau đóng băng và trong bản sao lưu bằng nhau (4/10, 0/8, 1/9), nhưng token khác nhỏ (`code-learn` 51k và 53k). `subagents/code-eval` chạy hai lần: 1/11 cả hai, token 225k và 200k (chênh 11%). Vậy chênh lệch 1 check giữa các điều kiện trên tác vụ đánh giá có thể là nhiễu. Tôi không có số lần lặp đủ để đo khoảng dao động.

**Đánh giá giả thuyết:**
- H1: đúng về điểm (0,06 bằng nhau); sai về mức chi phí: `subagents` tốn 1,75 lần (đánh giá) và 2,5 lần (học), chưa đến mức 2–3 lần ở mọi tác vụ.
- H2: đúng. Chênh lệch 0,03 điểm trung bình (1 check); không giúp check quy ước mới.
- H3: đúng ở cả ba điều kiện: học → đánh giá giảm 0,17→0,06 (`baseline`), 0,15→0,06 (`subagents`), 0,17→0,09 (`skills-auto`).

## 9. Hạn chế và tính hợp lệ

1. **Số mẫu rất nhỏ:** 3 tác vụ mỗi vai trò, mỗi điều kiện chạy một lần. Chênh lệch 1 check (ví dụ 1/11 và 2/11) không đủ để kết luận; nhiễu đo được ở `subagents/code-eval` là 11% token và không đổi điểm, nhưng số lần lặp quá ít để đo khoảng dao động điểm.
2. **Giới hạn đệ quy 60 bước làm nhiều lần chạy dừng sớm:** 6 lần có `GraphRecursionError`, tốn 200k–460k token, cao hơn hẳn các lần không lỗi. Điểm của các lần này phản ánh cả giới hạn của harness, không chỉ khả năng của tác tử.
3. **Chỉ một mô hình (`gpt-4o-mini`), một lần chạy, không có kiểm soát môi trường đầy đủ:** sandbox không có pandas, nên tác vụ dữ liệu buộc tác tử dùng thư viện chuẩn hoặc thất bại; điều này ảnh hưởng đều các điều kiện nhưng làm điểm dữ liệu gần 0.
4. **Curator chỉ ghi được skill sau khi sửa prompt, và skill không được đọc:** điều kiện `skills-auto` gần như chỉ thêm một câu vào prompt. Kết luận về "tự tiến hóa" bị giới hạn bởi việc skill không được dùng; không thể tách hiệu ứng của nội dung skill với hiệu ứng của việc nạp skill.
5. **Tác vụ do giảng viên thiết kế với quy ước ẩn:** các check `rule_` không đạt ở bất kỳ điều kiện nào (0/9 học, 0/12 đánh giá trong mỗi điều kiện), nên điểm phản ánh việc không đoán được quy ước hơn là năng lực kỹ thuật.

## 10. Kết luận

Trong thí nghiệm này, không điều kiện nào cải thiện đáng kể so với `baseline`: `subagents` không tốt hơn nhưng tốn gấp 1,75 đến 2,5 lần token, còn `skills-auto` chỉ hơn 1 check, và không skill nào được tác tử đọc. Mọi quy tắc quy ước đều không đạt, kể cả quy tắc đã có phản hồi trong tác vụ học. Đề xuất tiếp theo: ép đọc skill (ví dụ đưa nội dung skill thẳng vào prompt hoặc kiểm tra `skills_read` trước khi tiếp tục), đồng thời chạy nhiều lần lặp để đo nhiễu.

## Phụ lục

- Lệnh đã chạy (theo thứ tự):
  - `pip install -e .` (venv WSL), `pytest` (34 test offline, đều đạt)
  - `python -m lab.runner --condition baseline --tasks data-learn`, rồi `baseline --tasks code-learn logs-learn`, `subagents --tasks learn`
  - `python -m lab.curator` (lần 1: 0 skill; lần 2 sau khi sửa prompt: 3 skill)
  - `python -m lab.runner --condition skills-auto --tasks learn`
  - Commit `hypotheses` (`1dfc77f`), sao lưu `results/skills-auto` → `results/skills-auto-dev`, commit `freeze skills` và tag `freeze` (`1780e86`)
  - `python -m lab.runner --condition baseline --tasks eval`, `subagents --tasks eval` (chạy lại sau khi thêm log và timeout), `skills-auto --tasks all`
  - `python scripts/verify_freeze.py` (OK), `python -m lab.compare > report/table.md`, `python scripts/check_breakdown.py`
- Thử thách mở rộng (Phần 6): không thực hiện.
- Ghi chú khác:
  - Shell của tác tử không chạy được trên Windows (`cmd.exe` không có `which`, `cat`), nên mọi lần chạy đều trong WSL.
  - `model.py` là tệp có sẵn nên không sửa. Timeout cho mô hình được đặt trong `agent.py` (`default_model`).
  - Đã thêm `progress.log` (log từng bước) và `tests/test_05_robustness.py` (tệp test mới, không sửa test có sẵn).
