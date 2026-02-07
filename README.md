# 企业微信群内 @ 问答机器人

方案 B：企业微信自建应用 + 接收消息服务器 + RAG 问答。

## 结构

- `backend/` — FastAPI、WeCom 适配层、RAG、限额、管理 API
- `frontend_admin/` — 管理后台（知识/Prompt/限额/日志）
- `data/montreal_realestate/` — 领域知识文件
- `docker-compose.yml` — API + Postgres + Redis
- `SPEC.md` — 技术规格

## 本地开发

1. 复制 `.env.example` 为 `.env`，填写企业微信与 OpenAI 配置。
2. 启动依赖：
   ```bash
   docker compose up -d postgres redis
   ```
3. 后端：
   ```bash
   cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
   ```
4. 企业微信回调需公网 HTTPS，本地可用内网穿透（如 ngrok）暴露 `/wecom/callback`。

## 接口

- **GET/POST** `/wecom/callback` — 企业微信 URL 校验与消息回调
- **POST** `/v1/chat/ask` — 统一问答（见 SPEC.md）
- **GET** `/admin/limits`、`/admin/logs`、`/admin/knowledge/...` — 管理占位

## 部署

- `docker compose up -d` 启动全部。
- 回调地址配置为：`https://你的域名/wecom/callback`，并配置 Token、EncodingAESKey、CorpID、Secret 等。
