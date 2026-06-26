# Docker — 智研容器化部署

此目錄收納 zhiyan-legal 的 Docker 與 Docker Compose 設定。

| 檔案 | 用途 |
|:-----|:-----|
| `Dockerfile` | API 伺服器容器映像 |
| `docker-compose.yml` | 完整部署（API + RAG + 前端 + Caddy） |
| `nginx/` | 反向代理設定 |

> 當前階段以 Tailscale + systemd 部署為主，Docker 支援為 Phase 3 目標。
