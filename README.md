# 📈 ACB EMA & OBV Strategy Backtester

Web app kiểm định tính hiệu quả của chiến lược giao dịch kết hợp **EMA (Exponential Moving Average)** và **OBV (On-Balance Volume)** trên cổ phiếu **ACB** (Ngân hàng Thương mại Cổ phần Á Châu).

Dựa trên nghiên cứu của **Nhóm 3** – phiên bản đã sửa lỗi hạch toán vị thế (position accounting).

---

## 🌟 Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| **3 chiến lược** | So sánh EMA riêng lẻ, OBV riêng lẻ, và EMA + OBV kết hợp |
| **Tách Train/Test** | Kiểm định trên tập dữ liệu ngoài mẫu (out-of-sample) |
| **Tham số tùy chỉnh** | Điều chỉnh chu kỳ EMA, OBV, phí, trượt giá, stop-loss |
| **Biểu đồ tương tác** | Đường vốn (Equity Curve), tín hiệu mua/bán, khối lượng, OBV |
| **Thống kê chi tiết** | Sharpe, Sortino, Calmar, Win Rate, Profit Factor, Max Drawdown |
| **Upload dữ liệu** | Hỗ trợ upload file CSV tùy ý hoặc dùng dữ liệu ACB mặc định |
| **Nhận xét tự động** | Cảnh báo overfitting, đánh giá hiệu quả chiến lược |

---

## 🚀 Cài đặt & Chạy

### Chạy local

```bash
# Clone repo
git clone https://github.com/<your-username>/acb-ema-obv-strategy.git
cd acb-ema-obv-strategy

# Cài đặt thư viện
pip install -r requirements.txt

# Chạy app
streamlit run app.py
```

### Deploy trên Streamlit Cloud

1. Push code lên GitHub (bao gồm `app.py`, `requirements.txt`, `ACB.csv`, `README.md`)
2. Truy cập [share.streamlit.io](https://share.streamlit.io)
3. Kết nối GitHub repo
4. Chọn **Main file**: `app.py`
5. Click **Deploy** ✅

---

## 📁 Cấu trúc dự án

```
├── app.py               # Ứng dụng Streamlit chính
├── requirements.txt     # Thư viện Python cần thiết
├── ACB.csv              # Dữ liệu giá lịch sử ACB (2014-2023)
└── README.md            # File hướng dẫn này
```

---

## 📊 Chiến lược giao dịch

### Logic tín hiệu

| Chiến lược | Điều kiện MUA | Điều kiện BÁN |
|------------|---------------|---------------|
| **EMA** | Giá đóng cửa > EMA | Giá đóng cửa < EMA |
| **OBV** | Độ dốc OBV > 0 (áp lực mua tăng) | Độ dốc OBV < 0 (áp lực bán tăng) |
| **EMA + OBV** | Giá > EMA **VÀ** Độ dốc OBV > 0 | Giá đóng cửa < EMA |

### Quản lý vị thế
- **Long-only**: Chỉ mua (không bán khống)
- **Không tích lũy**: Chỉ giữ 1 vị thế tại một thời điểm
- **Shift(1)**: Tín hiệu sử dụng dữ liệu phiên trước (tránh look-ahead bias)
- **Stop-loss cố định**: Tự động cắt lỗ khi thua quá ngưỡng đã đặt

### Tham số mặc định

| Tham số | Giá trị mặc định | Mô tả |
|---------|-------------------|-------|
| EMA Period | 20 | Chu kỳ đường EMA |
| OBV Slope Period | 3 | Số phiên tính độ dốc OBV |
| Phí giao dịch | 0.2% | Phí mỗi lần mua/bán |
| Trượt giá | 0.1% | Slippage ước tính |
| Stop-loss | 7% | Ngưỡng cắt lỗ cố định |

---

## 📐 Các chỉ số hiệu suất

- **Sharpe Ratio**: Lợi nhuận điều chỉnh rủi ro (annualized, 252 ngày)
- **Sortino Ratio**: Tương tự Sharpe nhưng chỉ tính rủi ro giảm giá
- **Calmar Ratio**: Lợi nhuận hàng năm / Max Drawdown
- **Max Drawdown**: Mức sụt giảm tối đa từ đỉnh
- **Profit Factor**: Tổng lãi / Tổng lỗ
- **Win Rate**: Tỷ lệ giao dịch có lãi

---

## 📄 Dữ liệu

File `ACB.csv` chứa dữ liệu giá lịch sử cổ phiếu ACB với các cột:

| Cột | Mô tả |
|-----|-------|
| `Date` | Ngày giao dịch |
| `Close` | Giá đóng cửa |
| `Open` | Giá mở cửa |
| `High` | Giá cao nhất |
| `Low` | Giá thấp nhất |
| `Volume` | Khối lượng giao dịch |

**Giai đoạn**: 2014-01-02 đến 2023-12-29 (2,492 phiên)

Bạn có thể upload file CSV khác với cùng format để kiểm định trên cổ phiếu/tài sản khác.

---

## ⚠️ Lưu ý quan trọng

> **Kết quả backtest không đảm bảo hiệu suất trong tương lai.** Ứng dụng này chỉ dùng cho mục đích nghiên cứu và học thuật. Mọi quyết định đầu tư cần được xem xét kỹ lưỡng với nhiều yếu tố khác.

---

## 👥 Tác giả

**Nhóm 3** – Dự án nghiên cứu chiến lược giao dịch kỹ thuật cho cổ phiếu ACB.

---

## 📜 Giấy phép

Dự án này được phát hành cho mục đích học thuật và nghiên cứu.
