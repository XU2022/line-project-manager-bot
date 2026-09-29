# LINE Project Manager Bot

一个可以部署到LINE群聊的轻量项目管理机器人。它使用确定性规则处理任务，不把普通聊天交给大模型，也不依赖任何特定行业或内容类型。

## 功能

- 验证LINE webhook的HMAC-SHA256签名
- 限制允许使用机器人的群组和成员
- 只有消息以`H:` / `H：`开头或真实`@机器人`时才处理
- 创建、更新、完成、取消和查询通用任务
- 使用SQLite保存任务、成员、事件和提醒记录
- 任务创建者、负责人或管理员才能修改任务
- 在截止日前一天中午提醒负责人
- 优先使用Reply；只有定时提醒使用Push
- 查询LINE月度用量并执行本地消息预算保护
- 防止webhook重投和提醒重复发送
- 提供systemd、Nginx、HTTPS和GitHub Actions示例

## 工作方式

```text
LINE群消息
  → HTTPS webhook
  → 签名验证
  → 群组和成员白名单
  → H:/@机器人门控
  → 确定性任务指令
  → SQLite
  → 单条Reply

systemd timer
  → 检查明日到期任务
  → 检查LINE用量与本地预算
  → 单条Push并@负责人
```

## 要求

- Python 3.11或更高版本
- LINE Official Account及Messaging API channel
- 一个公网HTTPS webhook地址
- Linux部署时推荐systemd与Nginx

运行代码只使用Python标准库。

## 快速验证

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
```

复制示例配置，但不要把填写真实ID后的文件提交到Git：

```bash
cp config/members.example.json config/members.json
cp .env.example .env
```

本项目不会自动读取`.env`。本地运行时请先把变量导入当前shell；systemd部署使用`EnvironmentFile`。

初始化数据库：

```bash
set -a
. ./.env
set +a
line-project-init
```

启动服务：

```bash
line-project-bot
```

本地健康检查：

```bash
curl http://127.0.0.1:8646/healthz
```

生产环境完整步骤见[部署指南](docs/部署指南.md)。

如果还不知道群组ID和成员ID，请先按[LINE官方账号设置](docs/LINE官方账号设置.md)使用一次性引导模式。

## 指令示例

```text
H：新增任务“演示任务”，由我负责，截止10月15日
H：更新 TASK-0001，阶段改为审核
H：TASK-0001 已完成
H：取消 TASK-0001
H：查询当前任务
```

完整说明见[任务指令](docs/任务指令.md)。句子中间偶然出现`H:`不会触发机器人。

## 项目结构

```text
config/       脱敏示例配置和Nginx模板
docs/         LINE接入、指令与部署说明
migrations/   可查看的SQLite结构
src/          可安装Python包
systemd/      webhook服务和提醒timer
tests/        单元、集成、额度与隐私测试
```

## 隐私和安全

仓库只包含虚构成员、任务和LINE标识符。以下内容不得提交：

- Channel secret和access token
- 真实用户ID、群组ID和聊天室ID
- 生产数据库、事件记录和服务器日志
- 真实聊天截图和项目资料
- 私人域名、IP地址和账号路径

`.env`、`config/members.json`、数据库和日志已被`.gitignore`排除。更多信息见[SECURITY.md](SECURITY.md)。

## 测试

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

测试覆盖签名验证、消息门控、权限、任务生命周期、事件去重、提醒去重、额度保护、配置加载、打包schema和公开安全边界。

## 当前版本

当前版本为`0.1.0`。建议先在测试群和测试服务器验证，再用于实际项目群。

## 许可证

本项目采用[MIT License](LICENSE)。
