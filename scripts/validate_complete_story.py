"""One-off validation for complete story generation after prompt update."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SAMPLE = ROOT / "data" / "workflows" / "case-pipeline-705de7fe6dd441e4b64373275bfae758.json"
API_URL = "http://127.0.0.1:8020/v1/case-imports/execute"


def main() -> int:
    payload = json.loads(WORKFLOW_SAMPLE.read_text(encoding="utf-8"))
    source_text = str(payload["response"]["result"]["cleaning"]["cleaned_text"])
    # Use core judgment section to keep validation time reasonable while covering key facts.
    source_text = source_text.split("\n\n上述事实")[0].strip()

    workflow_id = f"validate-story-{uuid.uuid4().hex[:12]}"
    body = json.dumps(
        {
            "workflow_id": workflow_id,
            "case_id": "validate-story",
            "source_text": source_text,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = request.Request(
        API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": f"{workflow_id}-import",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:2000]}")
        return 1
    except Exception as exc:
        print(f"Request failed: {exc}")
        return 1

    if data.get("status") != "succeeded":
        print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
        return 1

    result = data.get("result") or {}
    story = str(result.get("complete_story") or "")
    quality = ((result.get("case_import_quality") or {}).get("story") or {})
    facts = ((result.get("case_import_quality") or {}).get("facts") or {})

    checks = {
        "has_title": story.startswith("# 案件完整剧情"),
        "has_chapters": story.count("## ") >= 2,
        "has_narrative_markers": any(
            marker in story
            for marker in ("场景与心理", "核心冲突", "对峙", "风暴", "尾声", "主线")
        ),
        "covers_key_names": all(name in story for name in ("黎祖新", "黎某1", "黎某3")),
        "covers_key_dates": ("7月19日" in story or "2011年7月19日" in story),
        "story_sufficient": bool(quality.get("sufficient")),
        "facts_sufficient": bool(facts.get("sufficient")),
        "story_chars": len(story),
        "compression_ratio": quality.get("compression_ratio"),
    }

    print("=== 完整剧情验证结果 ===")
    for key, value in checks.items():
        print(f"{key}: {value}")
    print("\n=== 剧情开头（前1200字）===\n")
    print(story[:1200])
    print("\n=== 剧情章节标题 ===")
    for line in story.splitlines():
        if line.startswith("## "):
            print(line)

    failed = [key for key, value in checks.items() if key.endswith("_sufficient") and not value]
    failed += [key for key in ("has_title", "has_chapters", "covers_key_names", "covers_key_dates") if not checks[key]]
    if failed:
        print(f"\n未通过项: {', '.join(failed)}")
        return 1
    print("\n验证通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
