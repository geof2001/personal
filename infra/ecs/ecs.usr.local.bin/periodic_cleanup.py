#!/usr/bin/env python
#
# Remove images that are not currently being used

import subprocess
import re


def main():
    running_image_ids = set()
    for line in subprocess.check_output(
            ['docker', 'ps', '-a', '--no-trunc=t']).split('\n'):
        cols = re.split('\s+', line, 2)
        if len(cols) >= 2:
            running_image_ids.add(cols[1])

    image_ids = set()
    for line in subprocess.check_output(['docker', 'images']).split('\n'):
        cols = re.split('\s+', line, 3)
        col0 = cols[0]
        if col0 in ['<none>', 'REPOSITORY', 'repository']:
            continue
        if len(cols) >= 3:
            image_ids.add('%s:%s' % (col0, cols[1]))

    removal_image_ids = image_ids - running_image_ids
    if len(removal_image_ids) > 0:
        subprocess.call("docker rmi %s" % ' '.join(removal_image_ids), shell=True)


main()
