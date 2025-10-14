from maix import image, camera, display, app, time
import cv2
import numpy as np

MIN_AREA = 2000
MAX_AREA = 80000

cam = camera.Camera(320, 240, fps=60)
disp = display.Display()

def is_rectangle(approx):
    if approx is None or len(approx) != 4 or not cv2.isContourConvex(approx):
        return False
    pts = [point[0] for point in approx]
    def angle(p1, p2, p3):
        v1 = np.array(p1) - np.array(p2)
        v2 = np.array(p3) - np.array(p2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0
        cos_angle = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
        return np.arccos(cos_angle) * 180 / np.pi
    angles = [angle(pts[i - 1], pts[i], pts[(i + 1) % 4]) for i in range(4)]
    return all(80 < ang < 100 for ang in angles)

while not app.need_exit():
    img = cam.read()
    if img is None:
        continue

    img_raw = image.image2cv(img, copy=True)
    inner_rect = None

    gray = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
    bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY, 11, 2)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    valid_rects = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (MIN_AREA <= area <= MAX_AREA):
            continue

        x, y, w, h = cv2.boundingRect(contour)
        margin = 1
        if x < margin or y < margin or x + w > img_raw.shape[1] - margin or y + h > img_raw.shape[0] - margin:
                continue
        
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if is_rectangle(approx):
            rect = [tuple(pt[0]) for pt in approx]
            perimeter = cv2.arcLength(contour, True)
            valid_rects.append((rect, area, perimeter))

    if valid_rects:
        # 根据周长筛选出边长最短的矩形
        inner_rect, _, _ = min(valid_rects, key=lambda x: x[2])
        # 绘制角点和边长最短的矩形
        
        for x, y in inner_rect:
            cv2.circle(img_raw, (x, y), 5, (0, 0, 255), -1)
        cv2.drawContours(img_raw, [np.array(inner_rect, dtype=np.int32)], -1, (0, 255, 0), 2)

    img_out = image.cv2image(img_raw, copy=False)
    disp.show(img_out)