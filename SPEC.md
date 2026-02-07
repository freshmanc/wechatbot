# 企业微信群内 @ 问答机器人 — 技术规格书

## 1. 接入方案

- **选定方案**：企业微信自建应用（方案 B）
- **能力**：群内 @ 机器人才回复、接收消息事件、验签解密、回复群消息
- **不采用**：群机器人 Webhook（仅适合通知，无法接收 @）

## 2. 系统架构

| 组件 | 职责 |
|------|------|
| **WeCom Adapter** | 接收回调、解析 @、标准化请求、调用 `/v1/chat/ask`、回发群消息 |
| **API 服务 (FastAPI)** | `/v1/chat/ask` 统一问答、限额/风控/超时、日志与统计 |
| **RAG 引擎** | 知识入库、检索(domain 过滤)、生成(LLM+Prompt)、引用/免责 |
| **数据层** | Postgres(业务/日志/配置)、pgvector/Chroma、Redis(限额/锁/缓存) |
| **管理后台** | 知识上传/启停/标签、Prompt 版本、限额配置、日志回看与标注 |

## 3. 仓库结构

```
wechatbot/
  backend/
    app/main.py
    app/config.py
    app/wecom/           # 企业微信适配层
    app/api/             # 路由
    app/core/            # 限额、LLM、领域、策略、错误
    app/rag/             # 入库、检索、生成、向量库
    app/db/              # 模型、会话、迁移
  frontend_admin/
  data/
    montreal_realestate/
  docker-compose.yml
  SPEC.md
```

## 4. 关键接口契约

### 4.1 企业微信回调

- **POST** `/wecom/callback`
- 查询参数：`msg_signature`, `timestamp`, `nonce`（URL 校验时还有 `echostr`）
- Body：加密 XML（或 JSON，按企业微信配置）
- 流程：验签 → 解密 → 业务处理 → 加密回复（可选）
- 加解密与签名：严格按企业微信官方算法（AES + SHA1）

### 4.2 统一问答接口

- **POST** `/v1/chat/ask`

**请求体：**

```json
{
  "platform": "wecom",
  "group_id": "wecom_room_xxx",
  "user_id": "wecom_user_xxx",
  "text": "问题文本",
  "domain": "montreal_realestate",
  "conversation_id": "optional"
}
```

**响应体：**

```json
{
  "request_id": "uuid",
  "answer": "文本回答",
  "citations": [
    {"source": "xxx.md", "title": "标题", "chunk_id": "..."}
  ],
  "flags": {"limited": false, "fallback": false}
}
```

## 5. @ 才回复策略

- 只处理**群聊**消息
- 判断是否 **@ 机器人**（或触发关键字）
- 提取真实问题文本（去掉 @ 与前缀）
- 调用 `POST /v1/chat/ask`
- 回复群消息（可 @ 提问者）

## 6. 数据模型（最小可用）

- **domains**：领域（如 Montreal/RealEstate）
- **documents**：知识文档元信息、标签、启停
- **chunks**：切分后的文本块
- **prompt_versions**：系统/领域/风格 prompt 版本 + active
- **usage_logs**：每次问答（问题、答案、引用、耗时、token、错误）
- **ratings**：质量标注（好/一般/差）
- **limits**：限额配置（用户/群/全局）

### Redis 限额 Key

- `user:{user_id}:{yyyyMMdd}`
- `group:{group_id}:{yyyyMMdd}`
- `global:{yyyyMMdd}`

## 7. RAG 核心策略

- **领域隔离**：入库与检索均带 `domain` 过滤
- **防胡说**：检索为空 → “知识库暂无相关内容”；Prompt 仅基于检索片段回答
- **房产免责**：可配置开关
- **超时兜底**：LLM 超时 15s → 固定兜底文案，日志 `fallback=true`

## 8. 部署（V1）

- **Docker Compose**：api（FastAPI）、postgres、redis，（可选）worker
- 企业微信回调需**公网 + HTTPS**（推荐 Nginx + 证书）
