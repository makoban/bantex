# 競艇データ収集システム Dockerfile
FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# タイムゾーン設定
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 依存パッケージインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ソースコードコピー
COPY src/ ./src/

# 実行
CMD ["python", "src/cron_job.py", "realtime"]
