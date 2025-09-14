import cv2
import numpy as np

# 尝试导入 pyzbar 用于条形码/二维码内容解码（可选）
try:
    from pyzbar.pyzbar import decode as zbar_decode
    _PYZBAR_AVAILABLE = True
except Exception:
    _PYZBAR_AVAILABLE = False


def barcode(image, debug=False):
    """检测图像中的条形码并返回定位信息。

    参数:
    - image: BGR 图像 (numpy 数组)
    - debug: 若为 True，会显示中间处理结果窗口，便于调试

    返回:
    - 如果找到条形码，返回一个字典：{
        'box': 4x2 的整型点坐标 (numpy array),
        'rect': (x, y, w, h) 轴对齐边界框,
        'roi': 裁切出的条形码图像 (BGR)
      }
      并且在输入图像上绘制定位框。
    - 如果未找到条形码，返回 None。
    """
    if image is None:
        return None

    # 灰度化
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 使用 Sobel 在 x 方向提取竖直条纹特征（条形码在 x 方向有强梯度）
    gradX = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=3)
    gradX = cv2.convertScaleAbs(gradX)
    if debug:
        cv2.imshow('gradX', gradX)

    # 高斯模糊以降低噪声
    blur = cv2.GaussianBlur(gradX, (9, 9), 0)
    if debug:
        cv2.imshow('blur', blur)

    # OTSU 二值化
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if debug:
        cv2.imshow('thresh', thresh)

    # 形态学操作：先闭运算以连接条形码的竖条，再适当腐蚀/膨胀去掉小噪点
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    closed = cv2.erode(closed, None, iterations=4)
    closed = cv2.dilate(closed, None, iterations=4)
    if debug:
        cv2.imshow('closed', closed)

    # 查找外部轮廓
    contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # 选取面积最大的轮廓作为条形码区域
    c = max(contours, key=cv2.contourArea)

    # 使用最小外接矩形（可旋转）提高定位精度
    rect = cv2.minAreaRect(c)
    box = cv2.boxPoints(rect)
    # np.int0 is deprecated/removed in some numpy versions; use astype(int) for portable integer coords
    box = box.astype(int)

    # 在输入图像上绘制检测到的条形码区域
    cv2.drawContours(image, [box], -1, (0, 255, 0), 2)

    # 计算轴对齐边界框并裁切 ROI
    x, y, w, h = cv2.boundingRect(box)
    # 保护边界
    h_img, w_img = image.shape[:2]
    x = max(0, x)
    y = max(0, y)
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    roi = image[y:y+h, x:x+w].copy() if w > 0 and h > 0 else None

    decoded_list = None
    # 如果可用，使用 pyzbar 解码 ROI 中的条码/二维码
    if roi is not None and _PYZBAR_AVAILABLE:
        try:
            decoded = zbar_decode(roi)
            decoded_list = []
            for d in decoded:
                try:
                    data = d.data.decode('utf-8')
                except Exception:
                    data = d.data
                decoded_list.append({'type': d.type, 'data': data, 'rect': d.rect, 'polygon': getattr(d, 'polygon', None)})
                # 在图像上绘制识别到的文本（红色）
                text = f"{d.type}:{data}"
                cv2.putText(image, text, (x, max(0, y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        except Exception:
            decoded_list = None

    # 返回检测结果，同时包含解码信息（如果有）
    return {'box': box, 'rect': (x, y, w, h), 'roi': roi, 'decoded': decoded_list}

# if __name__ == '__main__':
#     img = cv2.imread('test.png')
#     res = barcode(img, debug=True)
#     if res is not None:
#         print('found', res['rect'])
#     cv2.imshow('result', img)
#     cv2.waitKey(0)
#     cv2.destroyAllWindows()

if __name__ == '__main__':
    img_path = 'test22.png'
    img = cv2.imread(img_path)
    if img is None:
        print(f'无法读取图像: {img_path}')
        return

    # 不显示中间调试窗口，只返回结果和 ROI
    res = barcode(img, debug=False)
    if res is None:
        print('未检测到条形码')
    else:
        print('检测到条形码 rect:', res['rect'])
        # 打印解码结果（如果有）
        decoded = res.get('decoded')
        if decoded:
            for d in decoded:
                print(f"解码类型: {d['type']}, 内容: {d['data']}")
        else:
            print('未解码到内容（未安装 pyzbar 或解码失败）')
        # 如果有旋转 box，绘制已在函数中完成；这里再高亮 ROI
        roi = res.get('roi')
        if roi is not None:
            # 不保存 ROI
            pass
        cv2.imwrite('barcode_result.png', img)

    cv2.imshow('barcode_result', img)
    print('按任意键关闭窗口...')
    cv2.waitKey(0)
    cv2.destroyAllWindows()
