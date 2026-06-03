import json

import pytest

from services.evaluation_service import (
    DIMENSIONS,
    SCENE_RUBRICS,
    apply_assessment_driven_scoring,
    apply_rule_adjustments,
    build_fallback_report,
    build_knowledge_hits,
    build_rule_checks,
    calibrate_report,
    compute_grade_level,
    format_dialogue,
    infer_scene_type,
    merge_assessment_point_results,
    normalize_llm_report,
    reconcile_dimension_scores,
    render_rule_summary,
)


class TestInferSceneType:
    def test_infer_jiejing(self):
        class MockScene:
            name = "接警对话训练"
        assert infer_scene_type(MockScene()) == "接警"

    def test_infer_xianchang(self):
        class MockScene:
            name = "现场询问"
        assert infer_scene_type(MockScene()) == "现场"

    def test_infer_shenxun(self):
        class MockScene:
            name = "审讯嫌疑人"
        assert infer_scene_type(MockScene()) == "审讯"

    def test_infer_generic(self):
        class MockScene:
            name = "其他场景"
        assert infer_scene_type(MockScene()) == "通用"


class TestFormatDialogue:
    def test_format_user_and_ai(self):
        class MockMsg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        msgs = [
            MockMsg("user", "你好，请问发生了什么事？"),
            MockMsg("assistant", "是这样的，我和邻居有些矛盾。"),
            MockMsg("user", "具体是什么矛盾？"),
        ]
        dialogue, student_lines = format_dialogue(msgs)
        assert "学员: 你好" in dialogue
        assert "AI角色: 是这样的" in dialogue
        assert len(student_lines) == 2
        assert student_lines[0] == "你好，请问发生了什么事？"

    def test_format_empty(self):
        dialogue, student_lines = format_dialogue([])
        assert dialogue == ""
        assert student_lines == []


class TestBuildRuleChecks:
    def make_scene(self, name):
        class MockScene:
            pass
        s = MockScene()
        s.name = name
        s.dispatch_brief = None
        s.first_impression = None
        s.stages = "[]"
        return s

    def make_role(self, name="张某"):
        class MockRole:
            pass
        r = MockRole()
        r.name = name
        return r

    def test_jiejing_missing_location(self):
        scene = self.make_scene("接警对话")
        role = self.make_role()
        result = build_rule_checks(scene, ["你好", "请问什么情况"], role)
        findings = result["findings"]
        assert any("案发地点" in f["message"] for f in findings)

    def test_jiejing_with_location(self):
        scene = self.make_scene("接警对话")
        role = self.make_role()
        result = build_rule_checks(scene, ["你在哪里？具体地址是什么？", "几点发生的？"], role)
        findings = result["findings"]
        assert not any("案发地点" in f["message"] for f in findings)

    def test_jiejing_missing_injury_check(self):
        scene = self.make_scene("接警对话")
        role = self.make_role()
        result = build_rule_checks(
            scene, ["你在哪里？具体地址是什么？", "几点发生的？"], role
        )
        findings = result["findings"]
        assert any("受伤" in f["message"] or "风险" in f["message"] for f in findings)

    def test_xianchang_missing_identity(self):
        scene = self.make_scene("现场询问")
        role = self.make_role()
        result = build_rule_checks(scene, ["发生了什么事"], role)
        findings = result["findings"]
        assert any("身份" in f["message"] or "姓名" in f["message"] for f in findings)

    def test_xianchang_with_identity(self):
        scene = self.make_scene("现场询问")
        role = self.make_role()
        result = build_rule_checks(scene, ["你叫什么名字？", "和对方什么关系？"], role)
        findings = result["findings"]
        assert not any("身份" in f["message"] for f in findings)

    def test_shenxun_missing_timeline(self):
        scene = self.make_scene("审讯嫌疑人")
        role = self.make_role()
        result = build_rule_checks(scene, ["你叫什么", "你在现场做了什么"], role)
        findings = result["findings"]
        assert any("时间线" in f["message"] or "时间" in f["message"] for f in findings)

    def test_low_turn_deduction(self):
        scene = self.make_scene("通用")
        role = self.make_role()
        result = build_rule_checks(scene, ["你好"], role)
        assert result["deductions"]["信息获取效率"] >= 4
        assert result["deductions"]["执法流程完整性"] >= 3

    def test_bad_phrase_detection(self):
        scene = self.make_scene("接警对话")
        role = self.make_role()
        result = build_rule_checks(scene, ["快说，别废话！给我老实交代！"], role)
        assert result["deductions"]["执法语言规范性"] >= 8

    def test_no_role_name(self):
        scene = self.make_scene("通用")
        role = self.make_role(name="")
        result = build_rule_checks(scene, ["你好，请说明情况"], role)
        assert any("角色信息异常" in f["message"] for f in result["findings"])


class TestRenderRuleSummary:
    def test_no_findings(self):
        summary = render_rule_summary({"findings": []})
        assert "未发现明显" in summary

    def test_with_findings(self):
        findings = [
            {"level": "major", "dimension": "执法语言规范性", "message": "存在不规范用语"}
        ]
        summary = render_rule_summary({"findings": findings})
        assert "[major]" in summary
        assert "不规范用语" in summary


class TestNormalizeLLMReport:
    def test_full_report(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": 22, "full_score": 25, "reason": "基本规范"},
                {"dimension": "执法流程完整性", "score": 20, "full_score": 25, "reason": "流程基本完整"},
                {"dimension": "法律依据正确性", "score": 18, "full_score": 20, "reason": "基本正确"},
                {"dimension": "情绪控制能力", "score": 13, "full_score": 15, "reason": "情绪稳定"},
                {"dimension": "信息获取效率", "score": 12, "full_score": 15, "reason": "效率尚可"},
            ],
        }
        result = normalize_llm_report(report)
        assert result["total_score"] == 85
        assert len(result["scores"]) == 5

    def test_partial_report(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": 20, "reason": "还行"}
            ],
            "strengths": ["语言规范"],
            "improvements": ["可继续改进"],
            "suggestions": "继续努力",
        }
        result = normalize_llm_report(report)
        assert len(result["scores"]) == 5
        assert result["scores"][0]["score"] == 20
        assert result["scores"][1]["score"] == 25

    def test_score_clamping(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": 30, "full_score": 25, "reason": "超满分"}
            ],
        }
        result = normalize_llm_report(report)
        assert result["scores"][0]["score"] == 25

    def test_negative_score_clamp(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": -5, "full_score": 25, "reason": "负分"}
            ],
        }
        result = normalize_llm_report(report)
        assert result["scores"][0]["score"] == 0


class TestApplyRuleAdjustments:
    def test_deductions_applied(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": 20, "full_score": 25, "reason": ""},
                {"dimension": "执法流程完整性", "score": 20, "full_score": 25, "reason": ""},
                {"dimension": "法律依据正确性", "score": 18, "full_score": 20, "reason": ""},
                {"dimension": "情绪控制能力", "score": 15, "full_score": 15, "reason": ""},
                {"dimension": "信息获取效率", "score": 12, "full_score": 15, "reason": ""},
            ],
            "total_score": 85,
            "strengths": [],
            "improvements": [],
            "suggestions": "",
        }
        rule_checks = {
            "findings": [{"message": "违规用语"}],
            "deductions": {"执法语言规范性": 8, "情绪控制能力": 3},
        }
        result = apply_rule_adjustments(report, rule_checks)
        assert result["scores"][0]["score"] == 12
        assert result["scores"][3]["score"] == 12

    def test_deduction_no_negative(self):
        report = {
            "scores": [
                {"dimension": "执法语言规范性", "score": 3, "full_score": 25, "reason": ""},
            ]
            + [
                {"dimension": dim, "score": fs, "full_score": fs, "reason": ""}
                for dim, fs in DIMENSIONS[1:]
            ],
            "total_score": 0,
            "strengths": [],
            "improvements": [],
            "suggestions": "",
        }
        rule_checks = {
            "findings": [],
            "deductions": {"执法语言规范性": 10},
        }
        result = apply_rule_adjustments(report, rule_checks)
        assert result["scores"][0]["score"] == 0


class TestCalibrateReport:
    def make_report(self, total, turn_count=1):
        scores = []
        per_dim = total // 5
        remainder = total - per_dim * 5
        for i, (dim, fs) in enumerate(DIMENSIONS):
            score = per_dim + (1 if i < remainder else 0)
            scores.append({"dimension": dim, "score": score, "full_score": fs, "reason": ""})
        return {
            "scores": scores,
            "total_score": total,
            "strengths": [],
            "improvements": [],
            "suggestions": "",
        }

    def test_low_turn_cap(self):
        report = self.make_report(95, turn_count=1)
        result = calibrate_report(report, ["hello"], "通用")
        assert result["total_score"] <= 55

    def test_two_turn_cap(self):
        report = self.make_report(95, turn_count=2)
        result = calibrate_report(report, ["a", "b"], "通用")
        assert result["total_score"] <= 68

    def test_three_turn_cap(self):
        report = self.make_report(95, turn_count=3)
        result = calibrate_report(report, ["a", "b", "c"], "通用")
        assert result["total_score"] <= 78

    def test_many_turns_no_cap(self):
        report = self.make_report(85, turn_count=10)
        result = calibrate_report(report, ["a"] * 10, "通用")
        assert result["total_score"] == 85

    def test_adds_strengths_when_few(self):
        report = self.make_report(75, turn_count=5)
        result = calibrate_report(report, ["请", "麻烦", "有没有"], "接警")
        assert len(result["strengths"]) >= 2

    def test_adds_improvements_when_few(self):
        report = self.make_report(75, turn_count=5)
        result = calibrate_report(report, ["a"], "接警")
        assert len(result["improvements"]) >= 1
        assert any("地点" in imp for imp in result["improvements"])

    def test_adds_default_suggestions(self):
        report = self.make_report(75, turn_count=5)
        report["suggestions"] = ""
        result = calibrate_report(report, ["a"] * 5, "通用")
        assert len(result["suggestions"]) > 0


class TestBuildFallbackReport:
    def test_creates_valid_report(self):
        result = build_fallback_report("LLM 返回了非 JSON 摘要", ["hello"], "接警")
        assert "total_score" in result
        assert "scores" in result
        assert len(result["scores"]) == 5
        assert result["evaluation_meta"]["llm_fallback"] is True

    def test_empty_input(self):
        result = build_fallback_report("", ["a", "b"], "现场")
        assert len(result["scores"]) == 5


class TestSceneRubrics:
    def test_all_scene_types_have_rubrics(self):
        for scene_type in ["接警", "现场", "审讯", "通用"]:
            assert scene_type in SCENE_RUBRICS
            assert len(SCENE_RUBRICS[scene_type]) >= 1

    def test_rubrics_are_strings(self):
        for items in SCENE_RUBRICS.values():
            for item in items:
                assert isinstance(item, str)
                assert len(item) > 0


class TestDimensions:
    def test_total_weight_is_100(self):
        total = sum(fs for _, fs in DIMENSIONS)
        assert total == 100

    def test_all_five_dimensions(self):
        names = [dim for dim, _ in DIMENSIONS]
        assert "执法语言规范性" in names
        assert "执法流程完整性" in names
        assert "法律依据正确性" in names
        assert "情绪控制能力" in names
        assert "信息获取效率" in names


class TestFormalScoringHelpers:
    def test_compute_grade_level(self):
        assert compute_grade_level(92) == "卓越"
        assert compute_grade_level(75) == "良好"
        assert compute_grade_level(40) == "需改进"

    def test_merge_assessment_point_results_prefers_runtime_hit(self):
        runtime = [{"id": "ap_1", "label": "核实身份", "status": "hit", "weight": 10, "score": 10, "evidence": ["学员: 请出示证件"]}]
        llm = [{"id": "ap_1", "label": "核实身份", "status": "missed", "reason": "模型误判"}]
        rows = [{"id": "ap_1", "label": "核实身份", "content": "确认身份", "stage_name": "现场控制"}]
        merged = merge_assessment_point_results(runtime, llm, rows)
        assert merged[0]["status"] == "hit"
        assert merged[0]["score"] == 10
        assert "模型误判" in merged[0]["feedback"]

    def test_reconcile_dimension_scores(self):
        report = {
            "total_score": 60,
            "scores": [
                {"dimension": "执法语言规范性", "score": 20, "full_score": 25, "reason": "a"},
                {"dimension": "执法流程完整性", "score": 20, "full_score": 25, "reason": "b"},
                {"dimension": "法律依据正确性", "score": 20, "full_score": 20, "reason": "c"},
                {"dimension": "情绪控制能力", "score": 10, "full_score": 15, "reason": "d"},
                {"dimension": "信息获取效率", "score": 10, "full_score": 15, "reason": "e"},
            ],
        }
        result = reconcile_dimension_scores(report)
        assert result["total_score"] == sum(item["score"] for item in result["scores"])

    def test_apply_assessment_driven_scoring_caps_low_completion(self):
        report = normalize_llm_report(
            {
                "scores": [
                    {"dimension": "执法语言规范性", "score": 22, "full_score": 25, "reason": "较好"},
                    {"dimension": "执法流程完整性", "score": 22, "full_score": 25, "reason": "较好"},
                    {"dimension": "法律依据正确性", "score": 18, "full_score": 20, "reason": "较好"},
                    {"dimension": "情绪控制能力", "score": 13, "full_score": 15, "reason": "较好"},
                    {"dimension": "信息获取效率", "score": 13, "full_score": 15, "reason": "较好"},
                ]
            }
        )
        points = [
            {"label": "必考1", "status": "missed", "required": True, "weight": 10, "score": 0},
            {"label": "必考2", "status": "missed", "required": True, "weight": 10, "score": 0},
            {"label": "选考", "status": "missed", "required": False, "weight": 10, "score": 0},
        ]
        result = apply_assessment_driven_scoring(report, points, [])
        assert result["total_score"] <= 58
