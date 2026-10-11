"""Bounded four-region acquisition using blue tile boundaries, not piece identity.

The translucent result mesh must supply floor/cone/stair identity separately.
This fallback never promotes a 2x2 grid to a verified build type.
"""
import cv2
import numpy as np
from .edit_observation import _general_grid, _mask_hud

def flat_grid(image, aim, segments, budget=.035):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([90,220,90]),np.array([115,255,255]))
    _mask_hud(mask)
    mask=cv2.erode(mask,np.ones((3,3),np.uint8))
    extra=[];h,w=image.shape[:2]
    contours=sorted(cv2.findContours(mask,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)[0],
                    key=cv2.contourArea,reverse=True)[:20]
    for contour in contours:
        area=cv2.contourArea(contour)
        if not .002*w*h<area<.25*w*h:continue
        quad=cv2.approxPolyDP(contour,.025*cv2.arcLength(contour,True),True).reshape(-1,2)
        if len(quad)!=4 or not cv2.isContourConvex(quad):continue
        for a,b in zip(quad,np.roll(quad,-1,axis=0)):
            extra.append((*map(float,a),*map(float,b),float(np.linalg.norm(b-a))))
    if len(extra)<8:return None
    return _general_grid(image,aim,budget=budget,segs=extra+segments,sizes=(2,),min_area=.025)
