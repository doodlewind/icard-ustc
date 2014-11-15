from PIL import Image
from StringIO import StringIO


def parse(captcha):
    im = Image.open(StringIO(captcha))
    pixel_map = im.load()
    feature_pixels = {
        7: [[8, 3]],
        2: [[8, 12]],
        1: [[3, 12], [4, 11]],
        3: [[1, 4], [1, 11]],
        4: [[7, 12], [8, 9]],
        5: [[7, 3], [8, 8]],
        6: [[1, 8], [1, 9], [1, 10]],
        8: [[1, 9], [1, 10], [8, 5]],
        9: [[8, 5], [8, 6], [8, 7]],
        0: [[1, 9], [8, 9], [8, 6]]
    }
    answer = []
    for offset in range(0, 36, 9):
        for i in feature_pixels:
            for x, y in feature_pixels[i]:
                # 2 = white
                if pixel_map[x + offset, y] != 2:
                    break
            else:
                answer.append(i)
                break
    return '%i%i%i%i' % (answer[0], answer[1], answer[2], answer[3])
