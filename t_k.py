import threading
import time
import cv2


class CamThread:
    def __init__(self):
        self.top_frame = None
        self.bottom_frame = None
        self.stamp_detector_frame = None
        self.break_ret = False

    def get_frame(self, num_port, cam_cat):
        cap = cv2.VideoCapture(num_port)
        while True:
            if self.break_ret:
                cap.release()
                break
            _, frame = cap.read()
            if cam_cat == "top":
                self.top_frame = frame
            elif cam_cat == "bottom":
                self.bottom_frame = frame
            elif cam_cat == "stamp":
                self.stamp_detector_frame = frame
            time.sleep(0.02)

        return

    def run(self):
        top_frame_thread = threading.Thread(target=self.get_frame, args=[0, "top"])
        bottom_frame_thread = threading.Thread(target=self.get_frame, args=[1, "bottom"])
        stamp_frame_thread = threading.Thread(target=self.get_frame, args=[2, "stamp"])
        top_frame_thread.start()
        bottom_frame_thread.start()
        stamp_frame_thread.start()
        while self.top_frame is not None and self.bottom_frame is not None and self.stamp_detector_frame is not None:
            cv2.imshow("Top Frame", self.top_frame)
            cv2.imshow("Bottom Frame", self.bottom_frame)
            cv2.imshow("Stamp Detector Frame", self.stamp_detector_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.break_ret = True
                top_frame_thread.join()
                bottom_frame_thread.join()
                stamp_frame_thread.join()
                break
        cv2.destroyAllWindows()

        return


def display_cam_view():
    cap1 = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # cap1.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    # cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    cap2 = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap3 = cv2.VideoCapture(2, cv2.CAP_DSHOW)
    while True:
        frame1_ret, frame1 = cap1.read()
        # print(frame1.shape[:2])
        frame2_ret, frame2 = cap2.read()
        frame3_ret, frame3 = cap3.read()
        # print(frame3.shape[:2])
        if frame1_ret:
            cv2.imshow("Frame1", frame1)
        if frame2_ret:
            cv2.imshow("Frame2", frame2)
        if frame3_ret:
            cv2.imshow("Frame3", frame3)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap1.release()
    cap2.release()
    cap3.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    # CamThread().run()
    display_cam_view()
