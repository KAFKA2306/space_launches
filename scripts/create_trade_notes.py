import os
import re

import pandas as pd


def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)


def main():
    print("Starting trade note generation with FX logic & Comment Preservation...")

    trades_path = "data/unified/trades_unified.csv"
    charts_path = "resources/charts.csv"
    output_dir = "docs/tradenote"

    os.makedirs(output_dir, exist_ok=True)

    try:
        trades = pd.read_csv(trades_path, low_memory=False)
        trades["trade_date"] = pd.to_datetime(trades["trade_date"])

        charts = pd.read_csv(charts_path, index_col=0, parse_dates=True)
        chart_cols = set(charts.columns)

        if "USDJPY=X" in charts.columns:
            usdjpy_series = charts["USDJPY=X"].dropna()
            latest_usdjpy = usdjpy_series.iloc[-1]
            print(f"Latest USDJPY: {latest_usdjpy}")
        else:
            latest_usdjpy = 100.0
            print("Warning: USDJPY=X not found in charts, using fallback 100.0")

    except Exception as e:
        print(f"Error loading data: {e}")
        return

    unique_codes = trades["security_code"].dropna().unique()

    buy_keywords = ["buy", "purchase", "reinvest", "買"]
    sell_keywords = ["sell", "sales", "売", "解約"]
    usd_keywords = ["usd", "ドル", "us"]
    hkd_keywords = ["hkd", "hk"]

    for code in unique_codes:
        code_str = str(code)
        t = trades[trades["security_code"] == code].copy()
        if t.empty:
            continue

        name = t["security_name"].dropna().iloc[0] if not t["security_name"].dropna().empty else "Unknown"
        safe_name = sanitize_filename(name)
        file_path = os.path.join(output_dir, f"{sanitize_filename(code_str)}_{safe_name}.md")

        # Preserve existing comments
        existing_comment = ""
        default_comment_section = [
            "",
            "---",
            "",
            "## 振り返り・コメント",
            "",
            "<!-- ここに自分のコメントを追記してください -->",
            "",
        ]

        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "## 振り返り・コメント" in content:
                        parts = content.split("## 振り返り・コメント")
                        if len(parts) > 1:
                            existing_comment = parts[1]  # Keep everything after the header
            except Exception as e:
                print(f"Error reading existing file {file_path}: {e}")

        # Determine Currency
        currency = "JPY"
        if "currency" in t.columns:
            currencies = t["currency"].dropna().unique()
            if len(currencies) > 0:
                c_mode = str(currencies[0]).lower()
                if any(k in c_mode for k in usd_keywords):
                    currency = "USD"
                elif any(k in c_mode for k in hkd_keywords):
                    currency = "HKD"

        # Chart Processing
        adj_close_series = None
        candidates = [code_str, f"{code_str}.T", f"{code_str}.US"]
        for cand in candidates:
            if cand in chart_cols:
                adj_close_series = charts[cand].sort_index()
                break

        t = t.sort_values("trade_date")
        latest_price = None
        latest_date_str = "-"

        if adj_close_series is not None:
            prices_df = adj_close_series.reset_index()
            prices_df.columns = ["trade_date", "adj_close"]
            t_merged = pd.merge_asof(t, prices_df, on="trade_date", direction="backward")

            valid_prices = adj_close_series.dropna()
            if not valid_prices.empty:
                latest_price = valid_prices.iloc[-1]
                latest_date_str = valid_prices.index[-1].strftime("%Y-%m-%d")
        else:
            t_merged = t.copy()
            t_merged["adj_close"] = pd.NA

        # PnL Calculation
        total_quantity = 0.0
        total_cost = 0.0
        realized_pnl = 0.0

        t_merged["type_norm"] = t_merged["transaction_type"].astype(str).str.lower()

        for _, row in t_merged.iterrows():
            amt = abs(row["amount_jpy"]) if pd.notna(row["amount_jpy"]) else 0.0
            qty = row["quantity"] if pd.notna(row["quantity"]) else 0.0
            ttype = row["type_norm"]

            is_buy = any(k in ttype for k in buy_keywords)
            is_sell = any(k in ttype for k in sell_keywords)
            is_transfer_in = "入庫" in ttype
            is_transfer_out = "出庫" in ttype

            if is_buy:
                total_quantity += qty
                total_cost += amt
            elif is_sell:
                if total_quantity > 0:
                    avg_cost = total_cost / total_quantity
                    cost_of_sold = avg_cost * qty
                    realized_pnl += amt - cost_of_sold
                    total_cost -= cost_of_sold
                    total_quantity -= qty
                else:
                    realized_pnl += amt
                    total_quantity -= qty
            elif is_transfer_in:
                total_quantity += qty
            elif is_transfer_out:
                if total_quantity > 0:
                    avg_cost = total_cost / total_quantity
                    total_cost -= avg_cost * qty
                    total_quantity -= qty

        if abs(total_quantity) < 0.0001:
            total_quantity = 0.0
            total_cost = 0.0

        unrealized_pnl = 0.0
        market_value_jpy = 0.0
        latest_price_jpy = 0.0

        if total_quantity > 0.0001 and latest_price is not None:
            if currency == "USD":
                latest_price_jpy = latest_price * latest_usdjpy
                market_value_jpy = total_quantity * latest_price_jpy
            elif currency == "HKD":
                latest_price_jpy = latest_price * 19.0
                market_value_jpy = total_quantity * latest_price_jpy
            else:
                latest_price_jpy = latest_price
                market_value_jpy = total_quantity * latest_price

            unrealized_pnl = market_value_jpy - total_cost

        # Markdown Generation
        md_lines = []
        md_lines.append(f"# {code_str} {name}")
        md_lines.append("")
        md_lines.append("## 基本情報")
        md_lines.append("")
        md_lines.append(f"**最新データ ({latest_date_str})**")

        if latest_price:
            if currency == "USD":
                md_lines.append(f"- 最新価格: ${latest_price:,.2f} (約¥{latest_price_jpy:,.0f})")
                md_lines.append(f"- 為替レート: ¥{latest_usdjpy:,.2f}/USD")
            elif currency == "HKD":
                md_lines.append(f"- 最新価格: HK${latest_price:,.2f} (約¥{latest_price_jpy:,.0f})")
            else:
                md_lines.append(f"- 最新価格: ¥{latest_price:,.2f}")

        md_lines.append("")
        md_lines.append("| 項目 | 値 |")
        md_lines.append("|---|---|")
        md_lines.append(f"| 銘柄コード | {code_str} |")
        md_lines.append(f"| 現在保有 | {total_quantity:,.2f} |")
        md_lines.append(f"| 平均取得単価 | ¥{total_cost / (total_quantity if total_quantity > 0 else 1):,.2f} |")
        md_lines.append(f"| 現在評価額 | ¥{market_value_jpy:,.0f} |")
        md_lines.append(f"| 含み損益 | **¥{unrealized_pnl:,.0f}** |")
        md_lines.append(f"| 実現損益 | **¥{realized_pnl:,.0f}** |")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("## News on Trade Day")
        md_lines.append("")
        md_lines.append("<!-- News data placeholder -->")
        md_lines.append("_No news data available for this ticker._")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        md_lines.append("## 売買履歴")
        md_lines.append("")
        md_lines.append("| 日付 | 取引 | 数量 | 約定単価(円) | Adj Close | 受渡金額(JPY) |")
        md_lines.append("|---|---|---|---|---|---|")

        for _, row in t_merged.iterrows():
            d = row["trade_date"].strftime("%Y-%m-%d")
            ttype = row["transaction_type"]
            qty = row["quantity"]
            price = row["price"]
            amt = row["amount_jpy"]
            ac = row["adj_close"]

            qty_str = f"{qty:,.2f}" if pd.notna(qty) else "-"
            price_str = f"{price:,.2f}" if pd.notna(price) else "-"
            amt_str = f"{amt:,.0f}" if pd.notna(amt) else "-"
            ac_str = f"{ac:,.2f}" if pd.notna(ac) else "-"

            if "入庫" in str(ttype):
                ttype = f"{ttype} (Correction)"
                price_str = f"({price_str})"

            md_lines.append(f"| {d} | {ttype} | {qty_str} | {price_str} | {ac_str} | {amt_str} |")

        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

        # Append logic
        if existing_comment:
            md_lines.append("## 振り返り・コメント")
            md_lines.append(existing_comment)
        else:
            md_lines.extend(default_comment_section)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

    print("Generation complete.")


if __name__ == "__main__":
    main()
