# LINE官方账号设置

## 1. 创建Messaging API channel

在LINE Official Account Manager创建官方账号，再通过LINE Developers Console启用Messaging API。保存以下两项：

- Channel secret
- Channel access token

它们属于生产凭据，只能放在服务器的受限环境文件中。

## 2. 群聊设置

在Messaging API设置中：

- 启用webhook
- 允许机器人加入群聊
- 关闭不需要的默认自动回复，避免与本项目重复回复

将官方账号加入准备使用的LINE群。

## 3. 第一次取得群组和成员ID

新部署时还不知道群组ID和成员ID，可以短暂启用引导模式。

环境文件临时设置：

```text
LINE_ALLOWED_GROUPS=*
LINE_REMINDER_GROUP_ID=*
LINE_BOOTSTRAP_MODE=true
```

只启动`line-project-bot`，不要启用提醒timer。每位准备加入项目的成员在群里发送：

```text
H：身份
```

机器人会在群内回复当前群组ID和发言者成员ID。ID会出现在群聊中，因此只应在受信任的测试群或项目群内进行。

把取得的值写入服务器本地的成员配置和环境文件，然后立即关闭引导模式：

```text
LINE_ALLOWED_GROUPS=C_REAL_GROUP_ID
LINE_REMINDER_GROUP_ID=C_REAL_GROUP_ID
LINE_BOOTSTRAP_MODE=false
```

重新启动服务。非引导模式禁止使用`*`，可以防止遗漏关闭步骤。

## 4. 配置webhook URL

将公网HTTPS地址设置为：

```text
https://line.example.com/webhook
```

使用LINE Developers Console中的Verify功能验证连接。Verify可能发送`events`为空的请求，服务会正常返回HTTP 200。

## 5. 安全边界

- 不要把真实ID写入Git仓库
- 不要在公开群使用引导模式
- 完成身份收集后立即关闭引导模式并重启服务
- 不要在Nginx或应用日志中记录完整webhook正文
- 如果凭据可能泄露，应在LINE Developers Console重新签发

## 官方资料

- [Messaging API overview](https://developers.line.biz/en/docs/messaging-api/overview/)
- [Receive messages](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [Group chats](https://developers.line.biz/en/docs/messaging-api/group-chats/)
- [Verify webhook signature](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
