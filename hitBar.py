import numpy as np;
import cv2;
from typing import List, Dict, Any, Optional, Tuple;

class hitBar:
    """
    **Description**  
    A 'hit bar' that attaches to a detector to count the moving objects that cross from realmIn to realmOut. 
    realmIn is on the negative side of the line's normal, realmOut is on the positive side.

    **Properties**  
    - `imgOut`: The output image.
    - `imgSize`: The size of the reference image (height, width).
    - `startPoint`: The start point of the hit bar (x, y).
    - `endPoint`: The end point of the hit bar (x, y).
    - `direction`: The normal vector of the line from startPoint to endPoint.
    - `width`: The half-thickness (in pixels) for realmIn & realmOut.
    - `maxLength`: The maximum length of the history buffer. If exceeded, the oldest frame will be removed.
    - `realmIn`: The negative-side realm (4 points).
    - `realmOut`: The positive-side realm (4 points).
    - `name`: The name of the hit bar for debugging/logging.
    - `visualize`: Whether to draw the hit bar and realms in update method if an image is provided.
    - `history`: A list storing the previous frames' detection results.
    - `monitoredCatagories`: The categories that need to be counted or checked.
    - `Accumulator`: A dictionary counting the crossing events.

    **Methods**  
    - `__init__`: Initialize the hit bar with geometry and optional visualization switch.
    - `_monitor`: Monitor the hit bar with a list of categories.
    - `update`: Update the hit bar with a new detection result (the main logic to check crossing).
    - `_hasIn`: Check if this target was in realmIn in a previous frame.
    - `_inRealm`: Internal method to check if a point is inside a 4-point polygon realm.
    """
    def __init__(
        self,
        imgSize: Tuple[int,int] = None,
        startPoint: Optional[Tuple[int,int]] = None,
        endPoint: Optional[Tuple[int,int]] = None,
        name: str = "hitBar",
        monitor: Optional[List[str]] = None,
        width: float = 5.0,
        maxLength: int = 50,
        visualize: bool = True
    ):
        """
        **Description**  
        Initialize the hit bar.
        
        **Params**  
        - `img`: np.ndarray, A reference image used mainly for shape or optional drawing.
        - `startPoint`: Tuple (x, y) for the start point of the bar. If None, defaults to (0, midRow).
        - `endPoint`: (x, y) for the end point of the bar. If None, defaults to (imgWidth, midRow).
        - `name`: The name of this hit bar.
        - `monitor`: Optional initial categories to be monitored.
        - `width`: The thickness in pixel used to build realmIn/realmOut on either side.
        - `visualize`: Whether we draw the bar & realms in `update` if an image is provided.

        **Returns**  
        None;
        """
        self.name: str = name;
        self.visualize = visualize;
        self.imgSize: Tuple[int,int] = imgSize;

        if not startPoint or not endPoint:
            mid_row = self.imgSize[0] // 2;
            self.startPoint = (0, mid_row);
            self.endPoint   = (self.imgSize[1], mid_row);
        else:
            self.startPoint = startPoint;
            self.endPoint   = endPoint;
            
        self.maxLength: int = maxLength;
        self.width: float = width;
        dx = self.endPoint[0] - self.startPoint[0];
        dy = self.endPoint[1] - self.startPoint[1];

        n = np.array([-dy, dx], dtype=np.float32);
        norm_n = np.linalg.norm(n);
        if norm_n < 1e-6:
            # Degenerate line
            self.direction = np.array([0,0], dtype=np.float32);
            self.realmIn  = np.array([self.startPoint]*4, dtype=np.float32);
            self.realmOut = np.array([self.endPoint]*4,   dtype=np.float32);
        else:
            self.direction = n / norm_n;

            A = np.array(self.startPoint, dtype=np.float32);
            B = np.array(self.endPoint,   dtype=np.float32);

            offsetIn  = -self.width * self.direction;
            offsetOut =  self.width * self.direction;

            AIn  = A + offsetIn;
            BIn  = B + offsetIn;
            AOut = A + offsetOut;
            BOut = B + offsetOut;

            self.realmIn  = np.array([A, B, BIn,  AIn],  dtype=np.float32);
            self.realmOut = np.array([A, B, BOut, AOut], dtype=np.float32);

        self.history: List[Dict[str,Any]] = [];
        self.Accumulator: Dict[str,int] = {};
        self.monitoredCatagories: List[str] = [];

        if monitor:
            self._monitor(monitor);

    def _monitor(self, categories: List[str]) -> None:
        """
        **Description**  
        Set or add categories to be monitored by this hit bar.

        **Params**  
        - `categories`: List[str], A list of category names to be monitored.

        **Returns**  
        None;
        """
        for cat in categories:
            if cat not in self.Accumulator:
                self.Accumulator[cat] = 0;
        self.monitoredCatagories = list(set(self.monitoredCatagories + categories));

    def update(self, img: np.ndarray, detailedResult: Dict[str,Any]) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """
        **Description**  
        Update the hit bar with a new detection result.
        If `visualize=True` and 'img' in the result, draw realms on it.
        For each monitored target, check if crossing realmIn => realmOut.

        **Params**  
        - `detailedResult`: The detection info from Detector, recommended

        **Returns**  
        (imgOut, self.Accumulator)  
        - `imgOut`: The new image with the bar drawn (if visualize & 'img' present)
        - `Accumulator`: The counters for each category
        - 
        """
        

        self.history.append(detailedResult);
        if len(self.history) > self.maxLength:
            self.history.pop(0);

        self.imgOut = img.copy();
        if self.visualize:
            # Draw line => red
            cv2.line(self.imgOut, self.startPoint, self.endPoint, (0,0,255), 2);
            # realmIn => green
            pts_in  = np.int32(self.realmIn.reshape(-1,1,2));
            cv2.polylines(self.imgOut, [pts_in], True, (0,255,0), 2);
            # realmOut => blue
            pts_out = np.int32(self.realmOut.reshape(-1,1,2));
            cv2.polylines(self.imgOut, [pts_out], True, (255,0,0), 2);

        labels    = detailedResult.get("labels", []);
        IDs       = detailedResult.get("IDs", []);
        midPoints = detailedResult.get("midPoints", []);
        # print(midPoints);

        for idx, pt in enumerate(midPoints):
            # print(pt);
            cat = labels[idx];
            if cat not in self.monitoredCatagories:
                continue;
            objID = IDs[idx] if len(IDs) == len(labels) else idx;

            numInCat = None;
            if "numProjection" in detailedResult and cat in detailedResult["numProjection"]:
                arr = [x[1] for x in detailedResult["numProjection"][cat] if x[0] == objID];
                if arr:
                    numInCat = arr[0];

            if self._inRealm(pt, self.realmOut):
                if self._hasIn(pt, cat, objID, numInCat):
                    self.Accumulator[cat] += 1;
                    print(f"[{self.name}] {cat} No.{numInCat} (ID={objID})  count={self.Accumulator[cat]};");

        return self.imgOut, self.Accumulator;

    def _hasIn(self, pt: Tuple[int, int], cat: str, objID: int, numInCat: Optional[int]) -> bool:
        """
        **Description**  
        Check if the target (cat, objID) was in realmIn in a previous frame.

        **Params**  
        - `pt`: The point that has been in the realmOut.
        - `cat`: The category name.
        - `objID`: The object ID in that category.
        - `numInCat`: If used to differentiate multiple objects with same cat.

        **Returns**  
        bool, True if found in realmIn before, else False.
        """
        import numpy as np;
import cv2;
from typing import List, Dict, Any, Optional, Tuple;

class hitBar:
    """
    **Description**  
    A 'hit bar' that attaches to a detector to count the moving objects that cross from realmIn to realmOut. 
    realmIn is on the negative side of the line's normal, realmOut is on the positive side.

    **Properties**  
    - `imgOut`: The output image.
    - `imgSize`: The size of the reference image (height, width).
    - `startPoint`: The start point of the hit bar (x, y).
    - `endPoint`: The end point of the hit bar (x, y).
    - `direction`: The normal vector of the line from startPoint to endPoint.
    - `width`: The half-thickness (in pixels) for realmIn & realmOut.
    - `maxLength`: The maximum length of the history buffer. If exceeded, the oldest frame will be removed.
    - `realmIn`: The negative-side realm (4 points).
    - `realmOut`: The positive-side realm (4 points).
    - `name`: The name of the hit bar for debugging/logging.
    - `visualize`: Whether to draw the hit bar and realms in update method if an image is provided.
    - `history`: A list storing the previous frames' detection results.
    - `monitoredCatagories`: The categories that need to be counted or checked.
    - `Accumulator`: A dictionary counting the crossing events.

    **Methods**  
    - `__init__`: Initialize the hit bar with geometry and optional visualization switch.
    - `_monitor`: Monitor the hit bar with a list of categories.
    - `update`: Update the hit bar with a new detection result (the main logic to check crossing).
    - `_hasIn`: Check if this target was in realmIn in a previous frame.
    - `_inRealm`: Internal method to check if a point is inside a 4-point polygon realm.
    """
    def __init__(
        self,
        imgSize: Tuple[int,int] = None,
        startPoint: Optional[Tuple[int,int]] = None,
        endPoint: Optional[Tuple[int,int]] = None,
        name: str = "hitBar",
        monitor: Optional[List[str]] = None,
        width: float = 5.0,
        maxLength: int = 50,
        visualize: bool = True
    ):
        """
        **Description**  
        Initialize the hit bar.
        
        **Params**  
        - `img`: np.ndarray, A reference image used mainly for shape or optional drawing.
        - `startPoint`: Tuple (x, y) for the start point of the bar. If None, defaults to (0, midRow).
        - `endPoint`: (x, y) for the end point of the bar. If None, defaults to (imgWidth, midRow).
        - `name`: The name of this hit bar.
        - `monitor`: Optional initial categories to be monitored.
        - `width`: The thickness in pixel used to build realmIn/realmOut on either side.
        - `visualize`: Whether we draw the bar & realms in `update` if an image is provided.

        **Returns**  
        None;
        """
        self.name: str = name;
        self.visualize = visualize;
        self.imgSize: Tuple[int,int] = imgSize;

        if not startPoint or not endPoint:
            mid_row = self.imgSize[0] // 2;
            self.startPoint = (0, mid_row);
            self.endPoint   = (self.imgSize[1], mid_row);
        else:
            self.startPoint = startPoint;
            self.endPoint   = endPoint;
            
        self.maxLength: int = maxLength;
        self.width: float = width;
        dx = self.endPoint[0] - self.startPoint[0];
        dy = self.endPoint[1] - self.startPoint[1];

        n = np.array([-dy, dx], dtype=np.float32);
        norm_n = np.linalg.norm(n);
        if norm_n < 1e-6:
            # Degenerate line
            self.direction = np.array([0,0], dtype=np.float32);
            self.realmIn  = np.array([self.startPoint]*4, dtype=np.float32);
            self.realmOut = np.array([self.endPoint]*4,   dtype=np.float32);
        else:
            self.direction = n / norm_n;

            A = np.array(self.startPoint, dtype=np.float32);
            B = np.array(self.endPoint,   dtype=np.float32);

            offsetIn  = -self.width * self.direction;
            offsetOut =  self.width * self.direction;

            AIn  = A + offsetIn;
            BIn  = B + offsetIn;
            AOut = A + offsetOut;
            BOut = B + offsetOut;

            self.realmIn  = np.array([A, B, BIn,  AIn],  dtype=np.float32);
            self.realmOut = np.array([A, B, BOut, AOut], dtype=np.float32);

        self.history: List[Dict[str,Any]] = [];
        self.Accumulator: Dict[str,int] = {};
        self.monitoredCatagories: List[str] = [];

        if monitor:
            self._monitor(monitor);

    def _monitor(self, categories: List[str]) -> None:
        """
        **Description**  
        Set or add categories to be monitored by this hit bar.

        **Params**  
        - `categories`: List[str], A list of category names to be monitored.

        **Returns**  
        None;
        """
        for cat in categories:
            if cat not in self.Accumulator:
                self.Accumulator[cat] = 0;
        self.monitoredCatagories = list(set(self.monitoredCatagories + categories));

    def update(self, img: np.ndarray, detailedResult: Dict[str,Any]) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """
        **Description**  
        Update the hit bar with a new detection result.
        If `visualize=True` and 'img' in the result, draw realms on it.
        For each monitored target, check if crossing realmIn => realmOut.

        **Params**  
        - `detailedResult`: The detection info from Detector, recommended

        **Returns**  
        (imgOut, self.Accumulator)  
        - `imgOut`: The new image with the bar drawn (if visualize & 'img' present)
        - `Accumulator`: The counters for each category
        - 
        """
        

        self.history.append(detailedResult);
        if len(self.history) > self.maxLength:
            self.history.pop(0);

        # Recalculate realmIn and realmOut as parallelograms
        A = np.array(self.startPoint, dtype=np.float32);
        B = np.array(self.endPoint, dtype=np.float32);
        
        offsetIn  = -self.width * self.direction;
        offsetOut = self.width * self.direction;

        AIn  = A + offsetIn;
        BIn  = B + offsetIn;
        AOut = A + offsetOut;
        BOut = B + offsetOut;

        self.realmIn  = np.array([AIn, BIn, B, A], dtype=np.float32);
        self.realmOut = np.array([AOut, BOut, B, A], dtype=np.float32);

        # Create an overlay for transparency
        overlay = img.copy();

        # Convert realmIn and realmOut to integer points
        ptsIn  = np.int32(self.realmIn.reshape(-1,1,2));
        ptsOut = np.int32(self.realmOut.reshape(-1,1,2));

        # Fill the realms with semi-transparent colors
        cv2.fillPoly(overlay, [ptsIn], (0,0,255,100));  # Red with transparency
        cv2.fillPoly(overlay, [ptsOut], (255,0,0,100));  # Blue with transparency

        # Blend the overlay with the original image
        alpha = 0.4;  # Transparency level (0: fully transparent, 1: fully opaque)
        self.imgOut = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0);

        if self.visualize:
            # Draw the centerline in solid red
            cv2.line(self.imgOut, self.startPoint, self.endPoint, (0,0,255), 2);

        labels    = detailedResult.get("labels", []);
        IDs       = detailedResult.get("IDs", []);
        midPoints = detailedResult.get("midPoints", []);

        for idx, pt in enumerate(midPoints):
            cat = labels[idx];
            if cat not in self.monitoredCatagories:
                continue;
            objID = IDs[idx] if len(IDs) == len(labels) else idx;

            numInCat = None;
            if "numProjection" in detailedResult and cat in detailedResult["numProjection"]:
                arr = [x[1] for x in detailedResult["numProjection"][cat] if x[0] == objID];
                if arr:
                    numInCat = arr[0];

            if self._inRealm(pt, self.realmOut):
                if self._hasIn(pt, cat, objID, numInCat):
                    self.Accumulator[cat] += 1;
                    print(f"[{self.name}] {cat} No.{numInCat} (ID={objID})  count={self.Accumulator[cat]};");

        return self.imgOut, self.Accumulator;

    def _hasIn(self, pt: Tuple[int, int], cat: str, objID: int, numInCat: Optional[int]) -> bool:
        """
        **Description**  
        Check if the target (cat, objID) was in realmIn in a previous frame.

        **Params**  
        - `pt`: The point to check.
        - `cat`: The category name.
        - `objID`: The object ID in that category.
        - `numInCat`: If used to differentiate multiple objects with same cat.

        **Returns**  
        bool, True if found in realmIn before, else False.
        """
        try:
            pastFrame = self.history[-2];
        except IndexError:
            return False;
        labs  = pastFrame.get("labels", []);
        ids   = pastFrame.get("IDs", []);
        mids  = pastFrame.get("midPoints", []);
        if cat not in labs:
            return False;
        for i, lb in enumerate(labs):
            if lb == cat:
                checkID = ids[i] if len(ids) == len(labs) else i;
                if checkID == objID:
                    if ("numProjection" in pastFrame) and (numInCat is not None):
                        arr = [x[1] for x in pastFrame["numProjection"].get(cat, []) if x[0] == objID];
                        if not arr or arr[0] != numInCat:
                            continue;
                    oldPt = mids[i];
                    if self._inRealm(oldPt, self.realmIn):
                        self.direction = 0.5 * (self.direction + np.array([pt[0] - oldPt[0], pt[1] - oldPt[1]], dtype=np.float32));
                        return True;
        return False;

    def _inRealm(self, point: Tuple[int,int], realm: np.ndarray) -> bool:
        """
        **Description**
        Check if a point is inside the 4-point polygon realm.

        **Params**
        - `point`: (x,y);
        - `realm`: shape=(4,2) => corners of realm.

        **Returns**
        bool, True if inside/on boundary, else False.
        """
        px, py = point;
        contour = realm.reshape(-1,1,2);
        inside = cv2.pointPolygonTest(contour, (px, py), False);
        return inside >= 0;
    

if __name__ == "__main__":
    """
    A dynamic demo that repeatedly calls update as the main method, 
    simulating a moving object in multiple frames;
    """
    # Grey background
    H, W = 600, 800;
    bg = np.ones((H, W, 3), dtype=np.uint8) * 200;

    # create a hitBar
    hb = hitBar(
        imgSize=bg.shape,
        startPoint=(200,150),
        endPoint=(600,450),
        width=50.0,
        name="demoBar",
        visualize=True
    );
    hb._monitor(["ball"]);

    # sim => ball motion
    center_x = 100;
    center_y = 300;
    vel_x = 5;
    vel_y = 3;
    radius = 15;

    old_frame = None;
    while True:
        frame = bg.copy();

        # update position
        center_x += vel_x;
        center_y += vel_y;
        if center_x - radius < 0 or center_x + radius >= W:
            vel_x = -vel_x;
        if center_y - radius < 0 or center_y + radius >= H:
            vel_y = -vel_y;

        # build a detection result => "labels","IDs","midPoints" 
        # plus the "img" if we want to visualize 
        detectRes = {
            "img": frame,
            "labels": ["ball"],
            "IDs": [0],
            "midPoints": [(center_x, center_y)],
            "numProjection": {
                "ball": [(0,0)]
            }
        };

        # call update => main method
        imgOut, acc = hb.update(bg, detectRes);

        if imgOut is not None:
            # draw the ball
            cv2.circle(imgOut, (center_x, center_y), radius, (0,255,255), -1);
            cv2.putText(imgOut, "Press `q` to exit", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20,20,20), 2);
            cv2.imshow("HitBar Demo", imgOut);

        key = cv2.waitKey(3);
        if key == ord("q"):
            break;

    cv2.destroyAllWindows();

    def _inRealm(self, point: Tuple[int,int], realm: np.ndarray) -> bool:
        """
        **Description**
        Check if a point is inside the 4-point polygon realm.

        **Params**
        - `point`: (x,y);
        - `realm`: shape=(4,2) => corners of realm.

        **Returns**
        bool, True if inside/on boundary, else False.
        """
        px, py = point;
        contour = realm.reshape(-1,1,2);
        inside = cv2.pointPolygonTest(contour, (px, py), False);
        return inside >= 0;
    

if __name__ == "__main__":
    """
    A dynamic demo that repeatedly calls update as the main method, 
    simulating a moving object in multiple frames;
    """
    # Grey background
    H, W = 600, 800;
    bg = np.ones((H, W, 3), dtype=np.uint8) * 200;

    # create a hitBar
    hb = hitBar(
        imgSize=bg.shape,
        startPoint=(200,150),
        endPoint=(600,450),
        width=50.0,
        name="demoBar",
        visualize=True
    );
    hb._monitor(["ball"]);

    # sim => ball motion
    center_x = 100;
    center_y = 300;
    vel_x = 5;
    vel_y = 3;
    radius = 15;

    old_frame = None;
    while True:
        frame = bg.copy();

        # update position
        center_x += vel_x;
        center_y += vel_y;
        if center_x - radius < 0 or center_x + radius >= W:
            vel_x = -vel_x;
        if center_y - radius < 0 or center_y + radius >= H:
            vel_y = -vel_y;

        # build a detection result => "labels","IDs","midPoints" 
        # plus the "img" if we want to visualize 
        detectRes = {
            "img": frame,
            "labels": ["ball"],
            "IDs": [0],
            "midPoints": [(center_x, center_y)],
            "numProjection": {
                "ball": [(0,0)]
            }
        };

        # call update => main method
        imgOut, acc = hb.update(bg, detectRes);

        if imgOut is not None:
            # draw the ball
            cv2.circle(imgOut, (center_x, center_y), radius, (0,255,255), -1);
            cv2.putText(imgOut, "Press `q` to exit", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20,20,20), 2);
            cv2.imshow("HitBar Demo", imgOut);

        key = cv2.waitKey(3);
        if key == ord("q"):
            break;

    cv2.destroyAllWindows();