import threading
import cv2
import joblib

from src.stamp.detector import StampDetector
from src.arduino.communicator import ArduinoCom
from src.feature.extractor import ImageFeature
from src.stamp.aligner import StampAligner
from src.stamp.rotator import rotate_stamp
from settings import SIDE_MODEL_PATH, TOP_IMAGE_PATH, BOTTOM_IMAGE_PATH


class StampController:
    def __init__(self):
        self.stamp_detector = StampDetector()
        self.ard_com = ArduinoCom()
        self.stamp_aligner = StampAligner()
        self.side_model = joblib.load(SIDE_MODEL_PATH)
        self.image_feature = ImageFeature()
        self.frame = None

    @staticmethod
    def click_event(event, x, y, flags, params):

        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"[INFO] Point X: {int(x * 3264 / 1600)}, Point Y: {int(y * 2448 / 1200)}")

    def get_stamp_side(self, frame_path):
        frame_feature = self.image_feature.get_feature_from_file(img_path=frame_path)
        stamp_side = self.side_model.predict(frame_feature)[0]

        return stamp_side

    def run(self):
        cap = cv2.VideoCapture(0)
        top_cap = cv2.VideoCapture(1)
        bottom_cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3264)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2448)
        stamp_x = 0
        stamp_y = 0
        ard_threading = threading.Thread(target=self.ard_com.receive_command_arduino)
        ard_threading.start()
        while True:
            _, self.frame = cap.read()
            if self.ard_com.ard_res == "detect":
                detected_stamp_rect, detected_stamp_scores = self.stamp_detector.detect_from_images(frame=self.frame)
                detected_stamp = detected_stamp_rect[detected_stamp_scores.index(max(detected_stamp_scores))]
                if detected_stamp:
                    stamp_x = int((detected_stamp[0] + detected_stamp[2]) / 2)
                    stamp_y = int((detected_stamp[1] + detected_stamp[3]) / 2)
                    cv2.circle(self.frame, (stamp_x, stamp_y), 5, (0, 0, 255), 3)
                    print(f"[INFO] Pick Stamp at {stamp_x}, {stamp_y}")
                    self.ard_com.send_command_arduino(command=f"{stamp_x},{stamp_y}")
                    self.ard_com.ard_res = None
            if self.ard_com.ard_res == "moved":
                _, top_frame = top_cap.read()
                _, bottom_frame = bottom_cap.read()
                cv2.imshow("Top Frame", top_frame)
                cv2.imshow("Bottom Frame", bottom_frame)
                cv2.waitKey(1000)
                top_stamps_rect, _ = self.stamp_detector.detect_from_images(frame=top_frame)
                bottom_stamps_rect, _ = self.stamp_detector.detect_from_images(frame=bottom_frame)
                if len(top_stamps_rect) == 1 and len(bottom_stamps_rect) == 1:
                    top_stamp_roi = top_frame[top_stamps_rect[0][1]:
                                              top_stamps_rect[0][3], top_stamps_rect[0][0]:top_stamps_rect[0][2]]
                    cv2.imwrite(TOP_IMAGE_PATH, top_stamp_roi)
                    bottom_stamp_roi = \
                        bottom_frame[bottom_stamps_rect[0][1]:
                                     bottom_stamps_rect[0][3], bottom_stamps_rect[0][0]:bottom_stamps_rect[0][2]]
                    cv2.imwrite(BOTTOM_IMAGE_PATH, bottom_stamp_roi)
                    if self.get_stamp_side(frame_path=TOP_IMAGE_PATH) == "front":
                        front_stamp_image = top_stamp_roi
                    else:
                        if self.get_stamp_side(frame_path=BOTTOM_IMAGE_PATH) == "front":
                            front_stamp_image = bottom_stamp_roi
                        else:
                            self.ard_com.send_command_arduino(command="retry")
                            continue
                    final_stamp_image = rotate_stamp(frame=front_stamp_image)
                    res = self.stamp_aligner.align_stamps(stamp_frame=final_stamp_image)
                    self.ard_com.send_command_arduino(command=res)
                else:
                    self.ard_com.send_command_arduino(command="retry")
                self.ard_com.ard_res = None

            if stamp_x != 0 and stamp_y != 0:
                cv2.circle(self.frame, (stamp_x, stamp_y), 5, (0, 0, 255), 3)
            cv2.imshow("Stamp Detector", cv2.resize(self.frame, (1600, 1200)))
            cv2.setMouseCallback('Stamp Detector', self.click_event)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.ard_com.receive_ret = False
        ard_threading.join()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    StampController().run()