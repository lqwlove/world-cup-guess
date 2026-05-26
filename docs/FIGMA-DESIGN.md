# Figma 设计稿规范 — 世界杯 AI 战术室

> **用途**：在 Figma 中从零搭稿或改版；实现阶段再对照本稿开发。  
> **当前代码**：`apps/web` 已有 P0/P1 功能与 pitch 暗色主题，本稿在信息架构上对齐现网，视觉层做「暗色炫酷」升级方向。  
> **画板基准**：Desktop **1440 × 内容自适应**；内容区最大宽度 **1024px**（对应 `max-w-5xl`）。

---

## 0. Figma 文件结构（建议）

| 页面 (Page) | 画板 (Frame) | 说明 |
|-------------|--------------|------|
| **00 · Cover** | Cover | 项目名、版本、日期、免责说明一行 |
| **01 · 赛程** | `01-赛程-默认` / `01-赛程-空态` / `01-赛程-筛选中` | 首页 |
| **02 · 比赛详情** | `02-详情-战术室-共识` / `02-详情-战术室-生成中` / `02-详情-战术室-失败重试` / `02-详情-数据` / `02-详情-市场` | Tab 五态 |
| **03 · 组件库** | Buttons / Badges / Cards / Tabs / Chat / Certificate | 可复用组件 |
| **04 · 设计系统** | Color / Type / Spacing / Effects | Token 与样式 |

**文件命名建议**：`世界杯AI战术室-暗色-v1`

---

## 1. 设计 Token（与代码对齐 + 视觉升级）

### 1.1 颜色

| Token | Hex | 用途 |
|-------|-----|------|
| `bg/pitch-900` | `#0A1628` | 页面背景 |
| `bg/pitch-800` | `#0F2137` | 顶栏、卡片底 |
| `border/pitch-700` | `#163352` | 边框、分割线 |
| `accent/pitch-500` | `#1E6B4A` | 次要强调 |
| `accent/pitch-400` | `#2D9F6F` | 链接、Tab 选中、主按钮 |
| `accent/gold-400` | `#F5C542` | Logo、热门标签 |
| `accent/gold-500` | `#E6A817` | 热门标签描边变体 |
| `text/primary` | `#F1F5F9` (slate-100) | 标题、正文 |
| `text/secondary` | `#94A3B8` (slate-400) | 副文案、时间 |
| `status/ready` | `#2D9F6F` | 已有共识 |
| `status/generating` | `#D97706` (amber-600) | 生成中（可加 pulse 标注） |
| `status/partial` | `#EA580C` | 部分共识 |
| `status/failed` | `#DC2626` | 失败 |
| `status/none` | `#475569` (slate-600) | 未分析 |

**视觉升级（仅 Figma，实现二期）**

- 页面底：径向渐变 `#0A1628` → `#050D18`，叠加 2% 噪点 + 极淡球场线网格（8% 透明度）。
- 卡片 hover：边框 `#2D9F6F` 40% → 100%，外发光 `0 0 24px rgba(45,159,111,0.15)`。

### 1.2 字体

| 样式 | 字号 / 行高 | 字重 | 场景 |
|------|-------------|------|------|
| `Display/H1` | 24 / 32 | Bold | 页面标题「赛程」、详情队名 |
| `Body/MD` | 14 / 20 | Regular | 说明、元数据 |
| `Body/LG` | 18 / 28 | Semibold | 卡片对阵标题 |
| `Caption` | 12 / 16 | Medium | 状态胶囊、Tab、标签 |
| `Mono`（可选） | 13 / 18 | Regular | 概率、Edge 数字 |

**字体族**：中文 **PingFang SC / 思源黑体**；西文与数字 **Inter** 或 **SF Pro**。

### 1.3 间距与圆角

- 栅格：内容区左右 **32px** padding（`px-4` 在 1024 内约 16–32，稿面统一 32）。
- 卡片：`padding 16`，`gap 16`，圆角 **12**（`rounded-xl`）。
- 状态胶囊：圆角 **999**，`padding 4×8`。

---

## 2. 全局框架（所有页面共用）

```
┌────────────────────────────────────────────────────────────── 1440 ─┐
│ Header 64px  bg pitch-800/80 + blur  border-bottom pitch-700        │
│  [世界杯 AI 战术室] gold-400 18 Bold    右: 2026 美加墨 · 研究工具 12  │
├──────────────────────────────────────────────────────── max-w 1024 ─┤
│ Main padding 24 vertical / 32 horizontal                              │
│   {页面内容}                                                          │
├───────────────────────────────────────────────────────────────────────┤
│ Footer Disclaimer 12 slate-400 多行居中 最大宽 768                      │
└───────────────────────────────────────────────────────────────────────┘
```

**Header 组件**

- 左：品牌链回首页（无图标时可先用 ⚽ 或字母 W 占位 24×24）。
- 右：`2026 美加墨 · 研究工具`，`text/secondary`。

**Footer 文案（现网一致）**

> 本平台内容由 AI 基于公开信息生成，仅供参考，不构成任何投资建议或投注建议。请遵守所在地法律法规，理性看待预测结果。

---

## 3. 画板 01 — 赛程首页

### 3.1 `01-赛程-默认`

**区块自上而下**

1. **标题区**
   - H1：`赛程`
   - 副标题：`以赛程为入口，查看 AI 战术室合议结论与完整讨论回放`（14 slate-400，下间距 24）

2. **筛选条** `ScheduleFilters`
   - 三个下拉或 Chip 组：**日期** | **阶段** | **小组**
   - 高度 40，背景 pitch-800，边框 pitch-700，圆角 8
   - 占位：`全部日期` / `全部阶段` / `全部小组`

3. **比赛列表**（单列，`gap 16`）
   - 重复 **MatchCard** 组件 × 3（示例数据见下）

**MatchCard 结构**（宽 100% 内容区）

```
┌─ Card pitch-800 border pitch-700 radius 12 pad 16 ─────────────────┐
│ [可选] 热门 badge: bg gold-400/20 text gold-400 12                    │
│  🇲🇽 墨西哥  vs  🇿🇦 南非          [已有共识] 胶囊 ready 右对齐      │
│  2026-06-12 04:00 北京时间 · 小组赛 · 小组 A                        │
└──────────────────────────────────────────────────────────────────────┘
```

**示例三场（与产品数据一致，用于稿面标注）**

| 主队 | 客队 | 开球（北京时间） |
|------|------|------------------|
| 墨西哥 | 南非 | 6/12 04:00 |
| 韩国 | — | 6/12 11:00 |
| 加拿大 | — | 6/13 04:00 |

（第三场客队按 seed 实际填写；稿面用「加拿大 vs ○○」即可。）

**状态胶囊文案**

| key | 文案 | 色 |
|-----|------|-----|
| none | 未分析 | slate-600 |
| generating | 合议生成中 | amber + 动效标注 |
| ready | 已有共识 | pitch-400 |
| partial | 部分共识 | orange |
| failed | 生成失败 | red |

### 3.2 `01-赛程-空态`

- 筛选条保留
- 列表区居中文案：`暂无赛程数据，请确认 API 服务已启动。`（slate-400 14）

### 3.3 `01-赛程-筛选中`

- 日期 Chip 高亮「2026-06-12」
- 列表仅 2 张卡片（示意筛选结果）

---

## 4. 画板 02 — 比赛详情

### 4.1 共用顶区

- 返回：`← 返回赛程`（14 pitch-400，下间距 16）
- H1：`🇦🇷 阿根廷 vs 🇩🇿 阿尔及利亚`（演示场 `fifa-400021496`）
- 元数据：`2026-06-XX XX:XX 北京时间 · 小组赛 · A 组`（14 slate-400）

**Tab 导航**（下边框 pitch-700）

| Tab | 默认 |
|-----|------|
| AI 战术室 | ✓ 选中：底边 2px pitch-400，文字 pitch-400 |
| 数据概览 | 未选中 slate-400 |
| 预测市场 | 未选中 slate-400 |

### 4.2 `02-详情-战术室-共识`（核心稿）

**纵向布局（建议 1024 宽单栏，复杂区块可 8+4 分栏标注二期）**

1. **阶段进度** `PhaseProgressBar`  
   - 水平步骤：开场 → 交叉质询 → 深挖 → 玩法分拆 → 终局投票 → 共识  
   - 已完成：pitch-400 实心圆 + 连线；当前：gold 脉冲；未达：pitch-700 空心

2. **阅读模式** `ReadModeToggle`  
   - 分段控件：`速览` | `完整回放`（选中 pitch-400 底）

3. **共识证书** `ConsensusCertificate`（主视觉卡）
   - 标题：`合议共识证书`
   - 三玩法表格列：玩法 | 推荐 | 置信度 | 核心论点编号
   - 行：胜平负 / 比分 / 让球 — 用真实 Schema 字段占位
   - 底栏：生成时间、discussion_id 截断（Mono 12）

4. **市场 Edge** `MarketEdgeTable`  
   - 表头：结果 | 共识概率 | 市场隐含 | Edge  
   - Edge 正：绿色 `#2D9F6F`；负：红色

5. **分歧雷达** `DisagreementRadar`（简化为六边形或条形对比图占位）

6. **少数意见** `MinorityOpinions` — 折叠列表 1–2 条

7. **群聊/时间线**（二选一在稿里标清；现网 `ChatRoom` + `MessageTimeline`）
   - **ChatRoom**：左侧角色色点 + 角色名 12 Bold + 气泡 pitch-800
   - 角色色建议：主持人金、数据绿、怀疑派橙、市场紫、教练蓝、球迷灰、裁判红
   - 气泡最大宽 80%，圆角 12，内边距 12

8. **反馈**：`这篇分析有帮助吗？` 👍 👎（完成后显示）

### 4.3 `02-详情-战术室-生成中`

- 同上结构；进度条当前步高亮
- Chat 区底部：`合议进行中…` + 骨架气泡 × 3
- 禁用「重新生成」或隐藏，按 PRD 仅展示状态

### 4.4 `02-详情-战术室-失败重试`

- 顶部 Alert 条：红底 10% + 文案 `合议生成失败：{error 示例}`
- 主按钮：`重新发起合议`（pitch-400 填充，高 40，圆角 8）

### 4.5 `02-详情-数据`

- `MatchDataPanel`：事实卡片列表，每条：标题 + 来源 + 摘要
- 空态：`暂无结构化事实数据`

### 4.6 `02-详情-市场`

- `MarketPanel`：Polymarket 快照时间 + 概率条
- 不可用态：`预测市场数据暂不可用`

---

## 5. 组件库（03 页面必建）

| 组件名 | Variants | 说明 |
|--------|----------|------|
| `Button/Primary` | default, hover, disabled | 背景 pitch-400，字白 |
| `Button/Ghost` | default, hover | 边框 pitch-700 |
| `Badge/Hot` | — | gold 半透明底 |
| `Badge/Status` | none, generating, ready, partial, failed | 见 §3.1 |
| `Card/Match` | default, hover | 含热门 optional |
| `Tab/Item` | active, inactive | 底边 2px |
| `Chat/Bubble` | agent-{role} | 7 角色色 |
| `Certificate/Table` | — | 三行玩法 + 表头 |
| `Filter/Select` | default, open | 下拉示意 |

**Auto Layout**：卡片、列表、Chat 均纵向 Auto Layout + `gap` token。

---

## 6. 交互说明（Prototype）

| 热区 | 动作 | 目标 |
|------|------|------|
| MatchCard | Click | `02-详情-战术室-*` |
| Tab | Click | 切换对应画板 |
| `← 返回赛程` | Click | `01-赛程-默认` |
| 重新发起合议 | Click | 切到 `生成中` 画板（延时 0.3s） |
| ReadModeToggle | Click | 速览隐藏时间线，仅证书+Edge |

---

## 7. 与 Cursor Figma MCP 的衔接（Agent 建稿）

当 **Settings → MCP → Figma** 状态为 Connected 后，可对 Agent 说：

1. `whoami` 获取 `planKey`
2. `create_new_file`：`世界杯AI战术室-暗色-v1`，`editorType: design`
3. `use_figma` + 按本文 §0–§5 创建页面与画板

**若 MCP 持续 errored**：在 Figma 桌面端确认已登录 → Cursor 重载窗口 → 检查 Figma 插件/Remote MCP 授权。

---

## 8. 验收清单（设计稿完成标准）

- [ ] 3 个主流程画板：赛程默认、详情共识、详情生成中
- [ ] Token 页与现网 `tailwind.config.ts` 色值一致
- [ ] MatchCard 五种状态胶囊齐全
- [ ] 战术室含证书表 + Edge 表 + 至少 3 条 Chat 示例
- [ ] 全局 Header / Footer 与 PRD 免责声明一致
- [ ] 组件库可覆盖 80% 现网 `components/` 结构

---

## 9. 参考（现网结构，不改代码）

| 区域 | 代码路径 |
|------|----------|
| 赛程首页 | `apps/web/app/page.tsx` |
| 详情页 | `apps/web/app/match/[matchId]/page.tsx` |
| 比赛卡 | `apps/web/components/schedule/MatchCard.tsx` |
| 战术室 | `apps/web/components/war-room/WarRoomPanel.tsx` |
| 主题色 | `apps/web/tailwind.config.ts`、`globals.css` |

**文档版本**：v1 · 2026-05-24
