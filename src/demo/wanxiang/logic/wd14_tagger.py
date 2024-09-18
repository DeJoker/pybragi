# このスクリプトのライセンスは、Apache License 2.0とします
# (c) 2022 Kohya S. @kohya_ss

from base import log
import argparse
import csv
import glob
import os
import logging

from PIL import Image
import cv2
from tqdm import tqdm
import numpy as np
import torch
from tensorflow.keras.models import load_model
import tensorflow as tf
from huggingface_hub import hf_hub_download


# from wd14 tagger
gpus = tf.config.experimental.list_physical_devices('GPU')
print(gpus)
tf.config.experimental.set_virtual_device_configuration(gpus[0], [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=1024)])
IMAGE_SIZE = 448

CSV_FILE = "selected_tags.csv"


class WD14Tagger():
    def __init__(self):
        self.model_dir = os.path.join("/aigc-nas01/cyj/stick_model/", "wd14_tagger_model")
        self.model = load_model(self.model_dir)
        self.tags = self.tag_init()
        self.thresh = 0.5
        self.warm_up()

    def warm_up(self):
        img_path = "/aigc-nas01/cyj/sd_stick_figure/cyl_nresize-bk-INTER_AREA.png"
        image = Image.open(img_path)
        image = image.resize((512, 512), Image.ANTIALIAS)
        result = self.tag_single(image)
        logging.info(result)

    def tag_init(self):
        with open(os.path.join(self.model_dir, CSV_FILE), "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            l = [row for row in reader]
            header = l[0]  # tag_id,name,category,count
            rows = l[1:]
        assert header[0] == 'tag_id' and header[1] == 'name' and header[
            2] == 'category', "unexpected csv format: {}".format(header)

        tags = [row[1] for row in rows[1:] if row[2] == '0']  # categoryが0、つまり通常のタグのみ
        return tags

    def tag_single(self, pil_img, word_limit=77):# cv2は日本語ファイル名で死ぬのとモード変換したいのでpillowで開く
        st = cv2.getTickCount()
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert("RGB")
        img = np.array(pil_img)
        img = img[:, :, ::-1]  # RGB->BGR

        # pad to square
        size = max(img.shape[0:2])
        pad_x = size - img.shape[1]
        pad_y = size - img.shape[0]
        pad_l = pad_x // 2
        pad_t = pad_y // 2
        img = np.pad(img, ((pad_t, pad_y - pad_t), (pad_l, pad_x - pad_l), (0, 0)), mode='constant',
                     constant_values=255)

        interp = cv2.INTER_AREA if size > IMAGE_SIZE else cv2.INTER_LANCZOS4
        img = cv2.resize(img, (IMAGE_SIZE, IMAGE_SIZE), interpolation=interp)

        img = img.astype(np.float32)
        img = np.expand_dims(img, 0)

        probs = self.model(img) #, training=False)
        t = cv2.getTickCount() - st
        # logging.info("wd14 forward time: %.2fms" % (t*1000./cv2.getTickFrequency()))
        prob = probs[0][4:]
        prob = prob.numpy().flatten()

        index = np.where(prob >= self.thresh)[0]
        tags = np.array(self.tags)[index].tolist()

        # filter tags
        negs = {"monochrome", "greyscale", "white background", "no humans", "simple background", "comic", "solo", "border", "watermark"}
        # limit tag string length, otherwise will be parsed as two chunks
        tag_str = ''
        word_len = 0
        N = len(tags)
        for i, tag in enumerate(tags):
            tag = tag.replace('_', ' ')
            if(tag in negs):
                continue
            word_len += len(tag.split(' ')) + 1
            if(word_len >= word_limit+1):
                break 
            tag_str += ', ' + tag
        tag_str = tag_str[2:]

        #t = cv2.getTickCount() - st
        #print("WD14 all time: %.2fms" % (t*1000./cv2.getTickFrequency()))
        return tag_str

if __name__ == '__main__':
    wd14 = WD14Tagger()
    img_path = "/aigc-nas01/cyj/draw_guess/lu.jpg"
    image = Image.open(img_path)
    image = image.resize((512, 512), Image.ANTIALIAS)

    result = wd14.tag_single(image)
    logging.info(result)
    result = wd14.tag_single(image)
    logging.info(result)
