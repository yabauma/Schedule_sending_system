from datetime import datetime
import re
import sqlite3
import pandas as pd
import streamlit as st

st.title("授業ボイスレコーダー ＆ 予定管理アプリ 🎙️💾")

# --- データベースの初期化と操作関数 ---
def init_db():
  conn = sqlite3.connect("schedules.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            subject TEXT,
            deadline_or_date TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()
  conn.close()


def save_schedule(event_type, subject, deadline_or_date, details):
  conn = sqlite3.connect("schedules.db")
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO schedules (event_type, subject, deadline_or_date, details)
        VALUES (?, ?, ?, ?)
    """,
      (event_type, subject, deadline_or_date, details),
  )
  conn.commit()
  conn.close()


def get_all_schedules():
  conn = sqlite3.connect("schedules.db")
  df = pd.read_sql("SELECT * FROM schedules", conn)
  conn.close()
  return df


# アプリ起動時にDBを準備
init_db()

st.write("先生の発言から予定を抽出して、データベースに安全に保存します。")

# 入力方法の選択
input_mode = st.radio("入力方法を選択してください", ["テキストで入力", "マイクで録音"])

transcribed_text = ""

if input_mode == "テキストで入力":
  transcribed_text = st.text_area(
      "📝 先生の発言（文字起こし結果）",
      value=(
          "来週の金曜日、12月5日に数学の小テストをやります。範囲は教科書の30ページから35ページまでね。"
      ),
  )
else:
  audio_value = st.audio_input("ここを押して録音開始・停止")
  if audio_value is not None:
    st.success("録音が完了しました！")
    st.audio(audio_value)

    with open("recording.wav", "wb") as f:
      f.write(audio_value.read())

    st.info("🤖 AI（Whisper）が文字起こしをしています...")
    import whisper

    @st.cache_resource
    def load_whisper_model():
      return whisper.load_model("base")

    model = load_whisper_model()
    result = model.transcribe("recording.wav", language="ja")
    transcribed_text = result["text"]

    st.subheader("📝 文字起こし結果:")
    st.write(transcribed_text)


# 簡易抽出ロジック
def extract_schedule_simple(text):
  event_type = "テスト" if "テスト" in text or "試験" in text else "宿題"
  subject = "数学" if "数学" in text else "未指定"

  dates = re.findall(r"\d+月\d+日|来週の?[金土日月火水木]", text)
  deadline = dates[0] if dates else "未指定"

  pages = re.findall(r"\d+ページ", text)
  details = f"ページ範囲: {', '.join(pages)}" if pages else text

  return {
      "event_type": event_type,
      "subject": subject,
      "deadline_or_date": deadline,
      "details": details,
  }


# 保存ボタン
if transcribed_text and st.button("💾 予定を分析してデータベースに保存"):
  schedule_data = extract_schedule_simple(transcribed_text)

  save_schedule(
      event_type=schedule_data["event_type"],
      subject=schedule_data["subject"],
      deadline_or_date=schedule_data["deadline_or_date"],
      details=schedule_data["details"],
  )
  st.success("🎉 予定をデータベースに正常に保存しました！")

# 登録済みスケジュールの一覧表示
st.markdown("---")
st.subheader("📋 データベースに保存されたスケジュール一覧")
saved_df = get_all_schedules()
if not saved_df.empty:
  st.dataframe(saved_df)
else:
  st.info("まだ保存された予定はありません。")
