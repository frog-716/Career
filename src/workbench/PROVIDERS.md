# Provider 与附件接口

`CAREER_AI_MODE` 必须显式设置为 `LOCAL_ONLY` 或 `AI_ENABLED`；缺失/非法值 fail closed 为 LOCAL_ONLY，启动器会拒绝未显式设置的模式。`LOCAL_ONLY` 下 `get_provider()` 返回禁用 Provider，SecretStore、ModelGateway、真实 Provider 和 Research web search 均拒绝出站并返回 `local_only_disabled`；数据库中已有 `ModelConfig`/`secret_ref`、环境 API Key 或 TestProvider 都不能绕过该门禁。只有 `AI_ENABLED` 才会按显式配置选择 `CAREER_AI_PROVIDER=test` 或真实 OpenAI-compatible Provider。

兼容诊断 Provider 仍可读取旧环境变量，但不再作为业务调用配置；正式模型由 `AI-Config` 从 macOS Keychain 取 Key，并由 `ModelGateway` 调用 `/chat/completions`。请求包含 `model`、`messages`、`response_format: {"type":"json_object"}`；不复用远程会话、不自动重试、不跟随重定向。Base URL 只能是 HTTPS，或 localhost 的 HTTP。

`write_pdf` 使用 reportlab 生成分页 PDF，优先嵌入系统中文 TTF/TTC，找不到时回退 ReportLab `STSong-Light` CID 字体。`write_screenshot` 仅接收 PNG/JPEG Base64，限制 5MB；所有文件均在 `data_dir/artifacts` 内通过临时文件原子改名写入。
