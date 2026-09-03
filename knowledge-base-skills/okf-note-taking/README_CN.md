# OKF Note-Taking Skill

一个可复用的 [Kimi Code skill](https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html) 和 CLI 辅助工具，用于以 [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/open-knowledge-format) v0.2 的形式创建、关联和维护学习笔记。

它将每条笔记视为一个 OKF **概念**（带有 YAML frontmatter 的 markdown 文件），并组织在一个基于目录的 **bundle** 中，同时自动化处理保持 bundle 整洁可靠的各种琐事。

---

## 功能特性

- **一个概念 = 一个 `.md` 文件**，并包含必需的 YAML frontmatter（`type`、`title`、`description`、`tags`、`status`、`generated`）。
- **Bundle 脚手架**：通过 `init` 命令创建 `topics/`、`references/`、`computations/` 及其索引。
- **概念创建**：通过 `new` 命令创建笔记，并自动更新最近的 `index.md` 和 `log.md`。
- **笔记关联**：通过 `link` 命令在 `# Related notes` 中插入 bundle 相对路径链接。
- **图片附加**：通过 `attach` 命令将媒体复制到 `assets/`，并可选择记录到 frontmatter 中。
- **索引重建**：通过 `index` 命令保持目录列表最新。
- **合规检查**：通过 `check` 命令检查 frontmatter、脚注、本地图片和保留文件名。
- **Git LFS 设置**：通过 `lfs-setup` 命令将二进制资源排除在 git 历史之外。

---

## 目录结构

```text
okf-note-taking/
  SKILL.md              # Skill 入口（YAML frontmatter + Agent 指令）
  README.md             # 英文版说明
  README_CN.md          # 中文版说明（本文件）
  pyproject.toml        # Python 包元数据
  scripts/
    okf_notes.py        # CLI 辅助工具（init、new、link、attach、index、check、log、lfs-setup）
  references/
    WORKFLOW.md         # 详细的分步工作流
    COMMANDS.md         # CLI 命令参考
    LFS.md              # Git LFS 设置指南
    TEMPLATES.md        # 模板使用指南
  assets/
    concept-template.md # OKF 概念笔记模板
    index-template.md   # 目录索引模板
    log-template.md     # 更新日志模板
```

生成的 OKF bundle 结构如下：

```text
my-notes/
  .gitattributes        # Git LFS 规则（可选）
  index.md              # 根目录列表；可声明 okf_version: "0.2"
  log.md                # 更新历史
  topics/               # 主题笔记
    index.md
    backpropagation.md
  references/           # 外部来源镜像
    index.md
  computations/         # 可复现计算
    index.md
  assets/               # 附加媒体
    topics/
      backpropagation/
        gradient-flow.png
```

---

## 模块说明

| 文件 / 目录 | 作用 |
|------------|------|
| `SKILL.md` | Skill 入口。包含触发信号、核心原则、标准布局、工作流、媒体规范和 Agent 指令。 |
| `pyproject.toml` | Python 打包元数据。声明依赖并注册 `okf-notes` 控制台脚本。 |
| `scripts/okf_notes.py` | 核心 CLI 辅助工具。实现所有命令以及处理 frontmatter、更新索引、记录日志和 Git LFS 属性的工具函数。 |
| `references/WORKFLOW.md` | 初始化 bundle、创建笔记、关联笔记、附加图片、重建索引、检查合规性和设置 Git LFS 的详细工作流。 |
| `references/COMMANDS.md` | 每个 CLI 子命令及其选项的快速参考。 |
| `references/LFS.md` | 将 `assets/` 通过 Git LFS 管理的指南，包含生成的 `.gitattributes` 内容。 |
| `references/TEMPLATES.md` | frontmatter 字段说明以及如何使用 bundle 内模板。 |
| `assets/concept-template.md` | 单个 OKF 概念笔记模板。 |
| `assets/index-template.md` | 目录索引页模板。 |
| `assets/log-template.md` | 更新日志页模板。 |

---

## 安装

### 作为 Kimi Code skill

复制或符号链接此目录到 Kimi Code skills 目录：

```bash
cp -r okf-note-taking ~/.kimi-code/skills/
```

然后调用：

```text
/skill:okf-note-taking create backpropagation
```

### 作为 Python CLI 工具

```bash
cd okf-note-taking
pip install -e .
```

这将安装 `okf-notes` 命令：

```bash
okf-notes --help
```

---

## 快速开始

```bash
# 1. 初始化新的笔记 bundle
okf-notes init my-learning-notes --name "My Learning Notes"
cd my-learning-notes

# 2. 创建概念笔记
okf-notes new topics/backpropagation.md \
    --title "Backpropagation" \
    --description "How gradients flow backward" \
    --tags ml neural-networks

# 3. 附加图片
okf-notes attach topics/backpropagation.md \
    --file ~/Downloads/gradient-flow.png \
    --caption "Gradient flow through a network" \
    --record

# 4. 链接到另一篇笔记
okf-notes link topics/backpropagation.md --to topics/neural-networks.md

# 5. 重建索引并检查
okf-notes index --regenerate
okf-notes check
```

---

## 文档索引

- `SKILL.md` — Agent 核心指令。
- `references/WORKFLOW.md` — 包含输入输出示例和边界情况的详细工作流。
- `references/COMMANDS.md` — CLI 命令参考。
- `references/LFS.md` — Git LFS 设置指南。
- `references/TEMPLATES.md` — 模板使用指南。
- `assets/` — 可直接复制的模板。

---

## 依赖

- Python >= 3.11
- PyYAML >= 6.0

当直接通过 `python scripts/okf_notes.py` 调用时，`init`、`new`、`log` 和 `attach` 核心命令只需要 Python 标准库。`link`、`index` 和 `check` 命令需要 PyYAML。

---

## 许可证

Apache-2.0
