# -*- coding: utf-8 -*-
"""
Copyright 2018 Jacob M. Graving <jgraving@gmail.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from tensorflow.python.keras.engine import saving

import h5py
import json
import inspect

from deepposekit.models.layers.util import ImageNormalization, Float
from deepposekit.models.layers.convolutional import (
    UpSampling2D,
    SubPixelDownscaling,
    SubPixelUpscaling,
)
from deepposekit.models.layers.deeplabcut import ResNetPreprocess

from deepposekit.io import TrainingGenerator
from deepposekit.models.LEAP import LEAP
from deepposekit.models.StackedDenseNet import StackedDenseNet
from deepposekit.models.StackedHourglass import StackedHourglass
from deepposekit.models.DeepLabCut import DeepLabCut

MODELS = {
    "LEAP": LEAP,
    "StackedDenseNet": StackedDenseNet,
    "StackedHourglass": StackedHourglass,
    "DeepLabCut": DeepLabCut,
}


CUSTOM_LAYERS = {
    "Float": Float,
    "ImageNormalization": ImageNormalization,
    "UpSampling2D": UpSampling2D,
    "SubPixelDownscaling": SubPixelDownscaling,
    "SubPixelUpscaling": SubPixelUpscaling,
    "ResNetPreprocess": ResNetPreprocess,
}


def load_model(path, generator=None, augmenter=None, custom_objects=None):
    """
    Load the model

    Example
    -------
    model = load_model('model.h5', augmenter)

    """
    if custom_objects:
        if isinstance(custom_objects, dict):
            base_objects = CUSTOM_LAYERS
            custom_objects = dict(
                list(base_objects.items()) + list(custom_objects.items())
            )
    else:
        custom_objects = CUSTOM_LAYERS

    if isinstance(path, str):
        if path.endswith(".h5") or path.endswith(".hdf5"):
            filepath = path
        else:
            raise ValueError("file must be .h5 file")
    else:
        raise TypeError("file must be type `str`")

    train_model = saving.load_model(filepath, custom_objects=custom_objects)

    with h5py.File(filepath, "r") as h5file:
        train_generator_config = h5file.attrs.get("train_generator_config")
        if train_generator_config is None:
            raise ValueError("No data generator found in config file")
        train_generator_config = json.loads(train_generator_config.decode("utf-8"))[
            "config"
        ]

        model_config = h5file.attrs.get("pose_model_config")
        if model_config is None:
            raise ValueError("No pose model found in config file")
        model_name = json.loads(model_config.decode("utf-8"))["class_name"]
        model_config = json.loads(model_config.decode("utf-8"))["config"]

    if generator:
        signature = inspect.signature(TrainingGenerator.__init__)
        keys = [key for key in signature.parameters.keys()]
        keys.remove("self")
        keys.remove("augmenter")
        keys.remove("generator")
        kwargs = {key: train_generator_config[key] for key in keys}
        kwargs["augmenter"] = augmenter
        kwargs["generator"] = generator
        train_generator = TrainingGenerator(**kwargs)
    else:
        train_generator = None

    Model = MODELS[model_name]
    signature = inspect.signature(Model.__init__)
    keys = [key for key in signature.parameters.keys()]
    keys.remove("self")
    keys.remove("train_generator")
    if "kwargs" in keys:
        keys.remove("kwargs")
    kwargs = {key: model_config[key] for key in keys}
    kwargs["train_generator"] = train_generator

    # Pass to skip initialization and manually intialize
    kwargs["skip_init"] = True

    model = Model(**kwargs)
    model.train_model = train_model
    model.__init_train_model__()

    kwargs = {}
    kwargs["output_shape"] = model_config["output_shape"]
    kwargs["keypoints_shape"] = model_config["keypoints_shape"]
    kwargs["downsample_factor"] = model_config["downsample_factor"]
    kwargs["output_sigma"] = model_config["output_sigma"]
    model.__init_predict_model__(**kwargs)

    return model
