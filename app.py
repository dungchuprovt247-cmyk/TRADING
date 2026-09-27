"""
ACB EMA & OBV Strategy Backtester
====================================
Web app kiểm định tính hiệu quả của chiến lược kết hợp EMA và OBV
trên cổ phiếu ACB. Dựa trên notebook của Nhóm 3.

Tác giả: Nhóm 3 – Phiên bản Streamlit
"""

import streamlit as st
import pandas as pd
import numpy as np
import ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================
# CẤU HÌNH TRANG
# ============================================================
st.set_page_config(
    page_title="ACB EMA & OBV Strategy Backtester",
    page_icon="📈",
    layout="wide",
)

# ============================================================
# HÀM TẠO TÍN HIỆU GIAO DỊCH (từ notebook)
# ============================================================

def get_ema_signals(data, ema_period, price_col="Close"):
    """Tín hiệu chỉ dựa trên EMA."""
    close = data[price_col]
    ema = ta.trend.ema_indicator(close, window=int(ema_period))
    raw_entries = close > ema
    raw_exits = close < ema
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema


def get_obv_signals(data, obv_slope_period=3, price_col="Close"):
    """Tín hiệu chỉ dựa trên độ dốc OBV."""
    close = data[price_col]
    volume = data["Volume"]
    obv = ta.volume.on_balance_volume(close, volume)
    obv_slope = obv.diff(obv_slope_period)
    raw_entries = obv_slope > 0
    raw_exits = obv_slope < 0
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, obv_slope


def get_ema_obv_combined_signals(data, ema_period, obv_slope_period=3, price_col="Close"):
    """Tín hiệu kết hợp EMA và OBV."""
    close = data[price_col]
    volume = data["Volume"]
    ema = ta.trend.ema_indicator(close, window=int(ema_period))
    obv = ta.volume.on_balance_volume(close, volume)
    obv_slope = obv.diff(obv_slope_period)
    # Mua khi giá > EMA VÀ OBV slope > 0
    raw_entries = (close > ema) & (obv_slope > 0)
    # Bán khi giá < EMA
    raw_exits = close < ema
    entries = raw_entries.shift(1, fill_value=False)
    exits = raw_exits.shift(1, fill_value=False)
    return entries, exits, ema, obv_slope


# ============================================================
# HÀM QUẢN LÝ VỊ THẾ (State machine – từ notebook)
# ============================================================

def simulate_positions(entries, exits):
    """
    Quản lý vị thế dạng state machine.
    Trả về: position (Series 0/1), buy_orders (bool), sell_orders (bool)
    """
    position = pd.Series(0, index=entries.index, dtype=int)
    buy_orders = pd.Series(False, index=entries.index, dtype=bool)
    sell_orders = pd.Series(False, index=entries.index, dtype=bool)

    current_position = 0
    for i in range(len(entries)):
        if current_position == 0 and entries.iloc[i]:
            current_position = 1
            buy_orders.iloc[i] = True
        elif current_position == 1 and exits.iloc[i]:
            current_position = 0
            sell_orders.iloc[i] = True
        position.iloc[i] = current_position
    return position, buy_orders, sell_orders


# ============================================================
# HÀM BACKTEST (thay thế vectorbt, tái hiện đầy đủ logic)
# ============================================================

def run_backtest(data, entries, exits, price_col="Close",
                 init_cash=100.0, fees=0.002, slippage=0.001, sl_stop=0.07):
    """
    Mô phỏng backtest Long-only giống vbt.Portfolio.from_signals:
    - direction = 'longonly', accumulate = False
    - Phí giao dịch (fees), trượt giá (slippage), stop-loss cố định (sl_stop)
    - Trả về dict chứa các chỉ số hiệu suất và equity curve.
    """
    close = data[price_col].values
    n = len(close)

    cash = init_cash
    shares = 0.0
    entry_price = 0.0
    equity = np.zeros(n)
    position_arr = np.zeros(n, dtype=int)
    trades = []  # list of dicts: {entry_date, exit_date, entry_price, exit_price, return_pct}
    current_trade_entry_idx = None

    entries_arr = entries.values.astype(bool)
    exits_arr = exits.values.astype(bool)
    dates = data.index

    in_position = False

    for i in range(n):
        price = close[i]

        # Kiểm tra stop-loss nếu đang giữ vị thế
        if in_position and sl_stop > 0:
            loss_pct = (price - entry_price) / entry_price
            if loss_pct <= -sl_stop:
                # Trigger stop-loss – bán tại giá hiện tại (trừ slippage)
                sell_price = price * (1 - slippage)
                proceeds = shares * sell_price
                fee = proceeds * fees
                cash = proceeds - fee
                trade_return = (sell_price / entry_price) - 1
                trades.append({
                    "entry_date": dates[current_trade_entry_idx],
                    "exit_date": dates[i],
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "return_pct": trade_return * 100,
                })
                shares = 0.0
                in_position = False
                current_trade_entry_idx = None

        # Xử lý tín hiệu Entry/Exit
        if not in_position and entries_arr[i]:
            # MUA
            buy_price = price * (1 + slippage)
            fee = cash * fees
            invest = cash - fee
            shares = invest / buy_price
            entry_price = buy_price
            cash = 0.0
            in_position = True
            current_trade_entry_idx = i
        elif in_position and exits_arr[i]:
            # BÁN
            sell_price = price * (1 - slippage)
            proceeds = shares * sell_price
            fee = proceeds * fees
            cash = proceeds - fee
            trade_return = (sell_price / entry_price) - 1
            trades.append({
                "entry_date": dates[current_trade_entry_idx],
                "exit_date": dates[i],
                "entry_price": entry_price,
                "exit_price": sell_price,
                "return_pct": trade_return * 100,
            })
            shares = 0.0
            in_position = False
            current_trade_entry_idx = None

        # Tính equity tại thời điểm i
        if in_position:
            equity[i] = shares * price
            position_arr[i] = 1
        else:
            equity[i] = cash
            position_arr[i] = 0

    equity_series = pd.Series(equity, index=dates)
    daily_returns = equity_series.pct_change().fillna(0)

    # Tính các chỉ số
    total_return = (equity[-1] / init_cash - 1) * 100
    benchmark_return = (close[-1] / close[0] - 1) * 100

    # Drawdown
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown = drawdown.min() * 100  # negative %

    # Sharpe Ratio (annualized, giả định 252 ngày giao dịch)
    if daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Sortino Ratio
    downside = daily_returns[daily_returns < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = (daily_returns.mean() / downside.std()) * np.sqrt(252)
    else:
        sortino = 0.0

    # Calmar Ratio
    annual_return = (1 + total_return / 100) ** (252 / max(n, 1)) - 1
    calmar = annual_return / abs(max_drawdown / 100) if max_drawdown != 0 else 0.0

    # Win rate
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    n_closed = len(trades_df)
    if n_closed > 0:
        wins = trades_df[trades_df["return_pct"] > 0]
        n_wins = len(wins)
        win_rate = n_wins / n_closed * 100
        avg_win = wins["return_pct"].mean() if n_wins > 0 else 0
        losses = trades_df[trades_df["return_pct"] <= 0]
        n_losses = len(losses)
        avg_loss = losses["return_pct"].mean() if n_losses > 0 else 0
        best_trade = trades_df["return_pct"].max()
        worst_trade = trades_df["return_pct"].min()
        # Profit Factor
        gross_profit = wins["return_pct"].sum() if n_wins > 0 else 0
        gross_loss = abs(losses["return_pct"].sum()) if n_losses > 0 else 1e-9
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    else:
        win_rate = avg_win = avg_loss = best_trade = worst_trade = profit_factor = 0

    # Vị thế coverage
    position_coverage = position_arr.sum() / n * 100

    return {
        "equity": equity_series,
        "daily_returns": daily_returns,
        "trades": trades_df,
        "stats": {
            "Giai đoạn": f"{dates[0].strftime('%Y-%m-%d')} → {dates[-1].strftime('%Y-%m-%d')}",
            "Số phiên": n,
            "Vốn ban đầu": f"{init_cash:.2f}",
            "Vốn cuối kỳ": f"{equity[-1]:.2f}",
            "Tổng lợi nhuận (%)": f"{total_return:.2f}%",
            "Lợi nhuận Benchmark (%)": f"{benchmark_return:.2f}%",
            "Max Drawdown (%)": f"{max_drawdown:.2f}%",
            "Sharpe Ratio": f"{sharpe:.4f}",
            "Sortino Ratio": f"{sortino:.4f}",
            "Calmar Ratio": f"{calmar:.4f}",
            "Profit Factor": f"{profit_factor:.4f}",
            "Số giao dịch đã đóng": n_closed,
            "Tỷ lệ thắng (%)": f"{win_rate:.2f}%",
            "Lãi TB giao dịch thắng (%)": f"{avg_win:.2f}%",
            "Lỗ TB giao dịch thua (%)": f"{avg_loss:.2f}%",
            "Giao dịch tốt nhất (%)": f"{best_trade:.2f}%",
            "Giao dịch tệ nhất (%)": f"{worst_trade:.2f}%",
            "Thời gian giữ vị thế (%)": f"{position_coverage:.2f}%",
        },
        "raw": {
            "total_return": total_return,
            "benchmark_return": benchmark_return,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "profit_factor": profit_factor,
            "n_trades": n_closed,
            "win_rate": win_rate,
        },
    }


# ============================================================
# GIAO DIỆN STREAMLIT
# ============================================================

st.title("📈 Kiểm Định Chiến Lược EMA & OBV – Cổ Phiếu ACB")
st.markdown("""
**Chiến lược giao dịch kết hợp EMA (Exponential Moving Average) và OBV (On-Balance Volume)**
dựa trên nghiên cứu của **Nhóm 3**. Ứng dụng cho phép điều chỉnh tham số, so sánh 3 chiến lược
và kiểm định trên tập Train/Test tách biệt.
""")

# ---- SIDEBAR ----
st.sidebar.header("⚙️ Tham số chiến lược")

# Upload hoặc dùng dữ liệu mặc định
uploaded_file = st.sidebar.file_uploader(
    "📁 Tải lên file CSV (hoặc dùng dữ liệu ACB mặc định)",
    type=["csv"],
    help="File CSV cần có các cột: Close, Open, High, Low, Volume, Date",
)

# Tham số EMA
ema_period = st.sidebar.slider(
    "Chu kỳ EMA", min_value=5, max_value=100, value=20, step=1,
    help="Chu kỳ đường EMA (Exponential Moving Average)"
)

# Tham số OBV slope
obv_slope_period = st.sidebar.slider(
    "Chu kỳ độ dốc OBV", min_value=2, max_value=30, value=3, step=1,
    help="Số phiên tính độ dốc OBV (On-Balance Volume)"
)

st.sidebar.markdown("---")
st.sidebar.header("🏦 Tham số giao dịch")

init_cash = st.sidebar.number_input(
    "Vốn ban đầu", min_value=10.0, value=100.0, step=10.0,
)
fees = st.sidebar.number_input(
    "Phí giao dịch (%)", min_value=0.0, max_value=5.0, value=0.2, step=0.05,
    help="Phí mỗi lần mua/bán (% trên giá trị giao dịch)"
) / 100
slippage = st.sidebar.number_input(
    "Trượt giá (%)", min_value=0.0, max_value=5.0, value=0.1, step=0.05,
    help="Trượt giá ước tính khi thực hiện lệnh"
) / 100
sl_stop = st.sidebar.number_input(
    "Stop-loss (%)", min_value=0.0, max_value=30.0, value=7.0, step=0.5,
    help="Mức cắt lỗ cố định (% tính từ giá mua)"
) / 100

st.sidebar.markdown("---")
st.sidebar.header("📅 Chia tập dữ liệu")
train_start = st.sidebar.text_input("Bắt đầu Train", value="2014")
train_end = st.sidebar.text_input("Kết thúc Train", value="2020")
test_start = st.sidebar.text_input("Bắt đầu Test", value="2021")
test_end = st.sidebar.text_input("Kết thúc Test", value="2023")

# ---- TẢI DỮ LIỆU ----
@st.cache_data
def load_data(file):
    df = pd.read_csv(file)
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    df.sort_index(inplace=True)
    return df


try:
    if uploaded_file is not None:
        df = load_data(uploaded_file)
    else:
        df = load_data("ACB.csv")

    train_df = df.loc[train_start:train_end].copy()
    test_df = df.loc[test_start:test_end].copy()

    if len(train_df) == 0 or len(test_df) == 0:
        st.error("❌ Không có dữ liệu trong khoảng thời gian đã chọn. Vui lòng kiểm tra lại.")
        st.stop()

    # Hiển thị thông tin dữ liệu
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("📊 Tổng số phiên", f"{len(df):,}")
    with col_info2:
        st.metric("🏋️ Tập Train", f"{len(train_df):,} phiên")
    with col_info3:
        st.metric("🧪 Tập Test", f"{len(test_df):,} phiên")

except Exception as e:
    st.error(f"❌ Lỗi tải dữ liệu: {e}")
    st.info("Vui lòng đảm bảo file `ACB.csv` nằm cùng thư mục hoặc tải file CSV lên.")
    st.stop()


# ============================================================
# CHẠY BACKTEST CHO 3 CHIẾN LƯỢC
# ============================================================

def run_strategy(data, strategy_name, ema_p, obv_p, price_col="Close", **kwargs):
    """Chạy backtest cho một chiến lược cụ thể trên một tập dữ liệu."""
    if strategy_name == "EMA":
        entries, exits, ema = get_ema_signals(data, ema_p, price_col)
        extra = {"ema": ema}
    elif strategy_name == "OBV":
        entries, exits, obv_slope = get_obv_signals(data, obv_p, price_col)
        extra = {"obv_slope": obv_slope}
    else:  # Combined
        entries, exits, ema, obv_slope = get_ema_obv_combined_signals(data, ema_p, obv_p, price_col)
        extra = {"ema": ema, "obv_slope": obv_slope}

    position, buy_orders, sell_orders = simulate_positions(entries, exits)
    result = run_backtest(data, entries, exits, price_col, **kwargs)
    result["position"] = position
    result["buy_orders"] = buy_orders
    result["sell_orders"] = sell_orders
    result["extra"] = extra
    return result


# ============================================================
# TABS CHÍNH
# ============================================================
tab_train, tab_test, tab_compare, tab_signals, tab_data = st.tabs([
    "📈 Backtest Train", "🧪 Backtest Test", "📊 So sánh chiến lược",
    "🔔 Bảng tín hiệu", "📋 Dữ liệu gốc"
])

strategies = ["EMA", "OBV", "EMA + OBV"]
strategy_labels = {
    "EMA": f"EMA Riêng lẻ (EMA={ema_period})",
    "OBV": f"OBV Riêng lẻ (OBV_slope={obv_slope_period})",
    "EMA + OBV": f"EMA + OBV Kết hợp (EMA={ema_period}, OBV_slope={obv_slope_period})",
}

bt_kwargs = dict(init_cash=init_cash, fees=fees, slippage=slippage, sl_stop=sl_stop)


def display_backtest_results(data, dataset_label):
    """Hiển thị kết quả backtest cho tất cả chiến lược trên một tập dữ liệu."""
    results = {}
    for strat in strategies:
        results[strat] = run_strategy(data, strat, ema_period, obv_slope_period, **bt_kwargs)

    # ---- Metrics tổng quan ----
    st.subheader(f"📊 Tổng quan hiệu suất – Tập {dataset_label}")
    metric_cols = st.columns(3)
    for idx, strat in enumerate(strategies):
        r = results[strat]["raw"]
        with metric_cols[idx]:
            st.markdown(f"**{strategy_labels[strat]}**")
            st.metric("Tổng lợi nhuận", f"{r['total_return']:.2f}%",
                       delta=f"vs B&H: {r['total_return'] - r['benchmark_return']:.2f}%")
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Sharpe", f"{r['sharpe']:.3f}")
                st.metric("Win Rate", f"{r['win_rate']:.1f}%")
            with col_b:
                st.metric("Max DD", f"{r['max_drawdown']:.2f}%")
                st.metric("Trades", f"{r['n_trades']}")

    # ---- Biểu đồ Equity Curve ----
    st.subheader(f"💰 Đường vốn (Equity Curve) – Tập {dataset_label}")
    fig_eq = go.Figure()
    colors = {"EMA": "#2196F3", "OBV": "#FF9800", "EMA + OBV": "#4CAF50"}
    for strat in strategies:
        eq = results[strat]["equity"]
        fig_eq.add_trace(go.Scatter(
            x=eq.index, y=eq.values,
            mode="lines", name=strategy_labels[strat],
            line=dict(color=colors[strat], width=2),
        ))
    # Benchmark (Buy & Hold)
    bh = data["Close"] / data["Close"].iloc[0] * init_cash
    fig_eq.add_trace(go.Scatter(
        x=bh.index, y=bh.values,
        mode="lines", name="Buy & Hold (Benchmark)",
        line=dict(color="gray", width=1, dash="dash"),
    ))
    fig_eq.update_layout(
        height=450,
        xaxis_title="Ngày",
        yaxis_title="Giá trị danh mục",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        hovermode="x unified",
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # ---- Biểu đồ giá + chỉ báo cho chiến lược kết hợp ----
    st.subheader(f"🕯️ Biểu đồ giá & tín hiệu – EMA + OBV ({dataset_label})")
    comb = results["EMA + OBV"]

    fig_price = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.25, 0.25],
        vertical_spacing=0.03,
        subplot_titles=("Giá đóng cửa & EMA", "Khối lượng giao dịch", "Độ dốc OBV"),
    )

    # Candlestick / Line
    fig_price.add_trace(go.Scatter(
        x=data.index, y=data["Close"],
        mode="lines", name="Close", line=dict(color="#333", width=1),
    ), row=1, col=1)

    if "ema" in comb["extra"]:
        fig_price.add_trace(go.Scatter(
            x=data.index, y=comb["extra"]["ema"],
            mode="lines", name=f"EMA({ema_period})",
            line=dict(color="#E91E63", width=1.5),
        ), row=1, col=1)

    # Buy/Sell markers
    buy_dates = data.index[comb["buy_orders"]]
    sell_dates = data.index[comb["sell_orders"]]
    fig_price.add_trace(go.Scatter(
        x=buy_dates, y=data.loc[buy_dates, "Close"],
        mode="markers", name="MUA",
        marker=dict(symbol="triangle-up", color="green", size=10),
    ), row=1, col=1)
    fig_price.add_trace(go.Scatter(
        x=sell_dates, y=data.loc[sell_dates, "Close"],
        mode="markers", name="BÁN",
        marker=dict(symbol="triangle-down", color="red", size=10),
    ), row=1, col=1)

    # Volume
    fig_price.add_trace(go.Bar(
        x=data.index, y=data["Volume"],
        name="Volume", marker_color="rgba(100, 100, 200, 0.3)",
    ), row=2, col=1)

    # OBV Slope
    if "obv_slope" in comb["extra"]:
        obv_s = comb["extra"]["obv_slope"]
        colors_obv = ["green" if v > 0 else "red" for v in obv_s.values]
        fig_price.add_trace(go.Bar(
            x=data.index, y=obv_s.values,
            name="OBV Slope", marker_color=colors_obv,
        ), row=3, col=1)

    fig_price.update_layout(height=750, showlegend=True, hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig_price, use_container_width=True)

    # ---- Bảng thống kê chi tiết ----
    st.subheader(f"📋 Thống kê chi tiết – Tập {dataset_label}")
    stats_data = {}
    for strat in strategies:
        stats_data[strategy_labels[strat]] = results[strat]["stats"]
    stats_df = pd.DataFrame(stats_data)
    st.dataframe(stats_df, use_container_width=True)

    # ---- Danh sách giao dịch ----
    with st.expander(f"📝 Danh sách giao dịch – EMA + OBV ({dataset_label})"):
        trades_df = results["EMA + OBV"]["trades"]
        if len(trades_df) > 0:
            trades_display = trades_df.copy()
            trades_display.index = range(1, len(trades_display) + 1)
            trades_display.index.name = "STT"
            trades_display.columns = ["Ngày vào", "Ngày ra", "Giá vào", "Giá ra", "Lợi nhuận (%)"]
            trades_display["Lợi nhuận (%)"] = trades_display["Lợi nhuận (%)"].round(2)
            trades_display["Giá vào"] = trades_display["Giá vào"].round(2)
            trades_display["Giá ra"] = trades_display["Giá ra"].round(2)
            st.dataframe(trades_display, use_container_width=True)
        else:
            st.info("Không có giao dịch nào được thực hiện.")

    return results


# ---- TAB TRAIN ----
with tab_train:
    train_results = display_backtest_results(train_df, "Train")

# ---- TAB TEST ----
with tab_test:
    test_results = display_backtest_results(test_df, "Test")

# ---- TAB SO SÁNH ----
with tab_compare:
    st.subheader("📊 So sánh hiệu suất Train vs Test")

    compare_data = []
    for strat in strategies:
        tr = train_results[strat]["raw"]
        te = test_results[strat]["raw"]
        compare_data.append({
            "Chiến lược": strategy_labels[strat],
            "Tập dữ liệu": "Train",
            "Tổng lợi nhuận (%)": round(tr["total_return"], 2),
            "Benchmark (%)": round(tr["benchmark_return"], 2),
            "Sharpe Ratio": round(tr["sharpe"], 4),
            "Sortino Ratio": round(tr["sortino"], 4),
            "Max Drawdown (%)": round(tr["max_drawdown"], 2),
            "Win Rate (%)": round(tr["win_rate"], 2),
            "Profit Factor": round(tr["profit_factor"], 4),
            "Số giao dịch": tr["n_trades"],
        })
        compare_data.append({
            "Chiến lược": strategy_labels[strat],
            "Tập dữ liệu": "Test",
            "Tổng lợi nhuận (%)": round(te["total_return"], 2),
            "Benchmark (%)": round(te["benchmark_return"], 2),
            "Sharpe Ratio": round(te["sharpe"], 4),
            "Sortino Ratio": round(te["sortino"], 4),
            "Max Drawdown (%)": round(te["max_drawdown"], 2),
            "Win Rate (%)": round(te["win_rate"], 2),
            "Profit Factor": round(te["profit_factor"], 4),
            "Số giao dịch": te["n_trades"],
        })

    compare_df = pd.DataFrame(compare_data)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)

    # Biểu đồ cột so sánh
    st.subheader("📊 Biểu đồ so sánh Sharpe Ratio")
    fig_sharpe = go.Figure()
    colors_bar = {"Train": "#2196F3", "Test": "#FF5722"}
    for dataset in ["Train", "Test"]:
        subset = compare_df[compare_df["Tập dữ liệu"] == dataset]
        fig_sharpe.add_trace(go.Bar(
            x=subset["Chiến lược"], y=subset["Sharpe Ratio"],
            name=dataset, marker_color=colors_bar[dataset],
        ))
    fig_sharpe.update_layout(barmode="group", height=400, yaxis_title="Sharpe Ratio")
    st.plotly_chart(fig_sharpe, use_container_width=True)

    # So sánh Tổng lợi nhuận
    st.subheader("📊 Biểu đồ so sánh Tổng lợi nhuận (%)")
    fig_ret = go.Figure()
    for dataset in ["Train", "Test"]:
        subset = compare_df[compare_df["Tập dữ liệu"] == dataset]
        fig_ret.add_trace(go.Bar(
            x=subset["Chiến lược"], y=subset["Tổng lợi nhuận (%)"],
            name=dataset, marker_color=colors_bar[dataset],
        ))
    fig_ret.update_layout(barmode="group", height=400, yaxis_title="Tổng lợi nhuận (%)")
    st.plotly_chart(fig_ret, use_container_width=True)

    # Nhận xét tự động
    st.subheader("💡 Nhận xét tự động")
    comb_train = train_results["EMA + OBV"]["raw"]
    comb_test = test_results["EMA + OBV"]["raw"]

    if comb_test["sharpe"] > 0 and comb_test["total_return"] > 0:
        st.success("✅ **Chiến lược EMA + OBV có hiệu suất dương trên tập Test** – "
                   "tín hiệu cho thấy chiến lược có tiềm năng áp dụng thực tế, "
                   "tuy nhiên cần kiểm định thêm trên nhiều giai đoạn khác.")
    elif comb_test["total_return"] > comb_test["benchmark_return"]:
        st.warning("⚠️ **Chiến lược vượt Benchmark nhưng lợi nhuận tuyệt đối chưa ấn tượng** – "
                   "cần thận trọng khi áp dụng.")
    else:
        st.error("❌ **Chiến lược chưa hiệu quả trên tập Test** – "
                 f"Lợi nhuận: {comb_test['total_return']:.2f}% vs Benchmark: {comb_test['benchmark_return']:.2f}%. "
                 "Sharpe Ratio âm cho thấy rủi ro cao hơn lợi nhuận. "
                 "Có thể xảy ra hiện tượng overfitting trên tập Train.")

    sharpe_drop = comb_train["sharpe"] - comb_test["sharpe"]
    if sharpe_drop > 1.0:
        st.warning(f"⚠️ **Cảnh báo Overfitting**: Sharpe giảm {sharpe_drop:.2f} từ Train sang Test. "
                   "Chiến lược có thể đã overfit trên dữ liệu quá khứ.")

# ---- TAB TÍN HIỆU ----
with tab_signals:
    st.subheader("🔔 Bảng chỉ báo & vị thế giao dịch (EMA + OBV kết hợp)")

    signal_dataset = st.radio("Chọn tập dữ liệu:", ["Train", "Test"], horizontal=True)
    signal_data = train_df if signal_dataset == "Train" else test_df

    entries, exits, ema, obv_slope = get_ema_obv_combined_signals(
        signal_data, ema_period, obv_slope_period
    )
    position, buy_orders, sell_orders = simulate_positions(entries, exits)

    obv_full = ta.volume.on_balance_volume(signal_data["Close"], signal_data["Volume"])

    signal_df = pd.DataFrame({
        "Giá Đóng Cửa": signal_data["Close"],
        f"EMA ({ema_period})": ema.round(2),
        f"OBV": obv_full.round(0),
        f"Độ dốc OBV ({obv_slope_period} phiên)": obv_slope.round(0),
        "Lệnh MUA": buy_orders,
        "Lệnh BÁN": sell_orders,
        "Vị thế": position.map({0: "🔴 Tiền mặt", 1: "🟢 Nắm giữ"}),
    })

    # Chỉ hiện phiên có lệnh
    show_all = st.checkbox("Hiển thị tất cả phiên", value=False)
    if show_all:
        st.dataframe(signal_df, use_container_width=True, height=500)
    else:
        signal_orders = signal_df[buy_orders | sell_orders]
        st.dataframe(signal_orders, use_container_width=True, height=500)
        st.caption(f"Hiển thị {len(signal_orders)} phiên có lệnh giao dịch. "
                   f"Tổng: {int(buy_orders.sum())} lệnh MUA, {int(sell_orders.sum())} lệnh BÁN.")

# ---- TAB DỮ LIỆU ----
with tab_data:
    st.subheader("📋 Dữ liệu gốc ACB")
    st.dataframe(df, use_container_width=True, height=500)
    st.caption(f"Tổng: {len(df)} phiên | Từ {df.index.min().strftime('%Y-%m-%d')} "
               f"đến {df.index.max().strftime('%Y-%m-%d')}")


# ---- FOOTER ----
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.85em;'>
        <p>📈 ACB EMA & OBV Strategy Backtester | Nhóm 3<br>
        Dựa trên framework chiến lược EMA & OBV cho cổ phiếu ACB<br>
        <em>Lưu ý: Kết quả backtest không đảm bảo hiệu suất trong tương lai.</em></p>
    </div>
    """,
    unsafe_allow_html=True,
)
