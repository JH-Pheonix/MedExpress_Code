from maix import camera, display,app,time

cam = camera.Camera(320, 240)
disp = display.Display()
while not app.need_exit():
    t = time.ticks_ms()
    img = cam.read() 
    img = img.lens_corr(strength=1.7)	# 调整strength的值直到画面不再畸变
    disp.show(img)