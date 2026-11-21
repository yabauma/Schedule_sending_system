import streamlit as st
import requests
import re
import whisper

st.title("授業ボイスレコーダー ＆ LINE通知 🎙️🤖")

# --- 設定部分（ご自身のLINE情報に書き換えてください） ---
ACCESS_TOKEN = st.secrets["line"]["ACCESS_TOKEN"]
USER_ID = st.secrets["line"]["USER_ID"]                    # 取得したあなたのユーザーID

st.write("マイクで先生の話を録音すると、自動で文字起こし＆予定を抽出してLINEに通知します！")

# 1. ブラウザでのマイク録音ウィジェット
audio_value = st.audio_input("ここを押して録音開始・停止")

if audio_value is not None:
    st.success("録音が完了しました！")
    
    # 録音した音声を再生確認
    st.audio(audio_value)

    # 音声ファイルをローカルに一時保存
    with open("recording.wav", "wb") as f:
        f.write(audio_value.read())

    st.info("🤖 AI（Whisper）が文字起こしをしています...（少し待ってね）")

    # Whisperモデルをロード（キャッシュで2回目以降を速くする）
    @st.cache_resource
    def load_whisper_model():
        return whisper.load_model("base")

    model = load_whisper_model()

    # 音声を文字に変換
    result = model.transcribe("recording.wav", language="ja")
    transcribed_text = result["text"]

    # 文字起こし結果を画面に表示
    st.subheader("📝 文字起こし結果:")
    st.write(transcribed_text)

    # 2. テキストから予定を抜き出す関数
    def extract_schedule(text):
        tasks = []
        if "提出" in text or "宿題" in text or "ワーク" in text:
            tasks.append("【課題・提出物】関連の記述あり")
        if "テスト" in text or "試験" in text or "範囲" in text:
            tasks.append("【テスト・試験】関連の記述あり")
        
        pages = re.findall(r"\d+ページ", text)
        return tasks, pages

    # 3. LINE送信ボタン
    if st.button("🔍 予定を分析してLINEに通知を送る"):
        detected_tasks, detected_pages = extract_schedule(transcribed_text)
        
        # LINEに送るメッセージの組み立て
        message_text = "🤖【自動通知】先生の発言から予定を検出しました！\n\n"
        for task in detected_tasks:
            message_text += f"・{task}\n"
        if detected_pages:
            message_text += f"・ページ範囲: {', '.join(detected_pages)}\n"
        message_text += f"\n元の発言: {transcribed_text}"
        
        # 4. LINE Messaging APIへリクエスト送信
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
            st.success("🎉 LINEへの通知送信が成功しました！スマホを確認してみてください。")
        else:
            st.error(f"❌ 送信に失敗しました（エラーコード: {response.status_code}）")
            st.write(response.text)