from services.workflow_service import workflow_service
from services.case_role_reconciliation_service import reconcile_case_roles
from services.persona_soul_service import _persona_context


def _trace(stage: str):
    return {
        "primary_provider": "deepseek",
        "final_provider": "deepseek",
        "switched_provider": False,
        "attempts": [{"provider": "deepseek", "model": "test-long", "mode": "plain_json", "status": "success", "stage": stage}],
    }


def _three_scene_blueprints(*, roles: list[str], fact_id: str = "F1") -> dict:
    definitions = [
        ("S1", "报警核实", "接警", "核实报警情况", "intake", "dispatch_intake"),
        ("S2", "案发后现场核查", "案发后现场处置", "固定现场证据", "post_incident_onsite", "after_canonical_event"),
        ("S3", "案发后调查询问", "案发后调查询问", "核查人员陈述", "post_incident_inquiry", "after_canonical_event"),
    ]
    return {
        "blueprints": [
            {
                "scene_id": scene_id,
                "scene_name": scene_name,
                "scene_kind": scene_kind,
                "training_goal": training_goal,
                "training_entry_phase": phase,
                "entry_time_policy": policy,
                "canonical_outcome_locked": True,
                "student_role": "民警",
                "roles": roles,
                "fact_ids": [fact_id],
                "stages": [{"stage_name": "任务执行", "stage_goal": training_goal}],
            }
            for scene_id, scene_name, scene_kind, training_goal, phase, policy in definitions
        ]
    }


def _scene_script(*, roles: list[str], fact_id: str = "F1") -> dict:
    return {
        "scene_description": "民警依据案件事实完成当前训练任务",
        "difficulty": "中等",
        "dispatch_brief": "收到案件相关警情",
        "first_impression": "案件主要行为已经发生，相关人员等待民警处理",
        "roles": roles,
        "fact_ids": [fact_id],
        "supplement_ids": [],
        "stages": [{"stage_name": "任务执行", "stage_goal": "完成当前任务", "fact_ids": [fact_id]}],
        "script_markdown": "# 民警任务\n依据事实开展处置",
    }


def test_parse_preserves_evidence_offsets_and_story_world(monkeypatch):
    text = "2026年5月10日，张三在东风路看见李四搬走电脑，随后报警。"

    def fake_call(*, stage, **_kwargs):
        if stage == "evidence_extraction":
            return {"facts": [{"content": "张三在东风路看见李四搬走电脑", "fact_type": "行为", "quote": "张三在东风路看见李四搬走电脑", "status": "confirmed"}]}, _trace(stage)
        return {
            "case_name": "电脑被搬走警情",
            "case_type": "盗窃",
            "persons": [{"name": "张三", "role": "报警人", "role_type": "证人"}, {"name": "李四", "role": "相关人员", "role_type": "嫌疑人"}],
            "story_world": {"fact_cards": [{"id": "F1", "content": "张三在东风路看见李四搬走电脑", "fact_type": "行为", "status": "confirmed", "source_refs": [{"source_id": "source-1", "start": 12, "end": 29, "summary": "张三在东风路看见李四搬走电脑"}]}], "simulation_supplements": [{"id": "SIM1", "content": "现场监控正在调取", "purpose": "训练取证流程", "applicable_scene_types": ["现场核查"], "is_scoring_fact": False}]},
        }, _trace(stage)

    monkeypatch.setattr(workflow_service, "_generate_story_from_role_checkpoint", lambda *_args: ("张三在东风路看见李四搬走电脑，随后报警。", _trace("story_assembly")))
    result = workflow_service.parse_case_text(text)
    card = result["story_world"]["fact_cards"][0]
    assert result["parse_engine"] == "ai_text_first"
    assert not any("规则兜底" in warning for warning in result.get("parse_warnings") or [])
    assert card["source_refs"][0]["start"] >= 0
    assert result["story_world"]["simulation_supplements"] == []


def test_programmatic_people_rejects_legal_connectors_and_keeps_source_names():
    text = (
        "被告人黎伟楠及被告人黄志满均到庭参加诉讼。"
        "被害人黎某壬、黎某辛的陈述与证人黄某乙的证言相互印证。"
        "本院认为，上述人员的身份应以原文为准。"
    )

    people = workflow_service._programmatic_people(text)
    names = {person["name"] for person in people}

    assert {"黎伟楠", "黄志满", "黎某壬", "黎某辛", "黄某乙"}.issubset(names)
    assert "及被告人" not in names
    assert "本院认为" not in names
    assert all(person["persona_autofill"] is False for person in people)
    assert all("behavior_archetype" not in person for person in people)
    assert all(person["role_template_version"] == "source_memory_v2" for person in people)


def test_text_first_identity_does_not_receive_invented_persona_defaults(monkeypatch):
    monkeypatch.setattr(
        workflow_service,
        "_generate_story_from_role_checkpoint",
        lambda *_args: ("被告人张三与被害人李四发生冲突。", _trace("story_assembly")),
    )

    result = workflow_service.parse_case_text("被告人张三与被害人李四发生冲突。")
    people = {person["name"]: person for person in result["persons"]}

    assert set(people) == {"张三", "李四"}
    assert all(person["persona_source"] == "programmatic_identity_only" for person in people.values())
    assert all("behavior_archetype" not in person for person in people.values())
    assert all("current_goal" not in person for person in people.values())
    assert all("surface_stance" not in person for person in people.values())
    assert all("pressure_response" not in person for person in people.values())
    assert all(person["role_template_version"] == "source_memory_v2" for person in people.values())


def test_evidence_chunk_people_are_merged_when_worldview_omits_them(monkeypatch):
    text = "张三报警，李某甲和王五在现场。"

    def fake_call(*, stage, **_kwargs):
        if stage == "evidence_extraction":
            return {
                "facts": [{"content": "李某甲和王五在现场", "fact_type": "行为", "quote": "李某甲和王五在现场", "status": "claimed"}],
                "person_observations": [
                    {"name": "李某甲", "observation": "在现场", "quote": "李某甲和王五在现场"},
                    {"name": "王五", "observation": "在现场", "quote": "李某甲和王五在现场"},
                ],
            }, _trace(stage)
        return {"case_name": "测试案件", "case_type": "纠纷", "persons": [{"name": "张三", "role_type": "证人"}], "story_world": {}}, _trace(stage)

    monkeypatch.setattr(workflow_service, "_generate_story_from_role_checkpoint", lambda *_args: ("张三报警，李某甲和王五在现场。", _trace("story_assembly")))
    result = workflow_service.parse_case_text(text)

    assert {person["name"] for person in result["persons"]} == {"张三", "李某甲", "王五"}
    assert {card["name"] for card in result["story_world"]["person_cards"]} == {"张三", "李某甲", "王五"}


def test_scene_scripts_must_reference_authorized_facts(monkeypatch):
    case_info = {
        "case_name": "测试案件", "case_type": "盗窃",
        "persons": [{"name": "张三", "role_type": "证人", "status": "正常"}],
        "story_world": {"fact_cards": [{"id": "F1", "content": "张三报警", "status": "confirmed", "source_refs": [{"start": 0, "end": 4}]}], "simulation_supplements": []},
    }

    def fake_call(*, stage, **_kwargs):
        if stage == "scene_blueprint":
            primary = _three_scene_blueprints(roles=["张三"])["blueprints"][1]
            return {"blueprints": [primary]}, _trace(stage)
        if stage == "scene_blueprint_completion":
            raise RuntimeError("completion unavailable")
        return _scene_script(roles=["张三"]), _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    result = workflow_service.generate_scenes(case_info)
    assert result["scene_generation_mode"].startswith("ai_")
    assert len(result["scenes"]) == 3
    assert result["scenes"][0]["fact_ids"] == ["F1"]
    assert "民警任务" in result["scenes"][0]["script_markdown"]
    assert result["scenes"][0]["training_entry_phase"] == "intake"
    assert all(scene["student_role"] == "民警" for scene in result["scenes"])
    assert all(scene["canonical_outcome_locked"] is True for scene in result["scenes"])
    assert all(
        scene["entry_time_policy"] == "after_canonical_event"
        for scene in result["scenes"][1:]
    )
    assert [scene["portfolio_role"] for scene in result["scenes"]] == ["intake", "primary", "investigation"]
    assert sum(1 for scene in result["scenes"] if scene["is_primary"]) == 1
    assert all(scene["completion_criteria"] for scene in result["scenes"])
    assert all(scene["end_prompt"] for scene in result["scenes"])


def test_scene_adds_all_speakable_people_grounded_in_its_facts(monkeypatch):
    case_info = {
        "case_name": "多人纠纷", "case_type": "纠纷",
        "persons": [
            {"name": "张三", "role_type": "证人", "status": "正常"},
            {"name": "李某甲", "role_type": "相关人员", "status": "正常", "source_verification": "pending_review"},
            {"name": "王五", "role_type": "嫌疑人", "status": "正常"},
            {"name": "赵六", "role_type": "被害人", "status": "死亡"},
        ],
        "story_world": {
            "fact_cards": [{"id": "F1", "content": "张三看见李某甲与王五发生争执，赵六倒地", "status": "claimed", "source_refs": []}],
            "simulation_supplements": [],
        },
    }

    def fake_call(*, stage, **_kwargs):
        if stage == "scene_blueprint":
            # The model accidentally keeps only one protagonist. The service
            # must restore the other fact-grounded, speakable case people.
            return _three_scene_blueprints(roles=["张三"]), _trace(stage)
        return _scene_script(roles=["张三"]), _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    result = workflow_service.generate_scenes(case_info)

    assert result["scenes"][0]["roles"] == ["张三", "李某甲", "王五"]
    assert "赵六" not in result["scenes"][0]["roles"]


def test_scene_json_failure_uses_ai_text_template_before_rule_fallback(monkeypatch):
    case_info = {
        "case_name": "测试案件", "case_type": "盗窃",
        "persons": [
            {"name": "张三", "role_type": "证人", "status": "正常"},
            {"name": "李某甲", "role_type": "相关人员", "status": "正常", "source_verification": "pending_review"},
        ],
        "story_world": {"fact_cards": [{"id": "F1", "content": "张三报警", "status": "confirmed", "source_refs": [{"start": 0, "end": 4}]}], "simulation_supplements": []},
    }
    monkeypatch.setattr(workflow_service, "_call_case_ai", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("invalid json")))
    monkeypatch.setattr(
        workflow_service,
        "_call_scene_text_ai",
        lambda **_kwargs: ("# 场景 1\n场景名称：报警核实\n场景信息：民警核实报警。\n接警信息：收到张三报警。\n现场第一印象：张三在线等待。\n参与角色：张三、李某甲\n引用事实：F1\n## 训练阶段\n1. 信息初核：核实报警经过。\n## 民警任务与角色回应边界\n围绕 F1 询问。\n\n# 场景 2\n场景名称：案发后现场核查\n场景信息：民警在案件发生后核查现场。\n接警信息：案件主要行为已经发生。\n现场第一印象：相关人员等待处理。\n参与角色：张三、李某甲\n引用事实：F1\n## 训练阶段\n1. 证据固定：核查现场信息。\n## 民警任务与角色回应边界\n围绕 F1 核查。\n\n# 场景 3\n场景名称：案发后调查询问\n场景信息：民警开展后续调查。\n接警信息：进入案发后调查阶段。\n现场第一印象：相关人员等待询问。\n参与角色：张三、李某甲\n引用事实：F1\n## 训练阶段\n1. 陈述核查：核查人员陈述。\n## 民警任务与角色回应边界\n围绕 F1 询问。", _trace("scene_text_template")),
    )

    result = workflow_service.generate_scenes(case_info)

    assert result["scene_generation_mode"] == "ai_text_template"
    assert result["ai_workflow"]["used_rule_fallback"] is False
    assert len(result["scenes"]) == 3
    assert result["scenes"][0]["scene_name"] == "报警核实"
    assert result["scenes"][0]["roles"] == ["张三", "李某甲"]


def test_ai_people_outside_regex_list_are_retained_as_pending_review():
    result = workflow_service._normalize_parsed_case(
        "张三到派出所报警。",
        {"persons": [
            {"name": "张三", "role": "报警人", "role_type": "证人"},
            {"name": "李某甲", "role": "被提及人员", "role_type": "相关人员"},
        ]},
        "plain_case",
        None,
        allowed_names=["张三"],
    )
    people = {item["name"]: item for item in result["persons"]}
    assert set(people) == {"张三", "李某甲"}
    assert people["张三"]["source_verification"] == "source_matched"
    assert people["李某甲"]["source_verification"] == "pending_review"


def test_role_phase_checkpoint_survives_story_assembly_failure(monkeypatch):
    text = "证人张三称，上午9时在山脚看见李四拿着木棍上山。李四称自己只是路过。"
    ai_people = [
        {
            "name": "张三", "role_type": "证人", "persona_autofill": False,
            "role_memories": [{"memory_id": "张三-M1", "memory_type": "direct_statement", "statement": "上午9时在山脚看见李四拿着木棍上山。", "time_hint": "上午9时", "place_hint": "山脚", "actors": ["张三", "李四"], "certainty": "claimed", "source_refs": [{"source_id": "source-1", "start": 0, "end": 25}]}],
            "unresolved_claims": [], "response_constraints": ["只依据本人证言回答。"],
        },
        {"name": "李四", "role_type": "相关人员", "persona_autofill": False, "role_memories": [], "unresolved_claims": [], "response_constraints": []},
    ]
    monkeypatch.setattr(workflow_service, "_extract_role_lines_ai", lambda *_args: (ai_people, [_trace("role_line_extraction")]))
    monkeypatch.setattr(workflow_service, "_generate_story_from_role_checkpoint", lambda *_args: (_ for _ in ()).throw(RuntimeError("length")))
    monkeypatch.setattr("services.workflow_service.save_story_version", lambda **_kwargs: 99)

    result = workflow_service.parse_case_text(text)

    assert {person["name"] for person in result["persons"]} == {"张三", "李四"}
    assert result["role_checkpoint_version_id"] == 99
    assert next(person for person in result["persons"] if person["name"] == "张三")["role_memories"]
    assert result["story_world"]["events"]
    assert any("仅剧情切换" in warning for warning in result["parse_warnings"])


def test_role_memory_filters_judgment_title_and_derives_time_place():
    title = "黎祖新聚众斗殴—审判刑事判决书"
    testimony = "被害人黎某18陈述：2011年7月19日上午9时在山脚看到黎祖新持木棍上山。"

    sections = workflow_service._classify_source_sections(f"{title}\n{testimony}")
    testimony_start = testimony.index("被害人") + len(title) + 1

    assert workflow_service._section_for_position(sections, testimony_start) == "testimony"
    assert not workflow_service._is_testimony_candidate("黎祖新", title, title, "direct_statement", "case_overview")
    assert workflow_service._is_testimony_candidate("黎某18", testimony, testimony, "direct_statement", "testimony")
    assert workflow_service._memory_hints(testimony, testimony, testimony, 0) == ("2011年7月19日上午9时", "山脚")


def test_rule_role_memories_keep_anonymous_testimony_and_source_coordinates():
    text = "案件简介：发生争执。\n被害人黎某18陈述：2011年7月19日上午9时在山脚看到黎祖新持木棍上山。"
    persons = workflow_service._programmatic_people(text)
    names = {person["name"] for person in persons}
    assert "黎某18" in names

    reconstruction = workflow_service._build_role_memories_and_case_flow(text, persons, workflow_service._programmatic_claim_cards(text))
    memory = reconstruction["role_memories"]["黎某18"][0]
    assert memory["quote"].startswith("被害人黎某18陈述")
    assert memory["time_hint"] == "2011年7月19日上午9时"
    assert memory["place_hint"] == "山脚"
    assert memory["source_refs"][0]["start"] == text.index("被害人黎某18")


def test_action_facts_recover_regional_names_and_personal_experience_memories():
    text = (
        "经审理查明，农长望持钢管和农长站、许明向、农盛星一起殴打农仕康。"
        "许远光报警，蒙增利和蒙增军赶到现场阻拦。"
    )
    persons = workflow_service._programmatic_people(text)
    names = {person["name"] for person in persons}

    assert {"农长望", "农长站", "许明向", "农盛星", "农仕康", "许远光", "蒙增利", "蒙增军"}.issubset(names)
    reconstruction = workflow_service._build_role_memories_and_case_flow(
        text, persons, workflow_service._programmatic_claim_cards(text)
    )
    assert reconstruction["role_memories"]["农长望"][0]["memory_type"] == "personal_experience"
    assert reconstruction["role_memories"]["农仕康"][0]["memory_type"] == "personal_experience"


def test_story_phase_reconciliation_recovers_people_without_promoting_story_to_fact():
    text = "农长望持钢管殴打农仕康。许远光随后报警，蒙增利赶到现场阻拦。"
    story = "农长望握紧钢管，心里仍有怨气，随后殴打农仕康。\n\n许远光报警后等待民警到场。"
    result = reconcile_case_roles(
        {"persons": [{"name": "许远光", "role_type": "报警人", "role_memories": []}]},
        source_text=text,
        complete_story=story,
    )
    people = {person["name"]: person for person in result["persons"]}

    assert {"农长望", "农仕康", "许远光", "蒙增利"}.issubset(people)
    assert result["role_reconciliation"]["recovered_person_count"] >= 3
    assert all(person["role_memories"] for person in people.values())
    narrative = people["农长望"]["narrative_context"][0]
    assert narrative["is_scoring_fact"] is False
    assert narrative["usage"] == "persona_context_only"
    assert all(memory.get("is_scoring_fact") is not False for memory in people["农长望"]["role_memories"])


def test_persona_context_includes_source_events_and_marks_narrative_as_non_fact():
    person = {
        "name": "农长望",
        "role_type": "相关人员",
        "role_memories": [{"statement": "农长望持钢管参与殴打。"}],
        "role_event_ledger": [{"content": "农长望持钢管参与殴打。"}],
        "narrative_context": [{"content": "农长望心里仍有怨气。", "is_scoring_fact": False}],
    }
    context = _persona_context(person)

    assert "持钢管" in context["source_memories"]
    assert "持钢管" in context["source_event_summary"]
    assert "心里仍有怨气" in context["narrative_context_for_persona_only"]


def test_ai_document_reading_labels_are_used_as_role_memory_navigation(monkeypatch):
    text = (
        "黎祖新聚众斗殴—审判刑事判决书\n"
        "基本案情：双方因纠纷发生争执。\n"
        "被害人黎某18陈述：2011年7月19日上午9时在山脚看到黎祖新持木棍上山。\n"
        "本院认为：现有证据能够相互印证。"
    )

    def fake_call(*, stage, **_kwargs):
        assert stage == "document_structure_labeling"
        return {
            "sections": [
                {"section_type": "document_title", "semantic_label": "刑事判决书标题", "processing_priority": "ignore_header", "anchor_quote": "黎祖新聚众斗殴—审判刑事判决书", "summary": "文档标题", "characters": []},
                {"section_type": "case_overview", "semantic_label": "案件基本案情", "processing_priority": "case_reconstruction", "anchor_quote": "基本案情：双方因纠纷发生争执。", "summary": "纠纷背景", "characters": []},
                {"section_type": "testimony", "semantic_label": "被害人黎某18的目击陈述", "processing_priority": "role_memory", "anchor_quote": "被害人黎某18陈述：2011年7月19日上午9时在山脚看到黎祖新持木棍上山。", "summary": "被害人的目击证言", "characters": ["黎某18", "黎祖新"]},
                {"section_type": "judgment_reasoning", "semantic_label": "法院认定理由", "processing_priority": "context_only", "anchor_quote": "本院认为：现有证据能够相互印证。", "summary": "裁判理由", "characters": []},
            ]
        }, _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    sections, _traces, error = workflow_service._label_source_sections_ai(text, "test-document-label")
    testimony_start = text.index("被害人黎某18")

    assert not error
    assert workflow_service._section_for_position(sections, testimony_start) == "testimony"
    testimony_section = next(item for item in sections if item["start"] == testimony_start)
    assert testimony_section["label"] == "被害人黎某18的目击陈述"
    assert testimony_section["processing_priority"] == "role_memory"


def test_role_line_extraction_keeps_statement_when_ai_section_identifies_speaker(monkeypatch):
    text = "被害人黎某18陈述：2011年7月19日上午9时在山脚看到黎祖新持木棍上山。"
    sections = [{
        "section_id": "AIS1", "section_type": "testimony", "label": "被害人黎某18的目击陈述",
        "processing_priority": "role_memory", "start": 0, "end": len(text),
    }]

    def fake_call(*, stage, **_kwargs):
        assert stage == "role_line_extraction"
        return {
            "persons": [{
                "name": "黎某18", "role_type": "被害人", "role_basis": "被害人陈述",
                "testimony_lines": [{
                    "statement": "2011年7月19日上午9时在山脚看到黎祖新持木棍上山。",
                    "memory_type": "direct_statement", "time_hint": "未明确", "place_hint": "未明确",
                    "actors": ["黎某18", "黎祖新"], "certainty": "claimed",
                    "quote": "2011年7月19日上午9时在山脚看到黎祖新持木棍上山。",
                }],
                "unresolved_claims": [],
            }]
        }, _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    people, _traces = workflow_service._extract_role_lines_ai(text, "test-role-lines", sections)
    memory = people[0]["role_memories"][0]

    assert memory["statement"].startswith("2011年7月19日")
    assert memory["time_hint"] == "2011年7月19日上午9时"
    assert memory["place_hint"] == "山脚"
