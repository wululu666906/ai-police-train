from services.evaluation_service import (
    COMMON_DIMENSIONS,
    DIMENSIONS,
    SCORING_VERSION,
    build_adaptive_report,
    build_rule_checks,
    calculate_adaptive_weighting,
    compute_grade_level,
    format_dialogue,
    infer_scene_type,
    merge_assessment_point_results,
    reconcile_dimension_scores,
    render_rule_summary,
)


COMMON_DIMENSION_NAMES = {name for name, _ in COMMON_DIMENSIONS}


class MockMsg:
    def __init__(self, role, content):
        self.role = role
        self.content = content


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
        msgs = [
            MockMsg("user", "你好，请问发生了什么事？"),
            MockMsg("assistant", "是这样的，我和邻居有些矛盾。"),
            MockMsg("user", "具体是什么矛盾？"),
        ]
        dialogue, student_lines = format_dialogue(msgs)
        assert "学员: 你好" in dialogue
        assert "AI角色: 是这样的" in dialogue
        assert len(student_lines) == 2

    def test_format_empty(self):
        dialogue, student_lines = format_dialogue([])
        assert dialogue == ""
        assert student_lines == []


class TestBuildRuleChecks:
    def make_scene(self, name):
        class MockScene:
            pass

        scene = MockScene()
        scene.name = name
        scene.dispatch_brief = None
        scene.first_impression = None
        scene.stages = "[]"
        return scene

    def make_role(self, name="张某"):
        class MockRole:
            pass

        role = MockRole()
        role.name = name
        return role

    def test_jiejing_missing_location(self):
        result = build_rule_checks(self.make_scene("接警对话"), ["你好", "请问什么情况"], self.make_role())
        assert any("案发地点" in item["message"] for item in result["findings"])
        assert "关键信息整理能力" in result["deductions"]

    def test_bad_phrase_detection(self):
        result = build_rule_checks(self.make_scene("接警对话"), ["快说，别废话！给我老实交代！"], self.make_role())
        assert result["deductions"]["沟通表达与执法语言"] >= 8

    def test_no_old_dimension_names_in_deductions(self):
        result = build_rule_checks(self.make_scene("通用"), ["你好"], self.make_role())
        assert set(result["deductions"].keys()) == COMMON_DIMENSION_NAMES


class TestRenderRuleSummary:
    def test_no_findings(self):
        summary = render_rule_summary({"findings": []})
        assert "未发现明显" in summary

    def test_with_findings(self):
        summary = render_rule_summary(
            {"findings": [{"level": "major", "dimension": "沟通表达与执法语言", "message": "存在不规范用语"}]}
        )
        assert "[major]" in summary
        assert "不规范用语" in summary


class TestAdaptiveWeighting:
    def make_point(self, index, weight=12, required=True, status="hit"):
        return {
            "id": f"ap_{index}",
            "label": f"考察点{index}",
            "weight": weight,
            "required": required,
            "status": status,
            "score": weight if status == "hit" else weight // 2 if status == "partial" else 0,
        }

    def test_version_and_common_dimensions(self):
        assert SCORING_VERSION == "adaptive_v1"
        assert len(COMMON_DIMENSIONS) == 4
        assert len(DIMENSIONS) == 4
        assert {name for name, _ in DIMENSIONS} == COMMON_DIMENSION_NAMES

    def test_four_medium_points_split_half(self):
        points = [self.make_point(i, weight=12, required=True) for i in range(4)]
        weighting = calculate_adaptive_weighting(points)
        assert weighting["common_share"] == 0.5
        assert weighting["assessment_share"] == 0.5

    def test_no_points_uses_common_only(self):
        weighting = calculate_adaptive_weighting([])
        assert weighting["common_share"] == 1.0
        assert weighting["assessment_share"] == 0.0
        assert weighting["assessment_point_count"] == 0

    def test_many_high_required_points_are_capped_at_65_percent(self):
        points = [self.make_point(i, weight=15, required=True) for i in range(8)]
        weighting = calculate_adaptive_weighting(points)
        assert weighting["assessment_share"] == 0.65
        assert weighting["common_share"] == 0.35

    def test_duplicate_semantic_points_count_once(self):
        points = [
            {**self.make_point(1, weight=15), "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向。怎样算完成：回放时能听出明确派警判断。"},
            {**self.make_point(2, weight=10), "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向"},
        ]
        weighting = calculate_adaptive_weighting(points)
        assert weighting["assessment_point_count"] == 1
        assert len(weighting["point_weights"]) == 1
        assert weighting["point_weights"][0]["full_score"] == weighting["assessment_full_score"]


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

    def test_merge_assessment_point_results_dedupes_semantic_duplicates(self):
        runtime = [
            {"id": "ap_high", "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向。怎样算完成：回放时能听出明确派警判断。", "status": "missed", "weight": 15},
            {"id": "ap_low", "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向", "status": "partial", "weight": 10, "evidence": ["学员: 对方还在现场吗"]},
        ]
        llm = [
            {"id": "ap_low", "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向", "status": "missed", "reason": "重复模型输出"},
        ]
        rows = [
            {"id": "ap_high", "label": "初判警情等级", "content": "判断是否存在人身危险并给出处置倾向。怎样算完成：回放时能听出明确派警判断。", "stage_name": "接警", "weight": 15, "required": True},
        ]
        merged = merge_assessment_point_results(runtime, llm, rows)
        assert len(merged) == 1
        assert merged[0]["status"] == "partial"
        assert merged[0]["weight"] == 15
        assert merged[0]["score"] == 7

    def test_reconcile_dimension_scores(self):
        report = {
            "total_score": 60,
            "scores": [
                {"dimension": "沟通表达与执法语言", "score": 25, "full_score": 25, "reason": "a"},
                {"dimension": "主动询问与逻辑推进", "score": 25, "full_score": 25, "reason": "b"},
                {"dimension": "关键信息整理能力", "score": 25, "full_score": 25, "reason": "c"},
                {"dimension": "处置闭环意识", "score": 25, "full_score": 25, "reason": "d"},
            ],
        }
        result = reconcile_dimension_scores(report)
        assert result["total_score"] == sum(item["score"] for item in result["scores"])


class TestAdaptiveReport:
    def make_points(self, required_statuses):
        points = []
        for index, status in enumerate(required_statuses, start=1):
            points.append(
                {
                    "id": f"ap_{index}",
                    "label": f"必考{index}",
                    "status": status,
                    "required": True,
                    "weight": 12,
                    "score": 12 if status == "hit" else 6 if status == "partial" else 0,
                    "evidence": ["学员: 示例"],
                    "feedback": "反馈",
                }
            )
        return points

    def test_report_uses_adaptive_scores_without_old_dimensions(self):
        points = self.make_points(["hit", "hit", "hit", "hit"])
        report = build_adaptive_report(
            {"common_reviews": [], "strengths": [], "improvements": [], "suggestions": ""},
            points,
            [],
            ["您好，请说明情况", "几点发生的", "在哪里", "后续我们会处理"],
            [MockMsg("user", "您好，请说明情况"), MockMsg("assistant", "情况是这样的")],
            {"findings": [], "deductions": {}},
            "接警",
        )
        assert report["evaluation_meta"]["scoring_version"] == "adaptive_v1"
        dimensions = {item["dimension"] for item in report["scores"]}
        assert all(name in COMMON_DIMENSION_NAMES or name.startswith("考察点：") for name in dimensions)
        assert any(item["group"] == "assessment" for item in report["scores"])

    def test_required_point_cap(self):
        points = self.make_points(["missed", "missed", "missed"])
        report = build_adaptive_report(
            {"common_reviews": []},
            points,
            [],
            ["您好，请说明情况", "还有什么", "在哪里", "后续处理"],
            [MockMsg("user", "您好，请说明情况")],
            {"findings": [], "deductions": {}},
            "接警",
        )
        assert report["total_score"] <= 58
        assert report["evaluation_meta"]["score_caps"]["final_cap"] <= 58

    def test_red_flag_cap(self):
        points = self.make_points(["hit", "hit", "hit", "hit"])
        report = build_adaptive_report(
            {"common_reviews": []},
            points,
            [],
            ["快说，别废话！给我老实交代！", "在哪里", "几点", "后续处理"],
            [MockMsg("user", "快说，别废话！给我老实交代！")],
            {"findings": [], "deductions": {}},
            "接警",
        )
        assert report["total_score"] <= 59
        assert report["evaluation_meta"]["red_flags"]
