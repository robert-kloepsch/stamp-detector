import time
import threading
import cv2
import joblib
import configparser

from src.stamp.detector import StampDetector
from src.arduino.communicator import ArduinoCom
from src.feature.extractor import ImageFeature
from src.stamp.aligner import StampAligner
from src.stamp.orientator import StampOrientation
from src.stamp.rotator import rotate_stamp
from settings import SIDE_MODEL_PATH, TOP_IMAGE_PATH, BOTTOM_IMAGE_PATH, CONFIG_FILE_PATH


class StampController:
    def __init__(self):
        params = configparser.ConfigParser()
        params.read(CONFIG_FILE_PATH)
        self.top_cam_num = int(params.get('DEFAULT', 'top_cam'))
        self.bottom_cam = int(params.get('DEFAULT', 'bottom_cam'))
        self.stamp_detector_cam_num = int(params.get('DEFAULT', 'stamp_detector_cam'))
        self.stamp_detector = StampDetector()
        self.ard_com = ArduinoCom()
        self.stamp_aligner = StampAligner()
        self.stamp_orientation = StampOrientation()
        self.side_model = joblib.load(SIDE_MODEL_PATH)
        self.image_feature = ImageFeature()

    @staticmethod
    def click_event(event, x, y, flags, params):

        if event == cv2.EVENT_LBUTTONDOWN:
            print(f"[INFO] Point X: {int(x * 3264 / 1600)}, Point Y: {int(y * 2448 / 1200)}")

    def get_stamp_side(self, frame_path):
        frame_feature = self.image_feature.get_feature_from_file(img_path=frame_path)
        stamp_side = self.side_model.predict([frame_feature])[0]

        return stamp_side

    def run(self):
        cap = cv2.VideoCapture(self.stamp_detector_cam_num)
        top_cap = cv2.VideoCapture(self.top_cam_num)
        bottom_cap = cv2.VideoCapture(self.bottom_cam)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        top_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
        top_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        bottom_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
        bottom_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
        while True:
            cap_ret, _ = cap.read()
            top_ret, _ = top_cap.read()
            bottom_ret, _ = bottom_cap.read()
            if cap_ret and top_ret and bottom_ret:
                break
            time.sleep(0.1)
        stamp_x = 0
        stamp_y = 0
        ard_threading = threading.Thread(target=self.ard_com.receive_command_arduino)
        ard_threading.start()
        while True:
            _, frame = cap.read()
            _, top_frame = top_cap.read()
            _, bottom_frame = bottom_cap.read()
            if self.ard_com.ard_res == "detect":
                detected_stamp_rect, detected_stamp_scores = self.stamp_detector.detect_from_images(frame=frame)
                if detected_stamp_scores:
                    detected_stamp = detected_stamp_rect[detected_stamp_scores.index(max(detected_stamp_scores))]
                    stamp_x = int((detected_stamp[0] + detected_stamp[2]) / 2)
                    stamp_y = int((detected_stamp[1] + detected_stamp[3]) / 2)
                    cv2.circle(frame, (stamp_x, stamp_y), 5, (0, 0, 255), 3)
                    print(f"[INFO] Pick Stamp at {stamp_x}, {stamp_y}")
                    self.ard_com.send_command_arduino(command=f"{stamp_x},{stamp_y}")
                    self.ard_com.ard_res = None
            if self.ard_com.ard_res == "moved":
                top_stamps_rect, _ = self.stamp_detector.detect_from_images(frame=top_frame)
                bottom_stamps_rect, _ = self.stamp_detector.detect_from_images(frame=bottom_frame)
                if len(top_stamps_rect) == 1 and len(bottom_stamps_rect) == 1:
                    print("[INFO] Single Detected!")
                    self.ard_com.send_command_arduino(command="single")
                    top_stamp_roi = top_frame[top_stamps_rect[0][1] - 20:top_stamps_rect[0][3] + 20,
                                              top_stamps_rect[0][0] - 20:top_stamps_rect[0][2] + 20]
                    cv2.imwrite(TOP_IMAGE_PATH, top_stamp_roi)
                    bottom_stamp_roi = \
                        bottom_frame[bottom_stamps_rect[0][1] - 20:bottom_stamps_rect[0][3] + 20,
                                     bottom_stamps_rect[0][0] - 20:bottom_stamps_rect[0][2] + 20]
                    cv2.imwrite(BOTTOM_IMAGE_PATH, bottom_stamp_roi)
                    if self.get_stamp_side(frame_path=TOP_IMAGE_PATH) == "front":
                        front_stamp_image = top_stamp_roi
                    else:
                        if self.get_stamp_side(frame_path=BOTTOM_IMAGE_PATH) == "front":
                            front_stamp_image = bottom_stamp_roi
                        else:
                            self.ard_com.send_command_arduino(command="retry")
                            self.ard_com.ard_res = None
                            continue
                    rotated_img_path, rotated_image = rotate_stamp(frame=front_stamp_image)
                    orientation = self.stamp_orientation.estimate_rotate_angle(frame_path=rotated_img_path)
                    if orientation == "normal":
                        final_stamp_image = rotated_image
                    elif orientation == "clock":
                        final_stamp_image = cv2.rotate(rotated_image, cv2.ROTATE_90_CLOCKWISE)
                    elif orientation == "counter_clock":
                        final_stamp_image = cv2.rotate(rotated_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    else:
                        final_stamp_image = cv2.rotate(rotated_image, cv2.ROTATE_180)
                    res = self.stamp_aligner.align_stamps(stamp_frame=final_stamp_image)
                    self.ard_com.send_command_arduino(command=res)
                else:
                    print("[INFO] Multi or None Detected")
                    self.ard_com.send_command_arduino(command="none")
                self.ard_com.ard_res = None

            if stamp_x != 0 and stamp_y != 0:
                cv2.circle(frame, (stamp_x, stamp_y), 5, (0, 0, 255), 3)
            cv2.imshow("Stamp Detector", frame)
            cv2.imshow("Top Frame", top_frame, )
            cv2.imshow("Bottom Frame", bottom_frame)
            cv2.setMouseCallback('Stamp Detector', self.click_event)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        self.ard_com.receive_ret = False
        ard_threading.join()
        cap.release()
        bottom_cap.release()
        top_cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    StampController().get_stamp_side(frame_path="")
