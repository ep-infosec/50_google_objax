#!/usr/bin/env python

# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script to create SSL splits from a dataset.
"""

import json
import os
from collections import defaultdict

import numpy as np
import tensorflow as tf
from absl import app, flags
from tqdm import trange, tqdm

from examples.fixmatch.libml.data import core

flags.DEFINE_integer('seed', 0, 'Random seed to use, 0 for no shuffling.')
flags.DEFINE_integer('size', 0, 'Size of labelled set.')

FLAGS = flags.FLAGS


def get_class(serialized_example):
    return tf.io.parse_single_example(serialized_example,
                                      features={'label': tf.io.FixedLenFeature([], tf.int64)})['label']


def main(argv):
    assert FLAGS.size
    argv.pop(0)
    if any(not tf.io.gfile.exists(f) for f in argv[1:]):
        raise FileNotFoundError(argv[1:])
    target = '%s.%d@%d' % (argv[0], FLAGS.seed, FLAGS.size)
    if tf.io.gfile.exists(target):
        raise FileExistsError('For safety overwriting is not allowed', target)
    input_files = argv[1:]
    count = 0
    id_class = []
    class_id = defaultdict(list)
    print('Computing class distribution')
    dataset = tf.data.TFRecordDataset(input_files).map(get_class, 4).batch(1 << 10)
    for it in dataset:
        with tqdm(leave=False) as t:
            for i in it:
                id_class.append(i.numpy())
                class_id[i.numpy()].append(count)
                count += 1
            t.update(it.shape[0])
    print('%d records found' % count)
    nclass = len(class_id)
    assert min(class_id.keys()) == 0 and max(class_id.keys()) == (nclass - 1)
    train_stats = np.array([len(class_id[i]) for i in range(nclass)], np.float64)
    train_stats /= train_stats.max()
    if 'stl10' in argv[1]:
        # All of the unlabeled data is given label 0, but we know that
        # STL has equally distributed data among the 10 classes.
        train_stats[:] = 1

    print('  Stats', ' '.join(['%.2f' % (100 * x) for x in train_stats]))
    assert min(class_id.keys()) == 0 and max(class_id.keys()) == (nclass - 1)
    class_id = [np.array(class_id[i], dtype=np.int64) for i in range(nclass)]
    if FLAGS.seed:
        np.random.seed(FLAGS.seed)
        for i in range(nclass):
            np.random.shuffle(class_id[i])

    # Distribute labels to match the input distribution.
    npos = np.zeros(nclass, np.int64)
    label = []
    for i in range(FLAGS.size):
        c = np.argmax(train_stats - npos / max(npos.max(), 1))
        label.append(class_id[c][npos[c]])
        npos[c] += 1

    del npos, class_id
    label = frozenset([int(x) for x in label])
    if 'stl10' in argv[1] and FLAGS.size == 1000:
        data = tf.io.gfile.GFile(os.path.join(core.DATA_DIR, 'stl10_fold_indices.txt'), 'r').read()
        label = frozenset(list(map(int, data.split('\n')[FLAGS.seed].split())))

    print('Creating split in %s' % target)
    tf.io.gfile.makedirs(os.path.dirname(target))
    with tf.io.TFRecordWriter(target + '-label.tfrecord') as writer_label:
        pos, loop = 0, trange(count, desc='Writing records')
        for input_file in input_files:
            for record in tf.compat.v1.python_io.tf_record_iterator(input_file):
                if pos in label:
                    writer_label.write(record)
                pos += 1
                loop.update()
        loop.close()
    with tf.io.gfile.GFile(target + '-label.json', 'w') as writer:
        writer.write(json.dumps(dict(distribution=train_stats.tolist(), label=sorted(label)), indent=2, sort_keys=True))


if __name__ == '__main__':
    app.run(main)
