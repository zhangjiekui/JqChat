from typing import TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from rapidocr_paddle import RapidOCR
    except ImportError:
        from rapidocr_onnxruntime import RapidOCR


def get_ocr(use_cuda: bool = True) -> "RapidOCR":
    try:
        from rapidocr_paddle import RapidOCR

        ocr = RapidOCR(
            det_use_cuda=use_cuda, cls_use_cuda=use_cuda, rec_use_cuda=use_cuda
        )
    except ImportError:
        from rapidocr_onnxruntime import RapidOCR

        ocr = RapidOCR()
    return ocr

if __name__ == "__main__":
    ocr = get_ocr()
    text = ocr('/data/projects/JqChat/jqcode/jq_knowledge_manegement/chatchat/img/logo-long-chatchat-trans-v2.png')
    print(text)