# Provider 与附件接口

`get_provider()` 默认选择真实 Provider；设置 `CAREER_AI_PROVIDER=test` 才会启用确定性的 TestProvider。测试模式只读取本轮 `packet.sources`，诊断中会明确 `mode=test`。

真实 Provider 使用 `CAREER_AI_MODEL`、`CAREER_AI_API_KEY`（或 `OPENAI_API_KEY`）及可选 `CAREER_AI_BASE_URL`。请求为新建的 `/chat/completions` JSON，包含 `model`、`messages`、`response_format: {"type":"json_object"}`；不复用远程会话、不自动重试、不跟随重定向。Base URL 只能是 HTTPS，或 localhost 的 HTTP。

`write_pdf` 使用 reportlab 生成分页 PDF，优先嵌入系统中文 TTF/TTC，找不到时回退 ReportLab `STSong-Light` CID 字体。`write_screenshot` 仅接收 PNG/JPEG Base64，限制 5MB；所有文件均在 `data_dir/artifacts` 内通过临时文件原子改名写入。
