import os
import ntpath
import glob
import configparser
import numpy as np
import cv2

from rectpack import newPacker
from utils.folder_file_manager import make_directory_if_not_exists
from settings import PIXEL_TO_MM, PAPER_HEIGHT, PAPER_WIDTH, CONFIG_FILE_PATH, OUTPUT_DIR


class StampAligner:
    def __init__(self):
        params = configparser.ConfigParser()
        params.read(CONFIG_FILE_PATH)
        # self.collection_num = params.get('DEFAULT', 'collection_number')
        self.paper_width = int(PAPER_WIDTH * PIXEL_TO_MM)
        self.paper_height = int(PAPER_HEIGHT * PIXEL_TO_MM)
        self.align_status = "Init"
        self.current_width = 0
        self.current_height = 0
        self.row_height = 0
        self.row_stamps = {"row_stamp": [], "width": 0, "height": 0}
        self.stamp_status = []
        self.rectangles = []
        self.rectangle_sizes = []
        self.previous_rects = []

    def align_stamps(self, stamp_frame):
        height, width = stamp_frame.shape[:2]
        if self.paper_width - self.current_width - width < int(4 * PIXEL_TO_MM):
            self.row_stamps["width"] = self.current_width
            self.row_stamps["height"] = self.row_height
            self.current_height += self.row_height
            self.stamp_status.append(self.row_stamps.copy())
            self.current_width = 0
            self.row_height = 0
            self.row_stamps["row_stamp"] = []
            if self.paper_height - self.current_height - height < int(2 * PIXEL_TO_MM * (len(self.stamp_status) + 1)):
                self.align_status = "Complete"
            else:
                self.row_stamps["row_stamp"].append(stamp_frame)
                self.current_width += width
                self.row_height = max(self.row_height, height)
        else:
            self.row_stamps["row_stamp"].append(stamp_frame)
            self.current_width += width
            self.row_height = max(self.row_height, height)

        if self.align_status == "Complete":
            stamp_paper_image = np.ones([self.paper_height, self.paper_width, 3], dtype=np.uint8) * 255
            height_spacing = int((self.paper_height - self.current_height) / (len(self.stamp_status) + 1))
            height_pos = 0
            for i, r_stamps in enumerate(self.stamp_status):
                width_pos = int((self.paper_width - r_stamps["width"]) / 2)
                height_pos += height_spacing
                for r_stamp in r_stamps["row_stamp"]:
                    r_height, r_width = r_stamp.shape[:2]
                    r_height_spacing = r_stamps["height"] - r_height
                    pos_x = width_pos
                    pos_y = height_pos + r_height_spacing
                    stamp_paper_image[pos_y:pos_y + r_height, pos_x:pos_x + r_width] = r_stamp
                    width_pos += r_width
                height_pos += r_stamps["height"]
            # processed_image = self.image_utils.run(frame=stamp_paper_image)
            processed_image = stamp_paper_image
            output_images = glob.glob(os.path.join(OUTPUT_DIR, "*.jpg"))
            output_indices = []
            for o_image in output_images:
                image_index = int(ntpath.basename(o_image).replace("StampPaper", "").replace(".jpg", ""))
                output_indices.append(image_index)
            if output_indices:
                cnt_index = max(output_indices) + 1
            else:
                cnt_index = 0
            cv2.imwrite(os.path.join(OUTPUT_DIR, f'StampPaper{cnt_index}.jpg'), processed_image)
            print(f"[INFO] Successfully saved the final StampPaper Image into "
                  f"{os.path.join(OUTPUT_DIR, f'StampPaper{cnt_index}.jpg')}")
            self.stamp_status = []
            self.align_status = "Init"
            self.current_height = 0

            return "complete"
        else:
            return "retry"

    def pack_stamps(self, stamp_frame, collection_num, picture_num):
        collection_dir = make_directory_if_not_exists(os.path.join(OUTPUT_DIR, f"collection{collection_num}"))
        align_stamp_path = os.path.join(collection_dir, f'Picture{picture_num}.jpg')
        status = "retry"
        height, width = stamp_frame.shape[:2]
        self.rectangle_sizes.append((width, height))
        self.rectangles.append(stamp_frame)
        bins = [(self.paper_width, self.paper_height)]
        packer = newPacker(rotation=False)
        for r in self.rectangle_sizes:
            packer.add_rect(*r)
        for b in bins:
            packer.add_bin(*b)
        packer.pack()
        all_rects = packer.rect_list()
        stamp_paper_image = np.ones([self.paper_height, self.paper_width, 3], dtype=np.uint8) * 255
        for rect in self.previous_rects:
            _, x, y, w, h, _ = rect
            try:
                frame = self.rectangles[self.rectangle_sizes.index((w, h))]
                stamp_paper_image[self.paper_height - y - h:self.paper_height - y, x:x + w] = frame
            except Exception as e:
                print(e)
        cv2.imwrite(align_stamp_path, stamp_paper_image)
        if len(all_rects) < len(self.rectangles):
            status = "complete"
            self.previous_rects = []
            self.rectangles = []
            self.rectangle_sizes = []
            # cv2.imshow("Packed Frame", cv2.resize(stamp_paper_image, None, fx=0.3, fy=0.3))
            # cv2.waitKey()
        else:
            self.previous_rects = all_rects

        return status, align_stamp_path


if __name__ == '__main__':
    stamp_aligner = StampAligner()
    image_paths = glob.glob(os.path.join("", "*.jpg"))
    for i_path in image_paths:
        res = stamp_aligner.pack_stamps(stamp_frame=cv2.imread(i_path), collection_num=0, picture_num=0)
        print(f"[INFO] Image: {ntpath.basename(i_path)}, Res: {res}")
        if res == "complete":
            break
