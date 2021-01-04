# thumbnail_maker.py
import time
import os
import logging
from urllib.parse import urlparse
from urllib.request import urlretrieve
from queue import Queue
from threading import Thread
import PIL
from PIL import Image
import multiprocessing

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
THREADLOG = "[%(threadName)s, %(asctime)s, %(levelname)s] %(message)s"
logging.basicConfig(level=logging.DEBUG, format=THREADLOG,
                    handlers=[logging.FileHandler("logfile.log")])


class ThumbnailMakerService(object):
    def __init__(self, home_dir='.'):
        self.home_dir = home_dir
        self.input_dir = self.home_dir + os.path.sep + 'incoming'
        self.output_dir = self.home_dir + os.path.sep + 'outgoing'
        self.img_list = []

    def download_image(self, dl_queue):
        logging.info("attempting download")
        while not dl_queue.empty():
            try:
                url = dl_queue.get(block=False)
                # download each image and save to the input dir
                img_filename = urlparse(url).path.split('/')[-1]
                urlretrieve(url, self.input_dir + os.path.sep + img_filename)
                self.img_list.append(img_filename)
                dl_queue.task_done()
            except:
                logging.error("empty queue")

    def resize_img(self, filename):
        target_sizes = [32, 64, 200]
        logging.info(f"resizing image multiprocessed {filename}")
        orig_img = Image.open(self.input_dir + os.path.sep + filename)
        for basewidth in target_sizes:
            img = orig_img
            wpercent = (basewidth / float(img.size[0]))
            hsize = int((float(img.size[1])*float(wpercent)))
            img = img.resize((basewidth, hsize), PIL.Image.LANCZOS)
            new_filename = os.path.splitext(
                filename)[0] + '_' + str(basewidth) + os.path.splitext(filename)[1]
            img.save(self.output_dir + os.path.sep + new_filename)

        os.remove(self.input_dir + os.path.sep + filename)
        logging.info(f"completed resizing image {filename}")

    def make_thumbnails(self, img_url_list):
        logging.info("START make_thumbnails")
        pool = multiprocessing.Pool()

        start = time.perf_counter()

        dl_queue = Queue()

        for img in img_url_list:
            dl_queue.put(img)
        logging.info("created queue")
        for _ in range(4):
            t = Thread(target=self.download_image, args=(
                dl_queue,))  # comma creates tuple
            t.start()

        dl_queue.join()
        pool.map(self.resize_img, self.img_list)
        end = time.perf_counter()
        pool.close()
        pool.join()

        logging.info("END make_thumbnails in {} seconds".format(end - start))
