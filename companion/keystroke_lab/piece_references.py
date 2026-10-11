"""Conservative recognition of reviewed piece views, independent of grid size.

Feature correspondence supplies a local homography and piece label. This is
reference-view recognition, not a claim to recognize arbitrary builds. Unknown
views abstain. Labels describe the original piece, never accepted edit success.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import cv2
import numpy as np

@dataclass(frozen=True)
class ReferenceMatch:
    piece: str
    quad: tuple
    reference_id: str
    inliers: int
    error_px: float
    source: str = 'reviewed_visual_reference'

class PieceReferenceRecognizer:
    def __init__(self, manifest):
        manifest=Path(manifest)
        self.extractor=cv2.SIFT_create(nfeatures=2400,contrastThreshold=.003,edgeThreshold=20)
        self.references=[]
        for entry in json.loads(manifest.read_text())['references']:
            image=cv2.imread(str(manifest.parent/entry['image']))
            if image is None:continue
            scale=min(1.,960/image.shape[1])
            image=cv2.resize(image,None,fx=scale,fy=scale)
            gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
            mask=np.zeros(gray.shape,np.uint8)
            for region in entry['regions']:
                cv2.fillPoly(mask,[np.int32(np.asarray(region)*scale)],255)
            # HUD correspondence is not evidence about the piece. In particular
            # the edit crosshair alone can produce many duplicate SIFT points.
            centre=entry.get('crosshair',[image.shape[1]/(2*scale),image.shape[0]/(2*scale)])
            cv2.circle(mask,tuple(int(v*scale) for v in centre),int(48*scale),0,-1)
            keys,desc=self.extractor.detectAndCompute(gray,mask)
            if desc is not None:self.references.append((entry,scale,gray,mask,keys,desc))

    def recognize(self, image, aim):
        scale=min(1.,960/image.shape[1])
        small=cv2.resize(image,None,fx=scale,fy=scale)
        gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
        keys,desc=self.extractor.detectAndCompute(gray,None)
        if desc is None:return None
        results=[]
        for entry,ref_scale,reference,mask,rkeys,rdesc in self.references:
            pairs=cv2.BFMatcher().knnMatch(rdesc,desc,k=2)
            good=[p[0] for p in pairs if len(p)==2 and p[0].distance<.65*p[1].distance]
            # SIFT may produce several orientations at one physical point.
            unique={tuple(round(v,1) for v in rkeys[m.queryIdx].pt):m for m in good}
            good=list(unique.values())
            if len(good)<8:continue
            src=np.float32([rkeys[m.queryIdx].pt for m in good])
            dst=np.float32([keys[m.trainIdx].pt for m in good])
            H,inliers=cv2.findHomography(src,dst,cv2.RANSAC,2.5)
            if H is None or inliers is None:continue
            keep=inliers.ravel().astype(bool)
            if keep.sum()<8 or keep.mean()<.75:continue
            # Require spatially distributed support, not a single repeated icon.
            support=cv2.contourArea(cv2.convexHull(src[keep]))
            if support<.18*cv2.countNonZero(mask):continue
            quad=cv2.perspectiveTransform(np.float32([entry['quad']])*ref_scale,H)[0]
            if not cv2.isContourConvex(quad):continue
            if cv2.pointPolygonTest(quad,tuple(float(v*scale) for v in aim),False)<0:continue
            # The complete reviewed appearance must agree, including the ghost
            # mesh. Matching blue regions alone cannot distinguish these pieces.
            aligned=cv2.warpPerspective(gray,np.linalg.inv(H),(reference.shape[1],reference.shape[0]))
            a=reference[mask>0].astype(float);b=aligned[mask>0].astype(float)
            if a.std()<5 or b.std()<5:continue
            correlation=float(np.corrcoef(a,b)[0,1])
            if not np.isfinite(correlation) or correlation<.90:continue
            error=float(np.median(np.linalg.norm(cv2.perspectiveTransform(src[keep,None],H)[:,0]-dst[keep],axis=1)))
            results.append((correlation,ReferenceMatch(entry['piece'],tuple(tuple(float(v) for v in row) for row in quad/scale),
                           entry['id'],int(keep.sum()),error)))
        results.sort(key=lambda r:r[0],reverse=True)
        if not results:return None
        if len(results)>1 and results[0][1].piece!=results[1][1].piece and results[0][0]-results[1][0]<.05:return None
        return results[0][1]
