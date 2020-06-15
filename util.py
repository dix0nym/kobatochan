import json
import math
import os
import re
import subprocess
from datetime import datetime
import zlib
from base64 import b64decode, b64encode
from PIL import Image


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):  # pylint: disable=E0202
        if isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def waifu_resize(img, path):
    if img.format == "GIF":
        img = gif_to_jpg(img)
    size = img.size
    scale_ratio = max(
        math.floor((800 / size[0])) + 1,
        math.floor(1220 / size[1]) + 1)
    if img.mode != "RGB":
        img = img.convert("RGB")
    tmp_path = os.path.join(path, "tmp.jpg")
    cover_path = os.path.join(path, "cover.jpg")
    if scale_ratio < 2:
        img.save(cover_path)
        return True, None
    img.save(tmp_path)
    r = waifu2x(tmp_path, cover_path, 2, scale_ratio)
    img = Image.open(cover_path)
    img = img.resize((800, 1220), Image.ANTIALIAS)
    img.save(cover_path)
    os.remove(tmp_path) if r[0] else os.rename(tmp_path, cover_path)
    return r


def gif_to_jpg(img):
    i = img.convert("RGBA")
    bg = Image.new("RGBA", i.size)
    return Image.composite(i, bg, i)


def waifu2x(input_path, output_path, noise, scale):
    p = "waifu2x-converter.exe" if os.name == 'nt' else "waifu2x-converter-cpp"
    if os.name == 'nt':
        args = [
            p, "-i", input_path, "-o", output_path,
            "--noise_level",
            str(noise), "--scale_ratio",
            str(scale)
        ]
    else:
        args = [
            p, "-i", input_path, "-o", output_path,
            "--noise-level",
            str(noise), "--scale-ratio",
            str(scale)
        ]
    process = subprocess.Popen(args, stdout=subprocess.PIPE)
    output, err = process.communicate()
    line = output.splitlines()[-1].decode('utf-8')
    if os.name == 'nt':
        if line == "process successfully done!":
            return True, None
        else:
            return False, err
    else:
        p = r'.+\s(\d+) \[files processed\], (\d+) \[files errored\].+$'
        # print(line)
        matches = re.match(p, line)
        if matches and len(matches.groups()) == 2:
            if matches.group(1) == '1' and matches.group(2) == '0':
                return True, None
        return False, err


def compress(s):
    return b64encode(zlib.compress(s.encode('utf-8'))).decode('ascii')


def decompress(compressed_data):
    return zlib.decompress(b64decode(compressed_data)).decode('utf-8')


def get_valid_fs_name(ipath):
    ILLEGAL_CHARS = r'[^A-z0-9-]'
    c = re.sub(ILLEGAL_CHARS, "-", ipath)
    # remove multiple -
    c = "-".join([k for k in c.split("-") if k and len(k) > 0])
    # check if starts/ends with -
    if c.startswith("-"):
        c = c[1:]
    if c.endswith("-"):
        c = c[:-1]
    return c


def isbase64(sinput):
    pattern = r'^([A-Za-z0-9+\/]{4})*([A-Za-z0-9+\/]{3}=|[A-Za-z0-9+\/]{2}==)?$'
    return re.match(pattern, sinput)
