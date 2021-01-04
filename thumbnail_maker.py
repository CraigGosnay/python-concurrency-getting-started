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
import asyncio
import aiofiles
import aiohttp

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
    async def download_image_async(self, session, url):

        logging.info(f"attempting download {url}")

         # download each image and save to the input dir
        img_filename = urlparse(url).path.split('/')[-1]
        img_filepath = self.input_dir + os.path.sep + img_filename

        async with session.get(url) as response:
            async with aiofiles.open(img_filepath, 'wb') as f:
                content = await response.content.read()
                await f.write(content)

        self.dl_size += os.path.getsize(img_filepath)
        self.img_queue.put(img_filename)

    async def download_images_mgr_async(self, img_url_list):
        async with aiohttp.ClientSession() as session:
            for url in img_url_list:
                await self.download_image_async(session, url)

    def download_images(self, img_url_list):
        if not img_url_list:
            return
        
        os.makedirs(self.input_dir, exist_ok=True)
        asyncio.run(self.download_images_mgr_async(img_url_list))

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

        # cpu bound via multiprocessing
        n_processes = multiprocessing.cpu_count()
        for _ in range(n_processes):
            p = multiprocessing.Process(target=self.perform_resizing)
            p.start()

        # io bound via asyncio
        self.download_images(img_url_list)
        
        # poison pill to terminate
        for _ in range(n_processes):
            self.img_queue.put(None)  

        end = time.perf_counter()
        logging.info(f"END make_thumbnails in {end - start} seconds")
        logging.info(
            f"initial downloads size is {self.dl_size}, "
            "rescaled size is {self.resized_size.value}, "
            "space saved is {self.dl_size - self.resized_size.value}")
