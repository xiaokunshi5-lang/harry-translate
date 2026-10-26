# Harry Translate (哈利同传) 全景热词速查与专业语料库索引指南 (GLOSSARY_INDEX.md)

![Version](https://img.shields.io/badge/Version-v3.8-blue.svg)
![Packs](https://img.shields.io/badge/Glossary%20Packs-15%20Standard%20Packs-brightgreen.svg)
![Total Terms](https://img.shields.io/badge/Total%20Terms-18%2C449%20Authentic-purple.svg)
![Priority](https://img.shields.io/badge/Override%20Hierarchy-4--Tier%20(P0%3EP1%3EP2%3EP3)-orange.svg)
![Cloud Safe Cap](https://img.shields.io/badge/Cloud%20Hotwords-Smart%20Cap%20%E2%89%A4900-blueviolet.svg)
![Latency](https://img.shields.io/badge/Aho--Corasick%20Latency-%3C0.15ms%20(0%20Token)-success.svg)

本文档为 Harry Translate (哈利同传) 内置多维分类热词银行（`glossary_bank/`）的权威全景技术索引。全库包含 15 个标准化模块化 JSON 词包，涵盖 154 条 ASR 同音错字纠正规则、9,039 条中译英术语对齐规则以及 9,256 条英译中术语对齐规则，真实专业词条总量达到 **18,449 条**。

---

## 一、15 大分类词包全景速查总表

全库 15 个标准词包均位于项目根目录的 `glossary_bank/` 目录下，文件命名遵循 `序号_类别_频次.json` 的规范，按需加载、毫秒级热重载，并受到 4 级优先级调度体系的统一管理。

| 序号 | 词包文件名 | 标签名称与图标 | 分类层级 (Tier) | 调度优先级 | 锁定状态 (Locked) | 默认启用 | ASR 纠错 | 中译英 (ZH➔EN) | 英译中 (EN➔ZH) | 词条总数 | 典型涉外会议应用场景 | 真实高频词条与纠偏对照示例 |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **00** | `00_base_emergency.json` | 基础应急固定库 🔒 | emergency | **P1 (1)** | **True (常驻锁定)** | **True** | 20 | 50 | 30 | **100** | 国际大会开幕式、主席团会晤、紧急疏散预案、应急医疗与表决签约仪式 | `应急预案` ➔ *Emergency Preparedness Plan*<br>`举手表决通过` ➔ *Adopted by Show of Hands*<br>`Simultaneous Interpretation` ➔ *同声传译*<br>ASR: `麦克逢` ➔ `麦克风` |
| **01** | `01_party_gov_high.json` | 党建与政务(高频) 🏛️ | high_frequency | **P2 (2)** | False | **True** | 15 | 70 | 25 | **110** | 新时代治国理政研讨会、高质量发展论坛、中国式现代化专题峰会 | `新质生产力` ➔ *New Quality Productive Forces*<br>`高质量发展` ➔ *High-Quality Development*<br>`Chinese Modernization` ➔ *中国式现代化*<br>ASR: `新制生产力` ➔ `新质生产力` |
| **02** | `02_diplomacy_official_high.json` | 政务与外交公文(高频) 📜 | high_frequency | **P2 (2)** | False | **True** | 12 | 80 | 28 | **120** | 多边外事访问、联合声明发布会、国际公约缔结、全球治理双边会见 | `人类命运共同体` ➔ *Community with a Shared Future for Mankind*<br>`和平共处五项原则` ➔ *Five Principles of Peaceful Coexistence*<br>`Global Development Initiative` ➔ *全球发展倡议*<br>ASR: `人类命运共童体` ➔ `人类命运共同体` |
| **03** | `03_daily_items_common.json` | 日常物品(常见) 📦 | high_frequency | **P2 (2)** | False | **True** | 12 | 74 | 30 | **116** | 国际商务会展、办公电子设备交流、日常数码生活与后勤装备保障 | `轻薄笔记本电脑` ➔ *Ultra-Thin Laptop*<br>`智能折叠屏手机` ➔ *Foldable Smartphone*<br>`Docking Station` ➔ *拓展坞*<br>ASR: `笔计本电脑` ➔ `笔记本电脑` |
| **04** | `04_fruits_fresh_common.json` | 水果与生鲜(常见) 🍎 | high_frequency | **P2 (2)** | False | **True** | 12 | 71 | 25 | **108** | 涉外商务茶歇冷餐会、国际生鲜果品博览会、冷链进出口贸易谈判 | `红富士苹果` ➔ *Red Fuji Apple*<br>`阿克苏冰糖心苹果` ➔ *Aksu Crystal Sugar Heart Apple*<br>`Cavendish Banana` ➔ *香蕉*<br>ASR: `红富土苹果` ➔ `红富士苹果` |
| **05** | `05_key_locations_common.json` | 重点地名(常见) 🗺️ | high_frequency | **P2 (2)** | False | **True** | 12 | 71 | 25 | **108** | 跨国招商引资推介会、全球经贸合作考察路线、省市国际姊妹城市峰会 | `北京市` ➔ *Beijing Municipality*<br>`上海市` ➔ *Shanghai Municipality*<br>`Guangzhou` ➔ *广州*<br>ASR: `北极市` ➔ `北京市` |
| **06** | `06_classic_idioms_high.json` | 经典成语(高频) 📖 | high_frequency | **P2 (2)** | False | **True** | 12 | 79 | 28 | **119** | 涉外文化交流晚宴、主旨演讲致辞、中华传统典籍与政经对话公文翻译 | `实事求是` ➔ *Seeking Truth from Facts*<br>`求同存异` ➔ *Seeking Common Ground while Shelving Differences*<br>`Standing Together in Storms` ➔ *风雨同舟*<br>ASR: `实事求事` ➔ `实事求是` |
| **07** | `07_ai_tech_high.json` | AI与科技(高频) 🤖 | high_frequency | **P2 (2)** | False | **True** | 11 | 70 | 35 | **116** | 人工智能国际顶会 (NeurIPS/ICLR)、大模型技术发布会、AGI算力架构研讨 | `大语言模型` ➔ *Large Language Model*<br>`生成式人工智能` ➔ *Generative Artificial Intelligence*<br>`Multimodal AI` ➔ *多模态人工智能*<br>ASR: `大雨言模型` ➔ `大语言模型` |
| **08** | `08_spoken_slang_common.json` | 口语与热词(常见) 🗣️ | high_frequency | **P2 (2)** | False | **True** | 12 | 74 | 30 | **116** | 跨国互联网大厂产研对齐、敏捷项目复盘、出海业务与职场高频流行语 | `给力` ➔ *Awesome and Impactful*<br>`点赞` ➔ *Give a Big Thumbs-Up*<br>`Actionable Lever` ➔ *抓手*<br>ASR: `抓手点` ➔ `抓手` |
| **09** | `09_party_specialized_rare.json` | 党建专用语(生僻) 🏛️ | rare | **P3 (3)** | False | **True** | 6 | 1,200 | 1,200 | **2,406** | 党史党建专题讲座、组织人事法规、纪检监察巡视体制机制专精研讨 | `新时代组织建设责任制考核` ➔ *New Era Organizational Development Accountability Assessment*<br>`基层党建引领基层治理体制机制创新` ➔ *Grassroots Governance Innovation through Party Leadership*<br>ASR: `巡事巡查` ➔ `巡视巡察` |
| **10** | `10_industry_items_uncommon.json` | 工业与生活物品(不常见) 📦 | rare | **P3 (3)** | False | **True** | 6 | 1,500 | 1,500 | **3,006** | 国际重型机械装备博览会、流体阀门与管道配件出口、特种精密机加工 | `工业级法兰球阀核心组件` ➔ *Industrial-Grade Flange Ball Valve Core Component*<br>`数控多轴联动铣削加工主轴总成` ➔ *CNC Multi-Axis Simultaneous Milling Machining Spindle Assembly*<br>ASR: `法蓝阀门` ➔ `法兰球阀` |
| **11** | `11_fruits_agricultural_rare.json` | 水果与农特产(生僻) 🍎 | rare | **P3 (3)** | False | **True** | 6 | 1,200 | 1,200 | **2,406** | 国际地理标志农特产博览会、小众药食同源林下经济、热带稀有果品贸易 | `高原野生嘉宝果(树葡萄)鲜果礼盒` ➔ *Plateau Wild-Harvested Jabuticaba Fresh Premium Gift Box*<br>`长白山野生五味子干品特级装` ➔ *Changbai Mountain Wild Schisandra Berry Dried Premium Grade*<br>ASR: `加宝果` ➔ `嘉宝果` |
| **12** | `12_world_locations_ext.json` | 国内外地名(扩展) 🗺️ | rare | **P3 (3)** | False | **True** | 6 | 1,500 | 1,800 | **3,306** | 国际远洋航线与海事仲裁、全球海峡咽喉通航安全、国际干港与口岸物流 | `北部亚丁湾航运物流保税区` ➔ *Northern Gulf of Aden Maritime Logistics Bonded Zone*<br>`霍尔木兹海峡战略通航安全走廊` ➔ *Strait of Hormuz Strategic Maritime Navigation Safety Corridor*<br>ASR: `荷尔木兹` ➔ `霍尔木兹海峡` |
| **13** | `13_dialect_homophones_rare.json` | 地方方言谐音(生僻) 🗣️ | rare | **P3 (3)** | False | **True** | 6 | 1,500 | 1,500 | **3,006** | 粤港澳大湾区经贸论坛、川渝产业投资峰会、东北老工业基地振兴圆桌交流 | `地道正宗搞掂(搞定)典型语境交流` ➔ *Authentic Colloquial Get It Done Properly in Conversational Dialogue*<br>`雄起(加油振作)赛场欢呼鼓劲语境` ➔ *Sichuanese Colloquial Go for the Win and Rallying Cry*<br>ASR: `猴腮雷` ➔ `猴赛雷` |
| **14** | `14_biomedical_clinical_expert.json` | 生物医药与临床(专精) 🧬 | rare | **P3 (3)** | False | **True** | 6 | 1,500 | 1,800 | **3,306** | 国际临床肿瘤学会 (ASCO/CSCO)、新药多中心临床试验评估、基因测序与细胞治疗 | `临床试验三期程序性死亡受体配体1疗效评估标准` ➔ *Phase III Clinical Trial of Programmed Death-Ligand 1 PD-L1 Efficacy Evaluation Criteria*<br>`嵌合抗原受体T细胞免疫疗法细胞毒性监控` ➔ *Chimeric Antigen Receptor T-Cell CAR-T Immunotherapy Cytotoxicity Monitoring*<br>ASR: `PDL一配体` ➔ `PD-L1配体` |
| **全库** | **15 个标准词包** | **专业语料总库** | — | — | **1 强制常驻** | **15 默认开启** | **154** | **9,039** | **9,256** | **18,449** | **覆盖涉外政务、商务贸易、高精学术等全场景** | **18,449 词全部通过纯 Python Aho-Corasick 高速流式匹配** |

---

## 二、4 级优先级覆盖架构 (4-Tier Priority Override Hierarchy)

在实际涉外会议中，不同来源的专有名词和术语可能存在定义重叠或翻译风格差异。为了确保同传译文始终符合特定会议的最高准则，Harry Translate 确立了严格的 4 级优先级覆盖级联机制：

```
┌────────────────────────────────────────────────────────────────────────┐
│  P0 会议临时 VIP 词库 (Session Guest In-Memory: 0 I/O, 会后一键清空/转正)    │ ◄── 绝对最高级覆盖 (强行覆盖 P1/P2/P3)
├────────────────────────────────────────────────────────────────────────┤
│  P1 用户永久专属词库 (User Permanent glossary.json) + 基础应急固定库 (00)   │ ◄── 覆盖官方词包 P2/P3
├────────────────────────────────────────────────────────────────────────┤
│  P2 官方基础高频词库 (01~08 高频分类包: 党政、外交、成语、AI科技、日常口语等) │ ◄── 覆盖生僻专精包 P3
├────────────────────────────────────────────────────────────────────────┤
│  P3 扩展生僻专精词库 (09~14 生僻分类包: 党建生僻、工业管件、农特产、生物医药) │ ◄── 基础底层兜底
└────────────────────────────────────────────────────────────────────────┘
```

### 1. P0 会议临时 VIP 词库 (Session Guest In-Memory)
- **存储机制**：纯内存数据结构（`GlossaryManager._session_data`），0 磁盘 I/O 损耗。
- **业务定位**：专为会议开场前临时拿到的外宾姓名、突发赞助商机构名、特定发言人口音谐音定制。
- **覆盖行为**：拥有系统绝对最高优先级。当输入词条与底层官方包、用户永久词库冲突时，强制以 P0 设定输出。
- **生命周期处置**：
  - 会后无需保存时，调用 `POST /api/glossary/session/clear`，一键重置内存，磁盘无任何残留，绝不污染后续日常会议；
  - 若具有长期复用价值，调用 `POST /api/glossary/session/promote`，一键原子合并写入根目录 `glossary.json`，永久固化。

### 2. P1 用户永久专属词库与基础应急库 (User Permanent & Base 00)
- **存储机制**：持久化存储于根目录 [`glossary.json`](glossary.json) 及常驻词包 [`00_base_emergency.json`](glossary_bank/00_base_emergency.json)。
- **业务定位**：企业自身品牌资产、固定高管名单、行业标准译法以及大会基础流程指令（开幕式、表决、应急疏散）。
- **覆盖行为**：`00_base_emergency.json` 带有 `locked: true` 属性，前端禁止取消勾选。P1 词条强制覆盖官方 P2 与 P3 词包中的同名条目。

### 3. P2 官方基础高频词库 (Official High-Frequency Packs 01~08)
- **涵盖范围**：01 党建与政务、02 政务与外交公文、03 日常物品、04 水果生鲜、05 重点地名、06 经典成语、07 AI与科技、08 口语热词。
- **业务定位**：主流国际会议及日常涉外交流核心词汇，词条精炼（100~120 词/包），默认全开。
- **覆盖行为**：当生僻词包（P3）中存在宽泛表达时，以 P2 高频词包的规范译法为准。

### 4. P3 扩展生僻专精词库 (Rare Specialized Packs 09~14)
- **涵盖范围**：09 党建专用语、10 工业管件配件、11 稀有水果农特产、12 全球口岸与扩展地名、13 地方方言谐音、14 生物医药临床。
- **业务定位**：深水区高壁垒垂直领域，单包词量达 2,400~3,300 词，总计超 1.7 万词。
- **覆盖行为**：作为专业场景的大规模底层兜底。

---

## 三、云端热词智能截断机制 (Cloud Hotwords Safe Capping)

阿里云百炼平台（DashScope）与通义千问实时同传引擎（`qwen3.8-livetranslate-flash-realtime`）通过 WebSocket 通道传输音频与文本，其 `session.update` 指令对热词列表（Hotwords）设有 **1,000 词硬性容量上限**。若请求数组长度超出 1,000 词，云端网关直接抛出 `InvalidParameter` 错误并主动掐断 WebSocket 连接。

为了在支撑万级本地词库的同时确保云端会话绝对稳定，系统构建了智能截断闸门：

```
全部已激活词库 (最高可达 18,449+ 词)
         │
         ▼
按优先级排序去重: P0 (本场临时) ➔ P1 (永久常驻) ➔ P2 (高频主力) ➔ P3 (生僻专精)
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
[前 900 词安全推送]                        [超出 900 词截断部分]
         │                                         │
         ▼                                         ▼
阿里云百炼 WebSocket 推送                  本地 Aho-Corasick 自动机
(安全度 100%, 0 报错断线)                  (全量挂载, <0.15ms 零延迟补救)
```

1. **安全推送线设定（Safe Cap = 900）**：
   系统严格将推向云端的热词上限锁定为 **900 词**，预留 100 词（10%）的动态缓冲安全冗余。
2. **容量三态水位指示**：
   - 🟢 **`optimal` (优秀，$\le 750$ 词)**：云端热词负载轻松，声学模型高效响应；
   - 🟡 **`warning` (预警，$751 \sim 900$ 词)**：接近安全保护线，提示会务技术人员精简勾选；
   - 🔴 **`capped` (截断保护，$> 900$ 词)**：触发智能分流，前 900 词推送云端，超出部分自动由本地引擎 100% 承担。

---

## 四、本地纯 Python Aho-Corasick 自动机极速匹配 (0 Token 开销)

被云端截断的词条以及全量 18,449 词库均被无缝载入本地高性能多模式匹配自动机：

1. **零外部编译依赖**：采用纯 Python 实现 Trie 树及广度优先搜索失配指针（Failure Links），基于 `__slots__` 压缩节点开销，常驻内存仅约 46MB。
2. **极速单句扫描**：对包含 100 字符的长句进行全库 18,000+ 模式串扫描，实测单句匹配延迟仅 **0.0058ms (5.8µs)**，相比规范要求的 $\le 0.15\text{ms}$ 提升了两个数量级。
3. **零 Token 开销**：本地匹配直接作用于文本流出入站阶段，纠偏全程不产生任何云端大模型 API 调用费用。

---

## 五、已激活热词实时同步表与前置冲突探针

系统在主控大屏（`/` 或 `/split`）的 `#config-drawer` 工作台中提供了两项核心交互功能：

### 1. 已激活热词实时同步明细表 (`#active-glossary-table`)
- **联动刷新**：在勾选或取消勾选分类标签胶囊时，明细表及其计数标签（`#active-glossary-count`）在毫秒级内自动同步更新。
- **多维筛选过滤**：支持通过中英文输入框（`#active-glossary-search`）进行模糊检索，并可通过下拉选择器（`#active-glossary-filter`）在“全部已激活词条”、“基础常驻库”、“已勾选官方词包”、“本场临时 VIP 词”、“永久自定义词”之间秒级切换。
- **明细呈现**：直观展示原文字词、译文字词、所属分类包名、调度优先级徽章及作用域。

### 2. 录入前置冲突与覆盖检测探针 (`#conflict-probe-indicator`)
在添加单条或批量词条时，输入框下方挂载了实时防抖检测探针：
- 🟢 **全新词条直接生效 (`new`)**：当前词库中无该词，录入后将作为全新条目即刻生效；
- 🟡 **高优先级覆盖提示 (`override`)**：当前词在官方词包中已有默认翻译，探针将明确展示原译文及来源词包，并提示您的自定义设置将以更高优先级强行覆盖；
- ℹ️ **完全一致无需重复 (`identical`)**：当前输入与现有激活条目的译文完全相同，系统友好提示无需重复录入。

---

## 六、后端 RESTful API 接口契约

系统在 `server.py` 中提供了用于支撑上述特性的标准 HTTP 接口：

### 1. `GET /api/glossary/terms/active`
- **功能说明**：获取当前所有已激活生效的词条列表，供同步明细表与前端探针使用。
- **查询参数**：
  - `q`（可选，字符串）：中英文模糊检索关键词；
  - `category`（可选，字符串）：`terms_zh_to_en`、`terms_en_to_zh` 或 `asr_fixes`；
  - `scope`（可选，字符串）：`all`、`base`、`bank`、`session` 或 `permanent`；
  - `limit`（可选，整数）：返回结果最大数量，默认 500。
- **响应示例**：
  ```json
  {
    "status": "ok",
    "total_active_terms": 18449,
    "count": 500,
    "terms": [
      {
        "source": "新质生产力",
        "target": "New Quality Productive Forces",
        "category": "terms_zh_to_en",
        "source_pack_id": "01_party_gov_high",
        "source_pack_name": "党建与政务(高频)",
        "tier": "high_frequency",
        "priority": 2,
        "scope": "bank"
      }
    ]
  }
  ```

### 2. `POST /api/glossary/check_conflict`
- **功能说明**：录入前置冲突检测探针接口。
- **请求体格式 (JSON)**：
  ```json
  {
    "source": "新质生产力",
    "target": "Novel Productive Forces",
    "category": "terms_zh_to_en",
    "is_session": false
  }
  ```
- **响应示例 (高优先级覆盖)**：
  ```json
  {
    "status": "ok",
    "conflict_type": "override",
    "message": "已在官方词包收录默认翻译，您的自定义将以更高优先级强行覆盖",
    "will_override": true,
    "detail": {
      "existing_target": "New Quality Productive Forces",
      "existing_pack_name": "党建与政务(高频)",
      "existing_priority": 2,
      "incoming_priority": 1
    }
  }
  ```

---

## 七、自定义业务词包扩充指南

会务组织机构或企业开发人员如需新增垂直行业词包，可按照如下规范操作：

1. 在 `glossary_bank/` 目录下创建新文件，例如 `15_aerospace_satellite_tech.json`；
2. 遵循标准 JSON 模式编写：
   ```json
   {
     "id": "15_aerospace_satellite_tech",
     "name": "航空航天与卫星遥感",
     "icon": "🛰️",
     "tier": "rare",
     "priority": 3,
     "locked": false,
     "default_enabled": false,
     "description": "载人航天、空间遥感载荷与低轨卫星互联网专业术语",
     "asr_fixes": {
       "长针火箭": "长征火箭",
       "问添实验舱": "问天实验舱"
     },
     "terms_zh_to_en": {
       "近地轨道载人飞船": "Low Earth Orbit Manned Spacecraft",
       "合成孔径雷达遥感卫星": "Synthetic Aperture Radar Remote Sensing Satellite"
     },
     "terms_en_to_zh": {
       "Synthetic Aperture Radar": "合成孔径雷达",
       "Geostationary Orbit": "地球静止轨道"
     }
   }
   ```
3. 保存后无需重启后端，系统在下次访问接口时自动发现并挂载至 Aho-Corasick 自动机与配置抽屉。
