"""2-class 감성 분석 모델의 ONNX 변환 스크립트.

daekeun-ml/koelectra-small-v3-nsmc 모델을 ONNX 형식으로 변환하고
동적 양자화를 적용합니다. 백엔드는 PyTorch 없이 ONNX Runtime 만으로
추론하므로 배포 전에 이 변환이 필요합니다.

토크나이저도 함께 저장해 실행 시 외부 접속이 없도록 합니다.

사용법
    pip install torch onnx onnxruntime
    python export_binary_model.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

MODEL_NAME = "daekeun-ml/koelectra-small-v3-nsmc"

OUTPUT_DIR = Path(__file__).resolve().parent / "app" / "sentiment" / "model_binary"
ONNX_NAME = "nsmc_koelectra_small.onnx"
QUANTIZED_NAME = "nsmc_koelectra_small_quantized.onnx"

ONNX_PATH = OUTPUT_DIR / ONNX_NAME
QUANTIZED_PATH = OUTPUT_DIR / QUANTIZED_NAME

MAX_LENGTH = 128
SAMPLE_TEXT = "연출이 훌륭하고 배우들의 연기가 인상적이었습니다."

# 라벨 순서를 판정하기 위한 문장입니다.
POSITIVE_PROBE = "정말 훌륭하고 만족스러운 영화였습니다."
NEGATIVE_PROBE = "지루하고 실망스러워서 시간이 아까웠습니다."


# ---------------------------------------------------------------------------
# 준비
# ---------------------------------------------------------------------------

def require_packages():
    """변환에 필요한 패키지가 설치되어 있는지 확인합니다."""
    missing = []
    for package in ("torch", "onnx", "onnxruntime"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print("아래 패키지가 필요합니다.")
        print(f"    pip install {' '.join(missing)}")
        sys.exit(1)


def file_size_mb(path: Path) -> float:
    """파일 용량을 메가바이트 단위로 반환합니다."""
    return path.stat().st_size / (1024 * 1024)


# ---------------------------------------------------------------------------
# 변환
# ---------------------------------------------------------------------------

def export_onnx() -> None:
    """모델을 ONNX 형식으로 변환합니다."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    print(f"모델을 적재합니다: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    print(f"  출력 개수 : {model.config.num_labels}")
    print(f"  라벨 정보 : {model.config.id2label}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("토크나이저를 저장합니다.")
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    encoded = tokenizer(
        SAMPLE_TEXT,
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    # 미션 16 모델과 동일하게 input_ids 와 attention_mask 만 입력으로 사용합니다.
    inputs = (encoded["input_ids"], encoded["attention_mask"])

    print("ONNX 형식으로 변환합니다.")
    torch.onnx.export(
        model,
        inputs,
        str(ONNX_PATH),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=14,
        do_constant_folding=True,
    )
    print(f"  저장 완료 : {ONNX_PATH.name}  {file_size_mb(ONNX_PATH):.2f} MB")


def quantize() -> None:
    """동적 양자화를 적용해 용량을 줄입니다.

    ONNX 의 형상 추론은 C++ 로 구현되어 있어 대괄호나 한글이 포함된
    Windows 경로를 처리하지 못합니다. 임시 폴더에서 작업한 뒤
    결과 파일만 원래 위치로 옮깁니다.
    """
    from onnxruntime.quantization import QuantType, quantize_dynamic

    print("동적 양자화를 적용합니다.")

    with tempfile.TemporaryDirectory() as temp_name:
        temp_dir = Path(temp_name)
        temp_input = temp_dir / ONNX_NAME
        temp_output = temp_dir / QUANTIZED_NAME

        shutil.copy2(ONNX_PATH, temp_input)

        quantize_dynamic(
            model_input=str(temp_input),
            model_output=str(temp_output),
            weight_type=QuantType.QInt8,
        )

        shutil.copy2(temp_output, QUANTIZED_PATH)

    original = file_size_mb(ONNX_PATH)
    quantized = file_size_mb(QUANTIZED_PATH)
    reduction = (1 - quantized / original) * 100

    print(f"  저장 완료 : {QUANTIZED_PATH.name}  {quantized:.2f} MB")
    print(f"  용량 절감 : {reduction:.1f}퍼센트")


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------

def verify() -> int:
    """변환한 모델을 검증하고 부정 라벨의 인덱스를 반환합니다."""
    import numpy as np
    import onnxruntime as ort
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    print("변환 결과를 검증합니다.")

    tokenizer = AutoTokenizer.from_pretrained(str(OUTPUT_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    samples = [
        POSITIVE_PROBE,
        NEGATIVE_PROBE,
        "마지막 재회 장면에서는 눈물을 참기가 어려웠습니다.",
        "음향과 촬영이 만들어내는 불안한 분위기가 대단했습니다.",
    ]

    encoded = tokenizer(
        samples,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    with torch.no_grad():
        torch_logits = model(
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"],
        ).logits.numpy()

    feeds = {
        "input_ids": encoded["input_ids"].numpy().astype(np.int64),
        "attention_mask": encoded["attention_mask"].numpy().astype(np.int64),
    }

    outputs = {}
    for label, path in (("ONNX", ONNX_PATH), ("양자화", QUANTIZED_PATH)):
        session = ort.InferenceSession(
            str(path), providers=["CPUExecutionProvider"]
        )
        outputs[label] = session.run(None, feeds)[0]

    header = f"{'문장':46} {'PyTorch':>9} {'ONNX':>9} {'양자화':>9}"
    print()
    print(header)
    print("-" * len(header))

    agreement = 0
    for index, text in enumerate(samples):
        torch_label = int(torch_logits[index].argmax())
        onnx_label = int(outputs["ONNX"][index].argmax())
        quant_label = int(outputs["양자화"][index].argmax())

        if torch_label == quant_label:
            agreement += 1

        shortened = text[:42] + "..." if len(text) > 42 else text
        print(f"{shortened:46} {torch_label:>9} {onnx_label:>9} {quant_label:>9}")

    print()
    print(f"원본과 양자화 모델의 판정 일치 : {agreement} / {len(samples)}")

    max_diff = np.abs(torch_logits - outputs["ONNX"]).max()
    print(f"원본과 ONNX 의 최대 출력 차이  : {max_diff:.6f}")

    # -----------------------------------------------------------------------
    # 라벨 순서 판정
    # -----------------------------------------------------------------------
    positive_index = int(outputs["양자화"][0].argmax())
    negative_index = int(outputs["양자화"][1].argmax())

    print()
    if positive_index == negative_index:
        print("경고: 라벨 순서를 판정하지 못했습니다. 두 문장이 같은 인덱스로 나왔습니다.")
        return 0

    print(f"라벨 순서 : 인덱스 {negative_index} 가 부정, 인덱스 {positive_index} 가 긍정")
    return negative_index


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------

def main() -> None:
    require_packages()

    if OUTPUT_DIR.exists():
        print(f"기존 폴더를 정리합니다: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    export_onnx()
    print()
    quantize()
    print()
    negative_index = verify()

    print()
    print("=" * 70)
    print("변환이 완료되었습니다.")
    print(f"저장 위치 : {OUTPUT_DIR}")
    print("=" * 70)
    for path in sorted(OUTPUT_DIR.iterdir()):
        print(f"  {file_size_mb(path):9.2f} MB  {path.name}")

    print()
    print(".env 에 아래 항목을 추가해주세요.")
    print("-" * 70)
    print("BINARY_MODEL_DIR=app/sentiment/model_binary")
    print(f"BINARY_MODEL_FILE={QUANTIZED_NAME}")
    print(f"BINARY_NEGATIVE_INDEX={negative_index}")


if __name__ == "__main__":
    main()