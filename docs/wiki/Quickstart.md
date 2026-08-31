# 快速開始

## 1. 安裝

```bash
git clone https://github.com/Lucien-1127/zhiyan-legal.git
cd zhiyan-legal
bash scripts/setup.sh
source .venv/bin/activate
```

安裝腳本會建立 `.venv`、安裝 `zhiyan-legal` 與測試工具、建立 `.env` 範本，並執行不呼叫 API 的 dry-run。

若要手動安裝：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

## 2. 無 API 金鑰試跑

```bash
zhiyan-legal "公然侮辱的構成要件" --dry-run
zhiyan-legal "查台灣近期 deepfake 立法" --task RESEARCH --dry-run
zhiyan-legal "將資料整理成報告" --task REPORT --dry-run
zhiyan-legal --list-tasks
```

`--dry-run` 會執行路由、文件載入與提示詞組合，但不呼叫外部模型。

## 3. 設定 Provider

真正呼叫模型前，編輯本機 `.env`。可用鍵名與端點範例請參考 `.env.example`。

```bash
cp .env.example .env  # setup.sh 已建立時不必重複
```

不要把 `.env`、API key 或 token 提交到 Git。

## 4. 執行測試

以下命令與 GitHub Actions 的無金鑰測試範圍一致：

```bash
python -m pytest tests/ --tb=short \
  --ignore=tests/test_c54_validation.py \
  --ignore=tests/run_ablation_v8_committee.py \
  -m "not integration"
```

## 5. 選用功能

```bash
python -m pip install -e ".[committee]"  # 多模型委員會
python -m pip install -e ".[api]"        # FastAPI
python -m pip install -e ".[docgen]"     # DOCX 產生
python -m pip install -e ".[all]"        # 全部功能
```

## 常見問題

### 沒有 API 金鑰可以測試嗎？

可以。所有 `--dry-run` 命令與大部分單元測試都不需要 API key。

### `--mode` 可以使用嗎？

目前 CLI 使用 `--task`，例如 `--task RESEARCH`。舊文件中的 `--mode` 已停用。

### 斷網時可以使用嗎？

路由、文件組合、dry-run 與本機資料功能可以離線執行。即時法規、裁判查核與外部模型需要網路。

### 這是法律意見嗎？

不是。智研是研究與工程框架。個案權益仍需核對最新法源並諮詢合格專業人士。
