# LINE 接入边界

## 当前已实现

- 使用 Channel secret 对原始 webhook 请求体进行 HMAC-SHA256 验证
- 使用常量时间比较检查 `x-line-signature`
- 只接受白名单群组中的文本消息
- 可选成员白名单
- webhook结构化`@机器人`是首选触发方式
- 可配置的单字母前缀作为备用，只在句首触发
- 普通聊天静默忽略
- Reply API纯文本客户端

## 安全要求

1. 必须对未经修改的原始请求体验证签名，然后才能解析JSON。
2. 不要用来源IP白名单代替签名验证。
3. 生产环境必须配置允许的群组ID。
4. Channel secret和access token只能由环境变量或受限密钥文件提供。
5. 不记录完整消息正文、access token或成员标识符。
6. Reply token只用于对应事件的一次回复。

## 官方资料

- [Verify webhook signature](https://developers.line.biz/en/docs/messaging-api/verify-webhook-signature/)
- [Receive messages](https://developers.line.biz/en/docs/messaging-api/receiving-messages/)
- [Group chats and multi-person chats](https://developers.line.biz/en/docs/messaging-api/group-chats/)
- [Messaging API reference](https://developers.line.biz/en/reference/messaging-api/)
