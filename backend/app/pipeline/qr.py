from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np
import pymupdf

def parse_qr_payload(payload: str) -> Dict[str, Any]:
    parts = payload.strip().split("|")
    result: Dict[str, Any] = {"raw": payload}

    if len(parts) >= 4 and parts[0] == "MOCKVERIFY":
        result["issuer"] = parts[1]
        result["type"] = parts[2]
        result["reference"] = parts[3]

        for item in parts[4:]:
            if "=" in item:
                k, v = item.split("=", 1)
                result[k.strip().lower()] = v.strip()
    return result

def detect_and_decode_qr(doc: pymupdf.Document) -> Tuple[Optional[Dict[str, Any]], Optional[list], int]:
    """
    Renders pages at 150, 200, 300 dpi and uses OpenCV QRCodeDetector.
    Returns: (parsed_qr_dict, bbox_points, page_number)
    """
    detector = cv2.QRCodeDetector()

    for pno in range(len(doc)):
        page = doc[pno]
        for dpi in [150, 200]:
            pix = page.get_pixmap(dpi=dpi)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            elif pix.n == 1:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            val, points, _ = detector.detectAndDecode(img)
            if val and "MOCKVERIFY" in val:
                bbox = None
                if points is not None and len(points) > 0:
                    pts = points[0] if len(points.shape) == 3 else points
                    min_x = round(float(np.min(pts[:, 0])) * 72.0 / dpi, 1)
                    min_y = round(float(np.min(pts[:, 1])) * 72.0 / dpi, 1)
                    max_x = round(float(np.max(pts[:, 0])) * 72.0 / dpi, 1)
                    max_y = round(float(np.max(pts[:, 1])) * 72.0 / dpi, 1)
                    bbox = [min_x, min_y, max_x, max_y]

                parsed_data = parse_qr_payload(val)
                return parsed_data, bbox, pno + 1

    return None, None, 1
