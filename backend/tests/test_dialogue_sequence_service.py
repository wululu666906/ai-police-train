from services.dialogue_sequence_service import (
    build_intake_sequence_feedback,
    check_premature_questions,
    detect_officer_phase,
    detect_satisfied_phases,
)


def test_detect_officer_phase_progression():
    phases = detect_satisfied_phases(["你好，请问发生了什么事？"])
    assert "incident_nature" in phases
    assert detect_officer_phase(["你好，请问发生了什么事？"]) == "incident_nature"


def test_premature_time_before_incident():
    warning = check_premature_questions("事情大概几点发生的？", [], [])
    assert warning is not None
    assert warning["level"] == "warning"
    assert "premature_time" in warning["tags"]


def test_no_premature_after_incident_and_safety():
    history = ["你好，请问发生了什么事？", "你现在安全吗？有没有人受伤？"]
    warning = check_premature_questions("事情大概几点发生的？", history, [])
    assert warning is None


def test_intake_listen_first_feedback():
    class Msg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    messages = [Msg("assistant", "喂110吗，这边有人打架了！")]
    feedback = build_intake_sequence_feedback(messages, "", [])
    assert feedback is not None
    assert feedback["tags"] == ["intake_listen_first"]
