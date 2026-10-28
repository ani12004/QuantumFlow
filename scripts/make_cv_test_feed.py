"""Fake browser camera from a public test image; never opens a physical camera."""
import _bootstrap
import cv2,numpy as np
if __name__=='__main__':
    image=cv2.imread(str(_bootstrap.ROOT/'data/raw/cv_test/bus.jpg'))
    canvas=np.full((480,640,3),114,dtype=np.uint8)
    ratio=min(640/image.shape[1],480/image.shape[0]);w,h=round(image.shape[1]*ratio),round(image.shape[0]*ratio)
    x,y=(640-w)//2,(480-h)//2;canvas[y:y+h,x:x+w]=cv2.resize(image,(w,h))
    output=_bootstrap.ROOT/'tmp/cv_test';output.mkdir(parents=True,exist_ok=True)
    with (output/'public_sample.y4m').open('wb') as f:
        f.write(b'YUV4MPEG2 W640 H480 F5:1 Ip A1:1 C420jpeg\n')
        data=cv2.cvtColor(canvas,cv2.COLOR_BGR2YUV_I420).tobytes()
        for _ in range(5):f.write(b'FRAME\n');f.write(data)
    print('Fake test-camera file prepared; no webcam accessed.')
