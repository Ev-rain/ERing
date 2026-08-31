# 安全说明（Security）

## 报告漏洞

请**不要**在公开 Issue 中提交涉及安全的问题。可通过 GitHub 的
[Security Advisories](https://github.com/<your-user>/ERing/security/advisories/new)
功能或直接联系维护者私下报告。

## 已知注意事项

- 程序需要**全局鼠标钩子**才能实现右键轮盘，部分杀毒软件可能误报；
  发布版已内置钩子 DLL（`native\wheelhook.dll`），建议使用前加白名单；
- 以**普通权限**运行时，无法在管理员权限（UAC 提权）的窗口中使用钩子，
  请以管理员身份运行；
- `data\settings.json` 中保存的 **DeepSeek API Key 为明文**，请勿分享该文件，
  也不要把它提交到任何仓库（`.gitignore` 已排除 `data/`）。

## 依赖更新

依赖版本见 `src\ERing\requirements.txt`；请定期更新以获取安全修复。
