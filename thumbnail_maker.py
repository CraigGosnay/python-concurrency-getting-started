# thumbnail_maker.py
import time
import os
import logging
from urllib.parse import urlparse
from urllib.request import urlretrieve
from queue import Queue
from threading import Thread, Lock
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
        self.img_queue = multiprocessing.JoinableQueue()
        self.dl_size = 0  # total size of our downloads
        self.resized_size = multiprocessing.Value('i', 0)  # scaled down total

    # io bound
    def download_image(self, dl_queue, dl_size_lock):
        while not dl_queue.empty():
            logging.info("attempting download")
            try:
                url = dl_queue.get(block=False)
                # download each image and save to the input dir
                img_filename = urlparse(url).path.split('/')[-1]
                img_filepath = self.input_dir + os.path.sep + img_filename
                urlretrieve(url, img_filepath)
                with dl_size_lock:
                    self.dl_size += os.path.getsize(img_filepath)
                self.img_queue.put(img_filename)
                dl_queue.task_done()
            except:
                logging.error("empty queue")

    # cpu bound
    def perform_resizing(self):
        # validate inputs
        os.makedirs(self.output_dir, exist_ok=True)

        logging.info("beginning image resizing")
        target_sizes = [32, 64, 200]
        num_images = len(os.listdir(self.input_dir))

        start = time.perf_counter()
        while True:
            filename = self.img_queue.get()
            if not filename:
                self.img_queue.task_done()
                return
            logging.info(f"resizing image {filename}")
            orig_img = Image.open(self.input_dir + os.path.sep + filename)
            for basewidth in target_sizes:
                img = orig_img
                # calculate target height of the resized image to maintain the aspect ratio
                wpercent = (basewidth / float(img.size[0]))
                hsize = int((float(img.size[1]) * float(wpercent)))
                # perform resizing
                img = img.resize((basewidth, hsize), PIL.Image.LANCZOS)

                # save the resized image to the output dir with a modified file name
                new_filename = os.path.splitext(filename)[0] + \
                    '_' + str(basewidth) + os.path.splitext(filename)[1]
                out_filepath = self.output_dir + os.path.sep + new_filename
                img.save(out_filepath)
                # this provides a multiPROCESS lock (not thread)
                with self.resized_size.get_lock():
                    self.resized_size.value += os.path.getsize(out_filepath)

            os.remove(self.input_dir + os.path.sep + filename)
            logging.info(f"completed resizing image {filename}")
            self.img_queue.task_done()

        end = time.perf_counter()

        logging.info("created {} thumbnails in {} seconds".format(
            num_images, end - start))

    def make_thumbnails(self, img_url_list):
        logging.info("START make_thumbnails")
        start = time.perf_counter()

        dl_queue = Queue()  # must be local as must be picklable for mprocessing
        dl_size_lock = Lock()

        for img in img_url_list:
            dl_queue.put(img)

        # io bound via multithreading
        for _ in range(4):
            t = Thread(target=self.download_image,
                       args=(dl_queue, dl_size_lock))
            t.start()

        # cpu bound via multiprocessing
        n_processes = multiprocessing.cpu_count()
        for _ in range(n_processes):
            p = multiprocessing.Process(target=self.perform_resizing)
            p.start()

        dl_queue.join()
        for _ in range(n_processes):
            self.img_queue.put(None)  # poison pill

        end = time.perf_counter()
        logging.info(f"END make_thumbnails in {end - start} seconds")
        logging.info(
            f"initial downloads size is {self.dl_size}, " \
                 "rescaled size is {self.resized_size.value}, " \
                     "space saved is {self.dl_size - self.resized_size.value}")
