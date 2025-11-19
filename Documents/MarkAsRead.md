## はじめに
LINE Official Account における既読仕様に変更があったため、あらためて挙動を整理しました。  
ボット側から既読を付けようとした際に、期待した動作にならず混乱した方の参考になれば幸いです。

## LINE Official Account Manager から設定する
既読の付与は、[LINE Official Account Manager](https://manager.line.biz/account)（ログイン必須）から設定します。

https://manager.line.biz/account

:::note warn
[LINE Developers](https://developers.line.biz/console) からは設定できませんのでご注意ください。
:::

### 自動で既読が付く設定
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/471125/b9d5f923-10f8-4310-91cd-50bab52c76c4.png)

「Webhook のみ」がオンになっている場合、ユーザーからのメッセージには自動的に既読が付きます。  
ただし、この設定は **ボットが実行中かどうかに関係なく既読が付いてしまう** 点に注意が必要です。  
プログラムが起動しておらず Webhook を受け取れない状態であっても、Webhook 自体は送信されるため既読が付いてしまいます。

### 自動で既読が付かない設定
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/471125/ccbf6c5e-2319-424e-b219-5a806e937fb7.png)

「チャット機能」がオンになっている場合、自動では既読が付きません。  
この状態では、後述の Messaging API を使って明示的に既読を付ける必要があります。

## Messaging API を利用して既読を付ける方法
LINE公式ドキュメントでは、既読付与について以下のように案内されています。

https://developers.line.biz/ja/docs/messaging-api/mark-as-read/

### line-bot-sdk-python から既読を付与する例
```python
line_bot_api.mark_messages_as_read_by_token(
    MarkMessagesAsReadByTokenRequest(
        mark_as_read_token=event.message.mark_as_read_token
    )
)
```
:::note warn
この機能を利用するには、**line-bot-sdk-python 3.21.0 以上** が必要です。
同バージョンは 2025年11月初旬にリリース されています。
:::

## おわりに
LINE Bot における既読機能は、以前は申請を行った法人アカウントでのみ利用可能でした。
今回のように既読 API が広く公開されたことで、Bot のユーザー体験をより柔軟に設計できるようになりました。今後の活用の幅が広がることを期待したいところです。