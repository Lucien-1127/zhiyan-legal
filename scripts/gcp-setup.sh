#!/bin/bash
# =============================================================================
# GCP 自動化設定腳本
# 用法: bash scripts/gcp-setup.sh
# 注意：需先啟用 Service Usage API 才能執行
# =============================================================================

set -e

PROJECT="gen-lang-client-0435318113"
REGION="asia-east1"
ZONE="${REGION}-a"
VM="instance-20260606-124442"

echo "==================================="
echo " GCP 自動化工具設定"
echo " Project: ${PROJECT}"
echo " Region:  ${REGION}"
echo "==================================="

# ---- 1. 啟用 APIs ----
echo "[1/5] 啟用 APIs..."
gcloud services enable \
  secretmanager.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  workstations.googleapis.com \
  --project="${PROJECT}"

# ---- 2. Secret Manager：存入 API 金鑰 ----
echo "[2/5] 設定 Secret Manager..."

# 檢查是否有 .env 檔案
if [ -f ".env" ]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    name=$(echo "$key" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
    echo -n "$value" | gcloud secrets create "${name}" \
      --data-file=- \
      --project="${PROJECT}" \
      --replication-policy="automatic" 2>/dev/null \
    && echo "  ✓ ${name} 已存入" \
    || echo "  - ${name} 已存在（略過）"
  done < <(grep -v '^#' .env | grep '=')
else
  echo "  ⚠️ 找不到 .env，跳過 Secret Manager"
fi

# ---- 3. Cloud Run 部署 ----
echo "[3/5] 部署 Cloud Run..."
gcloud builds submit \
  --tag="${REGION}-docker.pkg.dev/${PROJECT}/zhiyan/zhiyan-api:latest" \
  --project="${PROJECT}" 2>/dev/null || echo "  ⚠️ 首次建置需先建立 Artifact Registry"

gcloud run deploy zhiyan-api \
  --image="${REGION}-docker.pkg.dev/${PROJECT}/zhiyan/zhiyan-api:latest" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=5 \
  --concurrency=20 \
  --timeout=300 \
  --set-env-vars="ZHIYAN_MODE=api,LOG_LEVEL=info" \
  --project="${PROJECT}" \
  && echo "  ✓ Cloud Run 部署完成"

# ---- 4. Cloud Scheduler：排程爬蟲 ----
echo "[4/5] 設定 Cloud Scheduler..."

gcloud scheduler jobs create pubsub freelance-crawler \
  --schedule="0 8 * * *" \
  --topic=crawler-trigger \
  --message-body='{"mode":"daily"}' \
  --location="${REGION}" \
  --project="${PROJECT}" 2>/dev/null \
  && echo "  ✓ 排程建立（每日 08:00）" \
  || echo "  - 排程已存在（略過）"

# ---- 5. 快照排程（已存在，補上標籤） ----
echo "[5/5] 確認備份狀態..."
gcloud compute snapshots list \
  --filter="SRC_DISK~${VM}" \
  --limit=3 \
  --format="table(name, status, creationTimestamp.date('%Y-%m-%d'))"

echo ""
echo "==================================="
echo " ✅ GCP 設定完成！"
echo "==================================="
echo ""
echo "下一步："
echo "  Cloud Run API: gcloud run services describe zhiyan-api --region=${REGION}"
echo "  Secret Manager: gcloud secrets list --project=${PROJECT}"
echo "  爬蟲排程:       gcloud scheduler jobs list --location=${REGION}"
