from types import SimpleNamespace

from services import llm_provider
from services.workflow_service import workflow_service

# The suite-wide fixture mocks the module attribute for unrelated tests; keep
# the real function for this focused provider-routing test.
REAL_CREATE_JSON_CHAT_COMPLETION = llm_provider.create_json_chat_completion


def _response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")]
    )


def test_deepseek_empty_json_fails_over_to_alternate_provider(monkeypatch):
    primary = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: _response("")))
    )
    alternate_calls = []

    def alternate_create(**kwargs):
        alternate_calls.append(kwargs)
        return _response('{"ok":true}')

    alternate = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=alternate_create)))
    monkeypatch.setattr(llm_provider, "_provider_for_client", lambda _client: "deepseek")
    monkeypatch.setattr(llm_provider, "_provider_fallback_order", lambda _provider: ["qwen"])
    monkeypatch.setattr(llm_provider, "_chat_client_for_provider", lambda _provider: alternate)
    monkeypatch.setattr(llm_provider, "_chat_model_for_provider", lambda _provider: "qwen-plus")
    monkeypatch.setattr(llm_provider.time, "sleep", lambda _seconds: None)

    response = REAL_CREATE_JSON_CHAT_COMPLETION(
        messages=[{"role": "user", "content": "health check"}],
        llm_client=primary,
        retries=1,
    )

    assert llm_provider.extract_message_text(response) == '{"ok":true}'
    assert alternate_calls[0]["model"] == "qwen-plus"
    assert "response_format" not in alternate_calls[0]


def test_scene_fallback_exposes_ai_failure_reason(monkeypatch):
    monkeypatch.setattr(
        "services.workflow_service.create_json_chat_completion",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider timeout")),
    )
    monkeypatch.setattr(
        "services.workflow_service.create_text_chat_completion",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("text provider timeout")),
    )
    case_info = {
        "case_name": "测试案件",
        "case_type": "邻里纠纷",
        "persons": [{"name": "张三", "role_type": "相关人员", "status": "正常"}],
    }

    result = workflow_service.generate_scenes(case_info)

    assert result["scene_generation_mode"].startswith("fallback")
    assert "provider timeout" in result["scene_generation_failure_reason"]
    assert "原因：" in result["scene_generation_warning"]


def test_provider_specific_max_tokens_are_clamped(monkeypatch):
    captured = []

    def create(**kwargs):
        captured.append(kwargs)
        return _response('{"ok":true}')

    qwen = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm_provider, "_provider_for_client", lambda _client: "qwen")
    monkeypatch.setattr(llm_provider, "QWEN_MAX_OUTPUT_TOKENS", 32768)
    response = REAL_CREATE_JSON_CHAT_COMPLETION(
        messages=[{"role": "user", "content": "health check"}],
        llm_client=qwen,
        max_tokens=128000,
        retries=1,
    )

    assert llm_provider.extract_message_text(response) == '{"ok":true}'
    assert captured[0]["max_tokens"] == 32768
