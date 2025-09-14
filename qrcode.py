from maix import image, camera, display

cam = camera.Camera(320, 240)
disp = display.Display()

while 1:
    img = cam.read()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    disp.show(img)
    texts = pyzbar.decode(gray)
    for text in texts:
        tt = text.data.decode("utf-8")
    print(tt)
 
