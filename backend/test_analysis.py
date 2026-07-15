"""测试两阶段视频分析流程"""
import sys
import os
import traceback
sys.path.insert(0, os.path.dirname(__file__))

from env_loader import load_backend_env
load_backend_env()

print("=" * 50)
print("Step 1: 检查环境配置")
print("=" * 50)
print(f"  DASHSCOPE_API_KEY set: {bool(os.getenv('DASHSCOPE_API_KEY'))}")
print(f"  DEEPSEEK_API_KEY set: {bool(os.getenv('DEEPSEEK_API_KEY'))}")
print(f"  LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")

import subprocess
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    print(f"  ffmpeg: {'OK' if result.returncode == 0 else 'FAILED'}")
except Exception as e:
    print(f"  ffmpeg: NOT FOUND - {e}")

VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "static", "videos")
print(f"\n  Videos dir: {VIDEOS_DIR}")
if os.path.exists(VIDEOS_DIR):
    files = [f for f in os.listdir(VIDEOS_DIR) if f.endswith(('.mp4', '.webm', '.mov'))]
    print(f"  Video files: {files[:5]}")
    if not files:
        print("  No video files found!")
        sys.exit(1)
    test_video = os.path.join(VIDEOS_DIR, files[0])
    print(f"  Testing with: {files[0]} ({os.path.getsize(test_video)} bytes)")
else:
    print("  Videos dir does not exist!")
    sys.exit(1)

try:
    print("\n" + "=" * 50)
    print("Step 2: 完整两阶段分析")
    print("=" * 50)
    from services.video_auto_config_service import analyze_video_file
    result = analyze_video_file(test_video, title_hint="测试视频", duration_seconds=75)
    print(f"  analysis_mode: {result.get('analysis_mode')}")
    print(f"  analysis_error: {result.get('analysis_error')}")
    print(f"  video_type: {result.get('video_type')}")
    print(f"  scenario_type: {result.get('scenario_type')}")
    print(f"  nodes count: {len(result.get('nodes') or [])}")
    print(f"  transcript count: {len(result.get('transcript') or [])}")
    if result.get('nodes'):
        for i, node in enumerate(result['nodes'][:5]):
            print(f"\n  === Node {i+1} ===")
            print(f"  title: {node.get('title')}")
            print(f"  trigger_time: {node.get('trigger_time')}s")
            print(f"  node_type: {node.get('node_type')}")
            print(f"  interaction_type: {node.get('node_interaction_type')}")
            print(f"  ai_hint: {(node.get('ai_instructor_hint') or 'MISSING')[:150]}")
            print(f"  keywords: {node.get('required_keywords')}")
            print(f"  correct_answer: {node.get('correct_answer')}")
            pc = node.get('prompt_content') or {}
            print(f"  speech_hint: {(pc.get('speech_hint') or 'N/A')[:120]}")
    else:
        print("  NO NODES GENERATED")
    print("\nDone!")
except Exception as e:
    print(f"\nERROR: {e}")
    traceback.print_exc()
