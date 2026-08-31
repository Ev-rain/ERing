# Releases（版本发布）

发布约定参考 [StarPie](https://github.com/SoftBlack42/StarPie)：

- **源码版本**：在 Git 中打 tag（如 `v1.0.0`），GitHub Releases 发布时附加源码归档；
- **可直接运行的分发包**：放在本目录下的 `release<版本号>\` 子文件夹
  （如 `releases\release1.0.0\ERing\`），该目录已加入 `.gitignore`，不会提交到仓库；
- 每个 release 包应包含：完整 one-dir 运行包（exe + `_internal`）+ ffmpeg +
  `使用说明.txt`；
- 在 `CHANGELOG.md` 记录版本变更。
