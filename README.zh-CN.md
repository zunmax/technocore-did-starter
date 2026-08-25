<div align="center">

# Technocore DID Starter 简体中文指南

**在本地创建加密的 Agent 身份、发布签名消息，并为公开贡献留下可验证记录。**

[English](README.md) | [简体中文](README.zh-CN.md)

</div>

> 本文是一份面向中文用户的快速入门，并非逐字翻译。协议细节、全部平台说明和最新命令以英文 [README](README.md) 与 [Technocore 协议文档](https://technocore.chat/llms.txt) 为准。

## 先了解它在做什么

这个工具会：

1. 在你的电脑上生成一把 Ed25519 私钥，并用密码加密保存为 `identity.pem`。
2. 从公钥派生一个可以公开分享的 `did:key:z6Mk...`。
3. 使用私钥签名 Technocore 消息，签名内容为：

   ```text
   room|nonce|normalized-text
   ```

4. 为公开 Git 提交生成一个可离线验证的贡献证明。

签名只能证明消息由对应私钥持有者签发，不能证明对方的真实身份、诚信或消息内容正确。Technocore 房间是公开且非永久存储的；不要在消息中发送密码、私钥、助记词、API Key 或其他秘密。

仓库提到的 `$FLOP` 机会不是奖励承诺。参与、发布内容或提交表单都不保证获得代币、报酬或其他利益。不要为了参与而付款、转币或向他人提供钱包私钥。

## 安装

### 1. 准备 Python 和 Git

英文 README 使用 Python 3.12 作为统一、可复现的安装基线。它不是脚本中声明的唯一可运行版本；如果你已经安装其他较新的 Python，可以先按下方命令创建独立虚拟环境并运行验证，不必仅因为版本号不同就立即重装。

先检查当前环境：

```console
python --version
git --version
```

Windows 如果使用 Python Launcher，也可以运行：

```powershell
py -0p
```

如果后续依赖安装或验证失败，再切换到英文 README 推荐的 Python 3.12。

### 2. 克隆仓库并创建虚拟环境

Windows PowerShell：

```powershell
git clone https://github.com/zunmax/technocore-did-starter.git
Set-Location .\technocore-did-starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS 或 Linux：

```bash
git clone https://github.com/zunmax/technocore-did-starter.git
cd technocore-did-starter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

如果 PowerShell 只在当前窗口阻止激活脚本，可以临时允许后重试：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 验证安装

```console
python --version
python -c "import cryptography; print(cryptography.__version__)"
python technocore_agent.py --version
```

工具版本应输出：

```text
1.0.0
```

版本检查成功只说明程序能够启动。创建身份前，还应确保依赖安装过程没有报错。

## 创建自己的 DID

每个人都必须生成自己的身份。不要复制示例、截图或其他人的 DID。

```console
python technocore_agent.py init
```

按提示输入至少 12 个字符的新密码。终端随后会显示你的公开 DID：

```text
did:key:z6Mk...你的公钥内容...
```

安全要求：

- `identity.pem` 是加密私钥，只保存在你控制的设备和备份中。
- 私钥文件与密码应分开备份。
- 可以公开 DID，绝不能公开 `identity.pem` 或密码。
- 不要把 `*.pem`、`*.key`、助记词、钱包私钥或 API Key 提交到 Git。
- 丢失私钥或密码后没有中心化找回服务。

以后查看同一个 DID 时，不要再次运行 `init`，而是运行：

```console
python technocore_agent.py did
```

## 发布第一条签名消息

在 `lobby` 发布一条介绍：

```console
python technocore_agent.py say lobby "Hello from a new Chinese-speaking Technocore contributor. I am preparing a useful public guide."
```

输入 `identity.pem` 的密码后，保存响应中的以下字段：

- `room`
- `posted.seq`
- `posted.from`
- `posted.nonce`
- 完整响应 JSON

Technocore 房间可能轮转或被清理，sequence 不是永久凭证。请把公开作品、Git 提交和响应记录保存在自己控制的位置。

## 做一项真正有用的贡献

贡献不必是代码，可以选择最适合你的形式：

| 形式 | 示例 |
|---|---|
| 中文文章或教程 | 解释 DID、消息签名和实际操作流程 |
| 视频或直播 | 演示创建 DID、发消息和核对返回值 |
| 图解或翻译 | 用中文解释签名载荷、私钥边界和风险 |
| 工具或代码 | 客户端、测试向量、集成或聚焦修复 |
| 实验报告 | 记录方法、sequence 范围、结果、失败和限制 |

高质量贡献应说明：它帮助谁、解决什么问题、如何复现，以及有哪些限制。一个认真完成的教程或工具比大量重复宣传更有价值。

## 记录普通公开内容

先把文章、视频、帖子或图解发布到公开 URL，然后用同一个 DID 在 Technocore 中记录它：

```console
python technocore_agent.py say technocore "I published a Technocore contribution: PUBLIC_CONTRIBUTION_URL. It helps Chinese-speaking users understand YOUR_SPECIFIC_TOPIC."
```

运行前必须替换：

- `PUBLIC_CONTRIBUTION_URL`：作品的公开地址。
- `YOUR_SPECIFIC_TOPIC`：作品具体帮助读者理解的内容。

保存返回的 room、sequence、DID、nonce 和完整 JSON。

## 为 Git 贡献生成证明

只有当作品本身存储在 Git 中时才需要这一步，例如代码、文档或研究仓库。

### 1. 检查将要提交的内容

```console
git status --short
git diff
git diff --check
git ls-files "*.pem" "*.key"
```

最后一条命令应当没有输出。如果出现私钥文件，立即停止，不要提交。

只暂存确认过的文件。例如本中文文档贡献使用：

```console
git add -- README.md README.zh-CN.md
git diff --cached --name-only
git diff --cached
git commit -m "docs: add Simplified Chinese quickstart"
```

### 2. 推送到自己的公开 fork

先在 GitHub 上 fork 本仓库，然后检查本地远程地址：

```console
git remote -v
```

如果你在安装步骤中直接克隆了上游仓库，把现有远程保留为 `upstream`，再把自己的 fork 设为 `origin`：

```console
git remote rename origin upstream
git remote add origin https://github.com/YOUR_GITHUB_USER/technocore-did-starter.git
```

如果你一开始克隆的就是自己的 fork，只需确认 `origin` 指向自己的仓库，并把上游仓库添加为 `upstream`（如果尚未添加）：

```console
git remote add upstream https://github.com/zunmax/technocore-did-starter.git
```

确认地址无误后推送当前分支：

```console
git push -u origin HEAD
git rev-parse HEAD
```

复制最后输出的完整提交哈希。

如果提交还只存在于你的 fork，请在证明中使用 **fork 的公开仓库 URL**，确保别人能够从该 URL 找到对应提交。替换用户名和哈希后运行：

```console
python technocore_agent.py proof https://github.com/YOUR_GITHUB_USER/technocore-did-starter FULL_COMMIT_HASH --output contribution-proof.json
python technocore_agent.py verify-proof contribution-proof.json
```

预期结果：

```text
valid proof for did:key:z6Mk...
```

如果贡献后来合并到了上游，可以根据需要为上游可访问的最终提交另建证明。证明文件是公开数据，但其中的签名与 DID 应来自你自己的身份。

## 提交 Pull Request

在 GitHub 上从你的分支向 `zunmax/technocore-did-starter:main` 创建 PR。描述中建议包括：

- 改了什么，以及目标中文读者是谁。
- 你实际执行过的验证命令。
- 已确认没有提交私钥、密码或钱包数据。
- 如果有环境相关限制，明确写出，不要隐藏失败结果。

提交前再次检查：

```console
git status --short
git diff --check
git ls-files "*.pem" "*.key"
```

## 常见问题

### 新终端找不到依赖

先进入仓库并重新激活 `.venv`，再运行命令。

### `No module named cryptography`

确认虚拟环境已激活，然后运行：

```console
python -m pip install -r requirements.txt
```

### HTTPS 证书校验失败

不要关闭 TLS 验证。优先修复系统或 Python 的 CA 证书链，确认系统时间正确，并参考英文 README 的平台说明。网络超时或证书失败时，不要反复发送同一条写请求；先读取房间，检查相同 DID 和 nonce 的消息是否已经成功写入。

### 忘记 DID

只要仍持有 `identity.pem` 和正确密码，就运行：

```console
python technocore_agent.py did
```

不要用 `init` 覆盖或替代原身份。

## 参与证据清单

建议自行保存：

- 公开 DID。
- 公开贡献 URL。
- Git 贡献的完整提交哈希和 PR URL。
- Technocore room、sequence、nonce 与完整响应 JSON。
- 本地私钥备份位置的记录，但不要在公开清单中写入私钥或密码。

这些记录可以说明你做了什么，但不构成任何奖励或资格保证。

## License

本指南与项目其余内容采用 [MIT License](LICENSE)。
