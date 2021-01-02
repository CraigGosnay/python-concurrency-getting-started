# thumbnail_maker.py
from PIL import Image
import PIL
from urllib.request import urlretrieve
from urllib.parse import urlparse
import threading
import os
import time
import logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
THREADLOG = "[%(threadName)s, %(asctime)s, %(levelname)s] %(message)s"
logging.basicConfig(level=logging.DEBUG, format=THREADLOG,
                    handlers=[logging.StreamHandler(),
                              logging.FileHandler("logfile.log")])


class ThumbnailMakerService(object):
    def __init__(self, home_dir='.'):
        self.home_dir = home_dir
        self.input_dir = self.home_dir + os.path.sep + 'incoming'
        self.output_dir = self.home_dir + os.path.sep + 'outgoing'
        self.downloaded_bytes = 0 
        self.download_lock = threading.Lock()
        self.dl_semaphore = threading.Semaphore(5)

    def download_image(self, url):
        self.dl_semaphore.acquire()
        try:
            # download each image and save to the input dir
            logging.info(f"downloading image at {url}")
            img_filename = urlparse(url).path.split('/')[-1]
            urlretrieve(url, self.input_dir + os.path.sep + img_filename)
            img_size = os.path.getsize(self.input_dir + os.path.sep + img_filename)
            with self.download_lock:
                self.downloaded_bytes += img_size # 3 part action, read, sum, write
            logging.info(f"{self.downloaded_bytes}")
            logging.info(f"image saved at {self.input_dir} ... {img_filename}")
        finally:
            self.dl_semaphore.release()
            
    def download_images(self, img_url_list):
        # validate inputs
        if not img_url_list:
            return
        os.makedirs(self.input_dir, exist_ok=True)

        logging.info("beginning image downloads")

        start = time.perf_counter()
        for url in img_url_list:
            self.download_image(url)
        end = time.perf_counter()

        logging.info("downloaded {} images in {} seconds".format(
            len(img_url_list), end - start))

    def download_images_threaded(self, img_url_list):
        if not img_url_list:
            return
        os.makedirs(self.input_dir, exist_ok=True)

        logging.info("beginning image downloads")

        start = time.perf_counter()
        threads = []
        for url in img_url_list:
            t = threading.Thread(target=self.download_image, args=(url,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        end = time.perf_counter()

        logging.info("downloaded {} images in {} seconds".format(
            len(img_url_list), end - start))

    def perform_resizing(self):
        # validate inputs
        if not os.listdir(self.input_dir):
            return
        os.makedirs(self.output_dir, exist_ok=True)

        logging.info("beginning image resizing")
        target_sizes = [32, 64, 200]
        num_images = len(os.listdir(self.input_dir))

        start = time.perf_counter()
        for filename in os.listdir(self.input_dir):
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
                img.save(self.output_dir + os.path.sep + new_filename)

            os.remove(self.input_dir + os.path.sep + filename)
        end = time.perf_counter()

        logging.info("created {} thumbnails in {} seconds".format(
            num_images, end - start))

    def make_thumbnails(self, img_url_list):
        logging.info("START make_thumbnails")
        start = time.perf_counter()

        # i/o bound
        self.download_images_threaded(img_url_list)
        # cpu bound
        self.perform_resizing()

        end = time.perf_counter()
        logging.info("END make_thumbnails in {} seconds".format(end - start))
