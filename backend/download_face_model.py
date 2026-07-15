"""下载 InsightFace buffalo_l 模型文件"""
import os
import sys
import zipfile
import urllib.request

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "face_models", "models", "buffalo_l")
os.makedirs(MODEL_DIR, exist_ok=True)

# buffalo_l 模型下载地址（InsightFace 官方）
MODEL_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
ZIP_PATH = os.path.join(os.path.dirname(MODEL_DIR), "buffalo_l.zip")

# 检查是否已下载
expected_files = ["det_10g.onnx", "w600k_r50.onnx"]
if all(os.path.exists(os.path.join(MODEL_DIR, f)) for f in expected_files):
    print(f"Model files already exist in {MODEL_DIR}")
    print(f"Files: {os.listdir(MODEL_DIR)}")
    sys.exit(0)

print(f"Downloading buffalo_l model from {MODEL_URL}...")
print(f"Target: {MODEL_DIR}")
print("This may take a few minutes...")

try:
    urllib.request.urlretrieve(MODEL_URL, ZIP_PATH)
    print(f"Downloaded to {ZIP_PATH} ({os.path.getsize(ZIP_PATH)} bytes)")
except Exception as e:
    print(f"Download failed: {e}")
    print("\nPlease manually download from:")
    print(f"  {MODEL_URL}")
    print(f"And extract to: {MODEL_DIR}")
    sys.exit(1)

print("Extracting...")
try:
    with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
        for member in zf.namelist():
            filename = os.path.basename(member)
            if filename.endswith('.onnx'):
                target = os.path.join(MODEL_DIR, filename)
                with zf.open(member) as src, open(target, 'wb') as dst:
                    dst.write(src.read())
                print(f"  Extracted: {filename} ({os.path.getsize(target)} bytes)")
    os.remove(ZIP_PATH)
    print(f"\nDone! Model files in {MODEL_DIR}:")
    print(f"  {os.listdir(MODEL_DIR)}")
except Exception as e:
    print(f"Extraction failed: {e}")
    sys.exit(1)

# 验证
print("\nVerifying model loading...")
try:
    from insightface.app import FaceAnalysis
    root_dir = os.path.dirname(os.path.dirname(MODEL_DIR))
    app = FaceAnalysis(name="buffalo_l", root=root_dir, allowed_modules=["detection", "recognition"], providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    print("SUCCESS: Model loaded and ready!")
except Exception as e:
    print(f"Verification failed: {e}")
    sys.exit(1)
