import os
import sys

# boatrace-dashboardディレクトリをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'boatrace-dashboard')))

from auto_betting import get_boat1_local_win_rate, fetch_local_win_rate_from_web, get_db_connection
from datetime import datetime

def test_recovery():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. 0.00の判定修正テスト (1/28 琵琶湖 4R)
            print("--- Test 1: Testing 0.00 logic (Biwako 4R) ---")
            local_win_rate = get_boat1_local_win_rate(cur, '20260128', '11', 4)
            print(f"Result: {local_win_rate} (Expected: 0.0)")

            # 2. Webフォールバックテスト (存在しないレース日を適当に指定してDBヒットしないようにする)
            # または、DBにないはずの今日のデータ
            print("\n--- Test 2: Testing Web Fallback (Biwako 4R via Web) ---")
            web_rate = fetch_local_win_rate_from_web('20260128', '11', 4)
            print(f"Web Result: {web_rate}")

            # 3. 他の場 (例: 若松 4R - 8.55のはず)
            print("\n--- Test 3: Testing another case (Wakamatsu 4R) ---")
            wakamatsu_rate = get_boat1_local_win_rate(cur, '20260128', '20', 4)
            print(f"Result: {wakamatsu_rate} (Expected: 8.55)")

    finally:
        conn.close()

if __name__ == "__main__":
    test_recovery()
