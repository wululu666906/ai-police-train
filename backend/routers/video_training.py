"""
视频实训模块 - 第二阶段路由
Session 管理、节点判定、关键词匹配、评估报告
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user

router = APIRouter(prefix="/video-training", tags=["VideoTraining"])


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

def _load_json(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _calc_full_score(nodes: list[models.VideoNode]) -> int:
    return sum(n.score_weight for n in nodes) if nodes else 100


def _serialize_session(session: models.VideoTrainingSession) -> dict:
    node_records = _load_json(session.node_records, [])
    violation_log = _load_json(session.violation_log, [])
    return {
        "id": session.id,
        "user_id": session.user_id,
        "video_id": session.video_id,
        "mode": session.mode,
        "status": session.status,
        "current_node_index": session.current_node_index,
        "total_score": session.total_score,
        "full_score": session.full_score,
        "node_records": node_records,
        "violation_log": violation_log,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
    }


def _serialize_node_result(r: models.VideoNodeResult) -> dict:
    return {
        "id": r.id,
        "session_id": r.session_id,
        "node_id": r.node_id,
        "node_index": r.node_index,
        "result": r.result,
        "retry_count": r.retry_count,
        "time_used": r.time_used,
        "score_earned": r.score_earned,
        "score_deducted": r.score_deducted,
        "answer_data": _load_json(r.answer_data, None),
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _match_keywords(text: str, keywords: list[str]) -> bool:
    """宽松关键词匹配：文本中包含任意一个关键词即通过"""
    if not keywords:
        return True
    normalized_text = text.lower()
    return any(kw.lower() in normalized_text for kw in keywords)


def _build_evaluation_report(
    session: models.VideoTrainingSession,
    node_results: list[models.VideoNodeResult],
    video: models.TrainingVideo,
) -> dict:
    """生成实训评估报告"""
    total = session.full_score or 100
    earned = session.total_score or 0
    pct = round(earned / total * 100) if total else 0

    # 评级
    if pct >= 90:
        grade = "优秀"
    elif pct >= 70:
        grade = "合格"
    else:
        grade = "待重修"

    # 各节点摘要
    node_summaries = []
    for r in node_results:
        node_summaries.append({
            "node_index": r.node_index,
            "node_id": r.node_id,
            "result": r.result,
            "retry_count": r.retry_count,
            "score_earned": r.score_earned,
            "score_deducted": r.score_deducted,
        })

    pass_count = sum(1 for r in node_results if r.result == "pass")
    skip_count = sum(1 for r in node_results if r.result in ("skip", "timeout"))
    total_deducted = sum(r.score_deducted for r in node_results)

    return {
        "session_id": session.id,
        "video_id": session.video_id,
        "video_title": video.title if video else "",
        "mode": session.mode,
        "total_score": earned,
        "full_score": total,
        "percentage": pct,
        "grade": grade,
        "pass_count": pass_count,
        "skip_count": skip_count,
        "total_nodes": len(node_results),
        "total_deducted": total_deducted,
        "node_summaries": node_summaries,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
    }


# ═════════════════════════════════════════════
# Session 管理
# ═════════════════════════════════════════════

@router.post("/start/{video_id}")
def start_video_training(
    video_id: int,
    mode: str = "practice",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """开始或恢复视频实训 Session"""
    video = db.query(models.TrainingVideo).filter(
        models.TrainingVideo.id == video_id,
        models.TrainingVideo.status == "published",
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在或未发布")
    if video.video_type != "interactive":
        raise HTTPException(status_code=400, detail="仅交互式实训视频支持创建训练 Session")
    if mode not in ("practice", "exam"):
        mode = "practice"

    # 查找是否有进行中的 session（同用户同视频）
    existing = (
        db.query(models.VideoTrainingSession)
        .filter(
            models.VideoTrainingSession.user_id == current_user.id,
            models.VideoTrainingSession.video_id == video_id,
            models.VideoTrainingSession.status == "active",
        )
        .order_by(models.VideoTrainingSession.created_at.desc())
        .first()
    )
    if existing:
        return {**_serialize_session(existing), "resumed": True}

    full_score = _calc_full_score(video.nodes)
    session = models.VideoTrainingSession(
        user_id=current_user.id,
        video_id=video_id,
        mode=mode,
        status="active",
        current_node_index=0,
        full_score=full_score,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {**_serialize_session(session), "resumed": False}


@router.get("/session/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取 Session 详情（含节点结果）"""
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")

    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session_id)
        .order_by(models.VideoNodeResult.node_index.asc())
        .all()
    )
    data = _serialize_session(session)
    data["node_results"] = [_serialize_node_result(r) for r in node_results]
    return data


# ═════════════════════════════════════════════
# 节点判定
# ═════════════════════════════════════════════

@router.post("/session/{session_id}/node/submit")
def submit_node_result(
    session_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    提交节点判定结果
    payload:
      node_id: int              节点 ID
      node_index: int           节点序号
      action: pass|skip|timeout 动作类型
      retry_count: int          本节点重试次数（默认 0）
      time_used: int            实际用时（秒）
      answer_data: dict         答题数据（判断/选择题用）
    """
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session 已结束")

    node_id = int(payload.get("node_id", 0))
    node_index = int(payload.get("node_index", 0))
    action = str(payload.get("action", "pass"))  # pass / skip / timeout
    retry_count = int(payload.get("retry_count", 0))
    time_used = payload.get("time_used")
    answer_data = payload.get("answer_data")

    node = db.query(models.VideoNode).filter(models.VideoNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # ── 计算得分 ──
    score_earned = node.score_weight
    score_deducted = 0

    if action == "skip":
        score_deducted = node.skip_score_deduct
        score_earned = max(0, node.score_weight - score_deducted)
        result = "skip"
    elif action == "timeout":
        score_deducted = node.skip_score_deduct
        score_earned = max(0, node.score_weight - score_deducted)
        result = "timeout"
    else:
        # pass：重试扣分
        score_deducted = min(retry_count * node.retry_score_deduct, node.score_weight)
        score_earned = max(0, node.score_weight - score_deducted)
        result = "pass"

        # 关键词校验（action 节点）
        submitted_text = str((answer_data or {}).get("text", "") if isinstance(answer_data, dict) else "")
        if node.node_type == "action" and submitted_text:
            keywords = _load_json(node.required_keywords, [])
            if keywords and not _match_keywords(submitted_text, keywords):
                # 关键词未匹配，额外扣一次重试分
                score_deducted += node.retry_score_deduct
                score_earned = max(0, node.score_weight - score_deducted)

    # ── 保存节点结果 ──
    # 检查是否已有该节点结果（重复提交时覆盖）
    existing_result = db.query(models.VideoNodeResult).filter(
        models.VideoNodeResult.session_id == session_id,
        models.VideoNodeResult.node_index == node_index,
    ).first()

    if existing_result:
        existing_result.result = result
        existing_result.retry_count = retry_count
        existing_result.time_used = time_used
        existing_result.score_earned = score_earned
        existing_result.score_deducted = score_deducted
        existing_result.answer_data = json.dumps(answer_data, ensure_ascii=False) if answer_data else None
        node_result = existing_result
    else:
        node_result = models.VideoNodeResult(
            session_id=session_id,
            node_id=node_id,
            node_index=node_index,
            result=result,
            retry_count=retry_count,
            time_used=time_used,
            score_earned=score_earned,
            score_deducted=score_deducted,
            answer_data=json.dumps(answer_data, ensure_ascii=False) if answer_data else None,
        )
        db.add(node_result)

    # 更新 Session 当前节点索引
    session.current_node_index = max(session.current_node_index, node_index + 1)
    db.commit()
    db.refresh(node_result)

    return {
        "node_result": _serialize_node_result(node_result),
        "score_earned": score_earned,
        "score_deducted": score_deducted,
        "result": result,
    }


@router.post("/session/{session_id}/violation")
def record_violation(
    session_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """记录违规行为（切屏、退出等）"""
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")

    log = _load_json(session.violation_log, [])
    log.append({
        "type": str(payload.get("type", "unknown")),
        "detail": str(payload.get("detail", "")),
        "ts": datetime.utcnow().isoformat(),
    })
    session.violation_log = json.dumps(log, ensure_ascii=False)
    db.commit()
    return {"message": "记录成功", "violation_count": len(log)}


# ═════════════════════════════════════════════
# 完成 & 评估报告
# ═════════════════════════════════════════════

@router.post("/session/{session_id}/finish")
def finish_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """结束实训，计算总分，生成评估报告"""
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    if session.status == "finished":
        # 已完成则直接返回报告
        return _get_report(db, session)

    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session_id)
        .all()
    )

    total_score = sum(r.score_earned for r in node_results)
    session.total_score = total_score
    session.status = "finished"
    session.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(session)

    return _get_report(db, session)


@router.get("/session/{session_id}/report")
def get_report(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取评估报告（Session 必须已完成）"""
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return _get_report(db, session)


def _get_report(db: Session, session: models.VideoTrainingSession) -> dict:
    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session.id)
        .order_by(models.VideoNodeResult.node_index.asc())
        .all()
    )
    video = db.query(models.TrainingVideo).filter(
        models.TrainingVideo.id == session.video_id
    ).first()
    return _build_evaluation_report(session, node_results, video)


# ═════════════════════════════════════════════
# 学员历史
# ═════════════════════════════════════════════

@router.get("/history")
def get_student_video_history(
    video_id: Optional[int] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    """学员的视频实训历史列表"""
    query = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.user_id == current_user.id,
    )
    if video_id:
        query = query.filter(models.VideoTrainingSession.video_id == video_id)
    sessions = query.order_by(models.VideoTrainingSession.created_at.desc()).limit(50).all()
    return [_serialize_session(s) for s in sessions]
