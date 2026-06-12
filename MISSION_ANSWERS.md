# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`
1. **Hardcoded Secrets**: API Key (`OPENAI_API_KEY`) và Database URL (`DATABASE_URL`) bị ghi cứng vào code nguồn. Lộ bí mật khi đưa code lên hệ thống quản lý mã nguồn (như GitHub).
2. **Hardcoded Config**: Các biến cấu hình như `DEBUG` và `MAX_TOKENS` bị gán cứng thay vì đọc linh động từ biến môi trường.
3. **Improper Logging**: Sử dụng lệnh `print()` trực tiếp thay vì thư viện logging có cấu trúc (JSON logging). Hơn nữa, dòng log in thẳng giá trị API key nhạy cảm ra đầu ra chuẩn.
4. **No Health Check**: Không thiết kế endpoint `/health` hay `/ready` để kiểm tra trạng thái hoạt động của ứng dụng, khiến các nền tảng điều phối container không thể tự động phát hiện lỗi và khởi động lại.
5. **Hardcoded host & port**: Host được gán cố định là `localhost` (không nhận kết nối bên ngoài container) và port cố định `8000` thay vì lấy từ biến môi trường `PORT`. Chế độ `reload=True` cũng được bật cứng không phù hợp cho môi trường production.
6. **No Graceful Shutdown**: Thiếu trình xử lý tín hiệu hệ thống (SIGTERM, SIGINT) khiến ứng dụng tắt đột ngột, có thể làm ngắt quãng các request đang xử lý.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config  | Hardcode trong file cấu hình | Đọc từ Environment Variables qua Pydantic-settings | Giúp ứng dụng linh hoạt thay đổi cấu hình giữa dev/staging/prod mà không cần đổi mã nguồn. |
| Secrets | Hardcode API key trực tiếp | Load qua biến môi trường thông qua tệp `.env` (không được commit) | Ngăn chặn việc lộ API keys, database credentials lên GitHub. |
| Port | Cứng cổng 8000 | Lấy động từ `os.getenv("PORT")` | Môi trường Cloud (Railway, Cloud Run, Render) tự động cấp và định tuyến qua các cổng bất kỳ. |
| Health check | Không có | Có sẵn các endpoints `/health` (Liveness) và `/ready` (Readiness) | Nền tảng điều phối (Kubernetes, AWS ECS, GCP Cloud Run) biết khi nào cần restart hoặc ngắt traffic. |
| Logging | Sử dụng `print()` không chuẩn | Sử dụng Structured JSON Logging | Dễ thu thập, lưu trữ tập trung, tìm kiếm và phân tích log khi chạy scale nhiều replica. |
| Shutdown | Tắt đột ngột (Hard kill) | Graceful Shutdown (Bắt tín hiệu SIGTERM và hoàn thành request dở dang) | Tránh mất mát dữ liệu hoặc lỗi kết nối cho client khi thực hiện Rolling Deployment. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` chứa đầy đủ bộ cài đặt Python và hệ điều hành đi kèm (dung lượng lớn ~1 GB).
2. **Working directory:** `/app` là thư mục làm việc chính trong container nơi mã nguồn được sao chép vào.
3. **Why COPY requirements.txt first?** Để tối ưu hóa cơ chế cache layer của Docker. Chỉ khi nào danh sách thư viện `requirements.txt` thay đổi thì Docker mới phải chạy lại lệnh cài đặt thư viện (`pip install`), ngược lại nó sẽ sử dụng lại layer đã build giúp tiết kiệm nhiều thời gian.
4. **CMD vs ENTRYPOINT:** `CMD` chỉ định lệnh mặc định và có thể bị ghi đè hoàn toàn khi chạy container bằng cách truyền tham số bổ sung ở terminal. `ENTRYPOINT` định nghĩa tệp thực thi chính cố định cho container và các tham số truyền thêm sẽ được nối tiếp vào tệp thực thi đó.

### Exercise 2.3: Image size comparison
- **Develop (Single-stage):** ~1.02 GB
- **Production (Multi-stage + Slim base):** ~160 MB
- **Difference:** Giảm khoảng **84%** kích thước lưu trữ.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway/Render deployment
- **URL:** https://production-agent-28ld.onrender.com/
- **Screenshot:** [Link to screenshots in screenshots/ folder](screenshots/deployment_railway.png)

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results
- **API Key auth:** Endpoint `/ask` từ chối truy cập (401 Unauthorized) nếu thiếu header `X-API-Key` hoặc sai giá trị key.
- **JWT auth:** Flow đăng nhập `/auth/token` trả về JWT Access Token hợp lệ. Client đính kèm `Authorization: Bearer <token>` để thực hiện hỏi đáp.
- **Rate limiting:** Lượt truy cập liên tiếp vượt quá 10 req/min sẽ trả về `429 Too Many Requests` đi kèm header `Retry-After`.

### Exercise 4.4: Cost guard implementation
- Triển khai cost guard bằng cách sử dụng Redis để ghi nhận chi phí token thực tế của từng người dùng (`user_id`).
- Mỗi yêu cầu tới model AI sẽ có ước lượng số token dựa trên kích thước của câu hỏi (ví dụ: `len(question.split()) * 2`).
- Nếu tổng chi phí của user trong tháng/ngày hiện tại (được lưu trong Redis bằng key `budget:user_id:YYYY-MM`) vượt quá budget đã cấu hình (ví dụ: $10.0), API sẽ lập tức từ chối và trả về lỗi HTTP 402 (Payment Required) trước khi thực hiện gọi API của LLM thực tế, bảo vệ ngân sách tối đa.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
- **Health check & Readiness check:** Endpoint `/health` trả về trạng thái liveness của app. Endpoint `/ready` ping tới Redis hoặc Database để xác nhận toàn bộ hệ thống dependencies đã sẵn sàng nhận traffic.
- **Graceful shutdown:** Sử dụng module `signal` để bắt tín hiệu `SIGTERM`. Khi nhận được tín hiệu, đặt `_is_ready = False` để `/ready` trả về lỗi (tín hiệu cho load balancer dừng route traffic mới đến instance này), sau đó chờ tất cả request đang thực thi hoàn thành (`_in_flight_requests == 0`) rồi mới ngắt kết nối và dừng ứng dụng.
- **Stateless design:** Di chuyển hoàn toàn bộ nhớ lịch sử hội thoại và bộ đếm giới hạn (rate limiting, cost guard) từ RAM của server sang **Redis**. Khi đó ta có thể scale ngang thành nhiều replica, các replica chia sẻ chung session qua Redis.
- **Load balancing:** Sử dụng Nginx phân tán traffic theo thuật toán Round-Robin đến 3 replica của Agent. Nếu một replica bị lỗi hoặc bị tắt để nâng cấp, Nginx sẽ tự động định hướng sang 2 replica còn lại một cách mượt mà.
