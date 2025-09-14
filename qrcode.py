from maix import image, uart, camera, display, pinmap, err

device = "/dev/ttyS1"
pin_function = {
        "A19": "UART1_TX",
        "A18": "UART1_RX"
    }
for pin, func in pin_function.items():
    err.check_raise(pinmap.set_pin_function(pin, func), f"Failed set pin{pin} function to {func}")

serial0 = uart.UART(device, 115200)

cam = camera.Camera(320, 240)
disp = display.Display()

def build_qrcode_packet(payload_str, cmd=0x00):
    s = (payload_str or "").strip()
    # 先去掉常见分隔/前缀
    clean = s.replace('0x','').replace('0X','').replace(' ','')
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
            # 如果 clean 全为十六进制字符，则按 hex 解析
            try:
                import re
                if re.fullmatch(r'[0-9A-Fa-f]+', clean):
                    if len(clean) % 2 == 1:
                        clean = '0' + clean
                    payload_bytes = bytes.fromhex(clean)
                else:
                    # 其它情况按 utf-8 编码
                    payload_bytes = payload_str.encode('utf-8')
            except Exception:
                payload_bytes = payload_str.encode('utf-8')
    else:
        payload_bytes = b''
    # 在 payload 后追加一个 0x00
    tail_zero = bytes([0x00])
    # 校验和：包含帧头 0xA5、命令字、payload 字节以及追加的 0x00
    checksum = (0xA5 + (cmd & 0xFF) + sum(payload_bytes) + 0x00) & 0xFF
    return bytes([0xA5, cmd & 0xFF]) + payload_bytes + tail_zero + bytes([checksum])

while 1:
    img = cam.read()
    qrcodes = img.find_qrcodes()
    for qr in qrcodes:
        corners = qr.corners()
        for i in range(4):
            img.draw_line(corners[i][0], corners[i][1], corners[(i + 1) % 4][0], corners[(i + 1) % 4][1], image.COLOR_RED)
        img.draw_string(qr.x(), qr.y() - 15, qr.payload(), image.COLOR_RED)
        payload_str = qr.payload()
        cmd = 0x00  # 这里可以改为需要的命令字，比如 0x01
        packet = build_qrcode_packet(payload_str, cmd)
        serial0.write(packet)
    disp.show(img)
