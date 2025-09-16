from maix import image, uart, camera, display, pinmap, err
from typing import Literal

device = "/dev/ttyS1"
pin_function = {
        "A19": "UART1_TX",
        "A18": "UART1_RX"
    }
for pin, func in pin_function.items():
    err.check_raise(pinmap.set_pin_function(pin, func), f"Failed set pin{pin} function to {func}")

serial0 = uart.UART(device, 115200)

cam = camera.Camera(640, 480 ,image.Format.FMT_GRAYSCALE)
disp = display.Display()

def int_to_bytes(n: int, byteorder: Literal['big', 'little'] = 'big', signed: bool = False, byte_count: int = None, truncate: bool = False):
    """
    将整数 n 转成字节序列，并返回 (bytes, used_byte_count)。

    - 如果 byte_count 为 None，则自动计算最小字节数并返回对应长度的 bytes。
    - 如果 byte_count 指定且 truncate=False，则在 byte_count 不足以表示 n 时会回退为最小所需字节数并返回该长度的 bytes（避免 OverflowError）。
    - 如果 byte_count 指定且 truncate=True，则对低位进行截断（无符号按位截断，带符号按两补截断）。
    - byteorder: 'big' 或 'little'
    - signed: 是否按带符号整数处理（两补表示）
    返回值: (b: bytes, used_len: int)
    """
    # 自动计算最小字节数
    def _min_bytes_needed(val: int, is_signed: bool) -> int:
        if val == 0:
            return 1
        if is_signed:
            for k in range(1, 9):
                minv = -(1 << (k * 8 - 1))
                maxv = (1 << (k * 8 - 1)) - 1
                if minv <= val <= maxv:
                    return k
            return 8
        else:
            if val < 0:
                val = -val
            return max(1, (val.bit_length() + 7) // 8)

    if byte_count is None:
        byte_count = _min_bytes_needed(n, signed)

    # 如果不截断且可能溢出，尝试直接转换，捕获 OverflowError 并回退到最小长度
    if not truncate:
        try:
            b = int.to_bytes(n, length=byte_count, byteorder=byteorder, signed=signed)
            return b, byte_count
        except OverflowError:
            # 计算最小字节数并返回
            min_len = _min_bytes_needed(n, signed)
            b = int.to_bytes(n, length=min_len, byteorder=byteorder, signed=signed)
            return b, min_len
    else:
        # 截断到指定字节数
        if signed:
            mask = (1 << (byte_count * 8)) - 1
            val = (n + (1 << (byte_count * 8))) & mask
            return val.to_bytes(byte_count, byteorder), byte_count
        else:
            mask = (1 << (byte_count * 8)) - 1
            val = n & mask
            return val.to_bytes(byte_count, byteorder), byte_count

def parse_payload_to_bytes(payload_str: str) -> bytes:
    """
    将传入的字符串 payload_str 解析为要发送的 bytes。

    解析规则（保持与原 build_qrcode_packet 一致）：
    - 先 strip()，去掉 0x/0X 前缀以及空格
    - 如果原始字符串全为十进制数字（s.isdigit()），将其当作十进制整数转换为十六进制字节
    - 否则如果 clean 全为十六进制字符，则按 hex 解析
    - 其它情况按 utf-8 编码
    """
    s = (payload_str or "").strip()
    clean = s.replace('0x', '').replace('0X', '').replace(' ', '')
    payload_bytes = b''
    if len(clean) > 0:
        # 如果原始字符串只包含十进制数字，按十进制整数转换为十六进制字节
        if s.isdigit():
            try:
                n = int(s)
                hexstr = format(n, 'X')  # 不带 0x
                if len(hexstr) % 2 == 1:
                    hexstr = '0' + hexstr
                payload_bytes = bytes.fromhex(hexstr)
            except Exception:
                payload_bytes = payload_str.encode('utf-8')
        else:
            try:
                import re
                if re.fullmatch(r'[0-9A-Fa-f]+', clean):
                    if len(clean) % 2 == 1:
                        clean = '0' + clean
                    payload_bytes = bytes.fromhex(clean)
                else:
                    payload_bytes = payload_str.encode('utf-8')
            except Exception:
                payload_bytes = payload_str.encode('utf-8')
    else:
        payload_bytes = b''

    return payload_bytes

def make_packet(payload, cmd: int = 0x00):
    """
    构建要通过串口发送的包，支持 payload 为 str/bytes/int。

    新包格式（无长度、无尾0x00）:
    [0xA5][cmd:1][payload...][checksum:1]

    - payload: 如果是 bytes，直接使用；如果是 int，使用 int_to_bytes 自动生成最小字节序列；否则按字符串解析 parse_payload_to_bytes。
    - checksum: 计算包含头、命令及 payload 的简单和校验 (mod 256)
    返回构建好的 bytes 包。
    """
    # 解析 payload
    if isinstance(payload, bytes):
        payload_bytes = payload
    elif isinstance(payload, int):
        payload_bytes, _ = int_to_bytes(payload, byteorder='big', signed=False)
    else:
        payload_bytes = parse_payload_to_bytes(str(payload))

    # 加回长度字节（1 字节），并把长度计入校验
    length = len(payload_bytes) & 0xFF
    checksum = (0xA5 + (cmd & 0xFF) + length + sum(payload_bytes)) & 0xFF
    return bytes([0xA5, cmd & 0xFF, length]) + payload_bytes + bytes([checksum])

while 1:
    img = cam.read()
    # img = img.lens_corr(strength=1.5)

    qrcodes = img.find_qrcodes()
    barcodes = img.find_barcodes()



    # 优先处理 barcode：如果同时扫到 QR code 和 barcode，只处理 barcode
    if barcodes:
        for b in barcodes:
            rect = b.rect()
            img.draw_rect(rect[0], rect[1], rect[2], rect[3], image.COLOR_BLUE, 2)
            payload_str = b.payload()
            cmd = 0x01  # 条码使用命令字 0x01
            packet = make_packet(payload_str, cmd)
            img.draw_string(b.x(), b.y() - 15, "payload: " + b.payload(), image.COLOR_GREEN)
            try:
                serial0.write(packet)
                print("Sent packet:", packet)
            except Exception:
                print("Failed to send packet:", packet)
                pass
    elif qrcodes:
        for qr in qrcodes:
            corners = qr.corners()
            for i in range(4):
                img.draw_line(corners[i][0], corners[i][1], corners[(i + 1) % 4][0], corners[(i + 1) % 4][1], image.COLOR_RED)
            img.draw_string(qr.x(), qr.y() - 15, qr.payload(), image.COLOR_RED)
            payload_str = qr.payload()
            cmd = 0x00  # QR code 使用命令字 0x00
            # 构建并发送数据包
            packet = make_packet(payload_str, cmd)
            try:
                serial0.write(packet)
                print("Sent packet:", packet)
            except Exception:
                print("Failed to send packet:", packet)
                pass
    disp.show(img)
