import streamlit as st
import requests
import re
import sqlite3
import pandas as pd

st.title("授業ボイスレコーダー ＆ 予定管理LINE通知 🎙️🤖")

# --- 0. データベースの初期化と操作関数 ---
def init_db():
    conn = sqlite3.connect("schedules.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            subject TEXT,
            deadline_or_date TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 重複チェック用
def check_duplicate(event_type, subject, deadline_or_date, details):
    conn = sqlite3.connect("schedules.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM schedules 
        WHERE event_type = ? AND subject = ? AND deadline_or_date = ? AND details = ?
    ''', (event_type, subject, deadline_or_date, details))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

# 新規保存用
def save_schedule(event_type, subject, deadline_or_date, details):
    conn = sqlite3.connect("schedules.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO schedules (event_type, subject, deadline_or_date, details)
        VALUES (?, ?, ?, ?)
    ''', (event_type, subject, deadline_or_date, details))
    conn.commit()
    conn.close()

# 💡 指定したIDのデータを削除する関数
def delete_schedule(schedule_id):
    conn = sqlite3.connect("schedules.db")
    cursor = conn.cursor()
    cursor.execute('DELETE FROM schedules WHERE id = ?', (schedule_id,))
    conn.commit()
    conn.close()

# 一覧取得用
def get_all_schedules():
    conn = sqlite3.connect("schedules.db")
    df = pd.read_sql("SELECT * FROM schedules", conn)
    conn.close()
    return df

# アプリ起動時にデータベースを準備
init_db()

# --- 1. StreamlitのSecretsからLINE情報を安全に取得 ---
try:
    ACCESS_TOKEN = st.secrets["line"]["ACCESS_TOKEN"]
    USER_ID = st.secrets["line"]["USER_ID"]
except Exception:
    st.error("❌ StreamlitのSecretsにLINEの認証情報（ACCESS_TOKEN, USER_ID）が設定されていません。")
    st.stop()

st.write("先生の発言から予定を抽出して、重複を防ぎながらデータベースに保存＆LINE通知を送ります！")

# 2. 入力エリア（テキストまたは録音）
input_mode = st.radio("入力方法を選択してください", ["テキストで入力・確認", "マイクで録音"])

transcribed_text = ""

if input_mode == "テキストで入力・確認":
    transcribed_text = st.text_area(
        "📝 先生の発言（文字起こし結果）",
        value="来週の金曜日、12月5日に数学の小テストをやります。範囲は教科書の30ページから35ページまでね。"
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

# 3. 簡易的な予定抽出ロジック（キーワード判定）
def extract_schedule_simple(text):
    event_type = "その他"
    if "テスト" in text or "試験" in text or "小テスト" in text:
        event_type = "テスト"
    elif "提出" in text or "宿題" in text or "ワーク" in text:
        event_type = "宿題"
        
    subject = "数学" if "数学" in text else "未指定"
    
    dates = re.findall(r"\d+月\d+日|来週の?[金土日月火水木]", text)
    deadline = dates[0] if dates else "未指定"
    
    pages = re.findall(r"\d+ページ", text)
    details = f"ページ範囲: {', '.join(pages)}" if pages else text
    
    return {
        "event_type": event_type,
        "subject": subject,
        "deadline_or_date": deadline,
        "details": details
    }

# 4. 分析＆重複チェック＆保存＆LINE送信の処理
if transcribed_text and st.button("🔍 予定を分析して保存・LINE通知"):
    schedule_data = extract_schedule_simple(transcribed_text)
    
    is_duplicate = check_duplicate(
        schedule_data["event_type"],
        schedule_data["subject"],
        schedule_data["deadline_or_date"],
        schedule_data["details"]
    )
    
    if is_duplicate:
        st.warning("⚠️ この予定はすでにデータベースに登録されています！（重複のため保存をスキップしました）")
    else:
        save_schedule(
            event_type=schedule_data["event_type"],
            subject=schedule_data["subject"],
            deadline_or_date=schedule_data["deadline_or_date"],
            details=schedule_data["details"]
        )
        st.success("💾 新しい予定をデータベースに保存しました！")

        message_text = (
            "🤖【自動通知】先生の発言から新しい予定を検出しました！\n\n"
            f"📌 種類: {schedule_data['event_type']}\n"
            f"📚 教科: {schedule_data['subject']}\n"
            f"⏰ 日時: {schedule_data['deadline_or_date']}\n"
            f"📖 内容: {schedule_data['details']}\n\n"
            f"元の発言: {transcribed_text}"
        )

        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ACCESS_TOKEN}",
        }
        data = {
            "to": USER_ID,
            "messages": [{"type": "text", "text": message_text}],
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            st.success("🎉 LINEへの通知送信も成功しました！")
        else:
            st.error(f"❌ LINE送信に失敗しました（エラーコード: {response.status_code}）")
            st.write(response.text)

# --- 5. 登録済みスケジュール一覧の表示 ＆ 削除機能 ---
st.markdown("---")
st.subheader("📋 データベースに保存されたスケジュール一覧")
saved_df = get_all_schedules()

if not saved_df.empty:
    st.dataframe(saved_df)

    # 💡 削除用の入力・ボタンエリア
    st.markdown("### 🗑️ 予定の削除")
    # 登録されているデータのIDリストを取得
    schedule_ids = saved_df["id"].tolist()
    
    selected_id = st.selectbox("削除したいスケジュールのIDを選択してください", schedule_ids)
    
    if st.button("選択したIDの予定を削除する"):
        delete_schedule(selected_id)
        st.success(f"🗑️ ID: {selected_id} の予定を削除しました！")
        st.rerun()  # 画面をリロードして最新の一覧を再表示する
else:
    st.info("まだ保存された予定はありません。")
