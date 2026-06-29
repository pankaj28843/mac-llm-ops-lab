from pathlib import Path


def test_observability_docs_describe_phoenix_and_prompt_safety() -> None:
    docs_path = Path("docs/evidence.md")

    assert docs_path.exists()
    text = docs_path.read_text(encoding="utf-8")
    operations = Path("docs/operations.md").read_text(encoding="utf-8")
    combined = "\n".join([text, operations])
    combined_flat = " ".join(combined.split())

    for required in (
        "OpenTelemetry",
        "Phoenix",
        "MAC_LLM_OPS_OTEL_ENABLED",
        "MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "http://127.0.0.1:26006/v1/traces",
        "http://phoenix:6006/v1/traces",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "mac_llm_ops.stream.cancelled",
        'gen_ai.response.finish_reasons=("cancelled",)',
        "db.transaction.outcome",
        "does not capture prompts",
        "artifacts/runtime/2026-06-28T160713+0200-phoenix-otel/",
        "artifacts/runtime/2026-06-28T173605+0200-vllm-mlx-phoenix-real-backend/",
        "openai-compatible",
        "Phoenix proof",
    ):
        assert required in combined_flat
