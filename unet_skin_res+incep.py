# -*- coding: utf-8 -*-
"""Unet_skin_res+incep.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MGI-GOiOLL7jbb_9Pe6fZf-m6bkIPIVW
"""

pip install -U segmentation-models==0.2.1

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import numpy as np
import cv2
from glob import glob
from sklearn.utils import shuffle
from sklearn.model_selection import train_test_split
import tensorflow as tf

import matplotlib.pyplot as plt
from tensorflow.keras.callbacks import ModelCheckpoint, CSVLogger, ReduceLROnPlateau, EarlyStopping, TensorBoard
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.metrics import Recall, Precision

from google.colab import drive
drive.mount('/content/drive')

H=256
W=192

from PIL import Image

dpath="/content/drive/MyDrive/dataset"
train_img=sorted(glob(os.path.join(dpath,"train","*.bmp")))
masks_img=sorted(glob(os.path.join(dpath,"masks","*.bmp")))
X_train = np.array([np.array(Image.open(fname)) for fname in train_img])/255
Y_train=  np.array([np.array(Image.open(fname))for fname in masks_img])/255

x_train, x_test, y_train, y_test = train_test_split(X_train, Y_train, test_size = 0.20)

len(x_train)

import matplotlib.pyplot as plt
plt.figure(figsize=(20,9))
plt.subplot(2,4,1)
plt.imshow(X_train[0])
plt.subplot(2,4,2)
plt.imshow(X_train[3])
plt.subplot(2,4,3)

'''
plt.imshow(X_train[54])
plt.subplot(2,4,4)
plt.imshow(X_train[77])
plt.subplot(2,4,5)
plt.imshow(X_train[100])
plt.subplot(2,4,6)
plt.imshow(X_train[125])
plt.subplot(2,4,7)
plt.imshow(X_train[130])
plt.subplot(2,4,8)
plt.imshow(X_train[149])
'''
plt.show()

img_rows, img_cols = x_train[0].shape[0], x_train[0].shape[1]
print(img_rows)
print(img_cols)

from keras.preprocessing.image import ImageDataGenerator
datagen = ImageDataGenerator(
        featurewise_center=False,
        samplewise_center=False,
        featurewise_std_normalization=False,
        samplewise_std_normalization=False,
        zca_whitening=False,
        rotation_range=90,
        zoom_range = 0.1,
        width_shift_range=0.1,
        height_shift_range=0.1,
        horizontal_flip=True,
        vertical_flip=True)

datagen.fit(x_train)

train_datagen = ImageDataGenerator(preprocessing_function=keras.applications.resnet50.preprocess_input)

x_train, x_val, y_train, y_val = train_test_split(X_train, Y_train, test_size = 0.20, random_state = 101)

print("Length of the Training Set   : {}".format(len(x_train)))
print("Length of the Test Set       : {}".format(len(x_test)))
#print("Length of the Validation Set : {}".format(len(x_val)))

import numpy as np
import tensorflow as tf
from tensorflow.keras import backend as K

def iou_score(y_true, y_pred):
    def f(y_true, y_pred):
        y_true = tf.cast(y_true, dtype=tf.float32)
        y_pred = tf.cast(y_pred, dtype=tf.float32)
        intersection = (y_true * y_pred).sum()
        union = y_true.sum() + y_pred.sum() - intersection
        x = (intersection + 1e-15) / (union + 1e-15)
        x = x.astype(np.float32)
        return x
    return tf.numpy_function(f, [y_true, y_pred], tf.float32)

smooth = 1e-15
def dice_coef(y_true, y_pred):
    y_true = tf.keras.layers.Flatten()(y_true)
    y_pred = tf.keras.layers.Flatten()(y_pred)
    y_true = tf.cast(y_true, dtype=tf.float32)
    y_pred = tf.cast(y_pred, dtype=tf.float32)
    intersection = tf.reduce_sum(y_true * y_pred)
    return (2. * intersection + smooth) / (tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) + smooth)

def dice_loss(y_true, y_pred):
    y_true = tf.cast(y_true, dtype=tf.float32)
    y_pred = tf.cast(y_pred, dtype=tf.float32)
    return 1.0 - dice_coef(y_true, y_pred)

lr=1e-4

from tensorflow.keras.layers import Conv2D, BatchNormalization, Activation, MaxPool2D, Conv2DTranspose, Concatenate,Input
from tensorflow.keras.models import Model
from tensorflow.keras.applications import ResNet50

def conv_blk(input,num_filters):
    x=Conv2D(num_filters,3,padding="same")(input)
    x=BatchNormalization()(x)
    x=Activation("relu")(x)

    x=Conv2D(num_filters,3,padding="same")(x)
    x=BatchNormalization()(x)
    x=Activation("relu")(x)

    return x


def encode(inputs,num_filters):
    x=conv_blk(inputs, num_filters)
    y=MaxPool2D((2,2))(x)
    return x,y

def decode(inputs,skip_conn,num_filters):
    x=Conv2DTranspose(num_filters,(2,2),strides=2,padding="same")(inputs)
    x=Concatenate()([x,skip_conn])
    x=conv_blk(x, num_filters)
    return x



def unet(io_shape):

    inputs=Input(shape=io_shape)


    s1,p1=encode(inputs, 64)
    s2,p2=encode(p1, 128)
    s3,p3=encode(p2, 256)
    s4,p4=encode(p3, 512)

    bridge=conv_blk(p4, 1024)

    d1=decode(bridge,s4,512)
    d2=decode(d1,s3,256)
    d3=decode(d2,s2,128)
    d4=decode(d3,s1,64)


    output=Conv2D(1,1,padding="same",activation="sigmoid")(d4)
    model=Model(inputs,output)
    metrics = [dice_coef, iou, Recall(), Precision()]
    model.compile(loss="binary_crossentropy", optimizer=Adam(lr), metrics=metrics)




    model.summary()
    model.save('unet_e1.h5')
    return model

unt=unet((W,H,3))

results = unt.fit(x_train, y_train, batch_size=32, epochs=5, validation_data=(x_test, y_test))

from tensorflow.keras.layers import Conv2D, BatchNormalization, Activation, MaxPool2D, UpSampling2D, Concatenate, Input, ZeroPadding2D
from tensorflow.keras.models import Model

def batchnorm_relu(inputs):
    x = BatchNormalization()(inputs)
    x = Activation("relu")(x)
    return x

def residual_block(inputs, num_filters, strides=1):

    x = batchnorm_relu(inputs)
    x = Conv2D(num_filters, 3, padding="same", strides=strides)(x)
    x = batchnorm_relu(x)
    x = Conv2D(num_filters, 3, padding="same", strides=1)(x)


    s = Conv2D(num_filters, 1, padding="same", strides=strides)(inputs)
    x = x + s
    return x

def decoder_block(inputs, skip_features, num_filters):
    x = UpSampling2D((2, 2))(inputs)
    x = Concatenate()([x, skip_features])
    x = residual_block(x, num_filters, strides=1)
    return x

def build_resunet(input_shape):
    inputs = Input(input_shape)

    x = Conv2D(64, 3, padding="same", strides=1)(inputs)
    x = batchnorm_relu(x)
    x = Conv2D(64, 3, padding="same", strides=1)(x)
    s = Conv2D(64, 1, padding="same", strides=1)(inputs)
    s1 = x + s


    s2 = residual_block(s1, 128, strides=2)
    s3 = residual_block(s2, 256, strides=2)

    b = residual_block(s3, 512, strides=2)

    d1 = decoder_block(b, s3, 256)
    d2 = decoder_block(d1, s2, 128)
    d3 = decoder_block(d2, s1, 64)

    outputs = Conv2D(1, 1, padding="same", activation="sigmoid")(d3)


    model = Model(inputs, outputs)
    return model

print("loss",res[0])
print("dice_coef",res[1]*100)
print("iou",res[2]*100)
print("recall",res[3]*100)
print("precison",res[4]*100)

model, hist = unet((W,H,3),1)

import matplotlib.pyplot as plt

img_num = 49
img_pred = unt.predict(x_test[img_num].reshape(1,192,256,3))
plt.figure(figsize=(16,16))
plt.subplot(1,3,1)
plt.imshow(x_test[img_num])
plt.title('Original Image')
plt.subplot(1,3,2)
plt.imshow(y_test[img_num], plt.cm.binary_r)
plt.title('Ground Truth')
plt.subplot(1,3,3)
plt.imshow(img_pred.reshape(192, 256), plt.cm.binary_r)
plt.title('Predicted Output')
plt.show()

!pip install -U --pre segmentation-models

import albumentations as A

print(x_train.shape,y_train.shape)

def random_rotation(x_image, y_image):
    rows_x,cols_x, chl_x = x_image.shape
    rows_y,cols_y = y_image.shape
    rand_num = np.random.randint(-40,40)
    M1 = cv2.getRotationMatrix2D((cols_x/2,rows_x/2),rand_num,1)
    M2 = cv2.getRotationMatrix2D((cols_y/2,rows_y/2),rand_num,1)
    x_image = cv2.warpAffine(x_image,M1,(cols_x,rows_x))
    y_image = cv2.warpAffine(y_image.astype('float32'),M2,(cols_y,rows_y))
    return x_image, y_image.astype('int')

def horizontal_flip(x_image, y_image):
    x_image = cv2.flip(x_image, 1)
    y_image = cv2.flip(y_image.astype('float32'), 1)
    return x_image, y_image.astype('int')

def img_augmentation(x_train, y_train):
    x_rotat = []
    y_rotat = []
    x_flip = []
    y_flip = []
    x_nois = []
    for idx in range(len(x_train)):
        x,y = random_rotation(x_train[idx], y_train[idx])
        x_rotat.append(x)
        y_rotat.append(y)

        x,y = horizontal_flip(x_train[idx], y_train[idx])
        x_flip.append(x)
        y_flip.append(y)
        return np.array(x_rotat), np.array(y_rotat), np.array(x_flip), np.array(y_flip)

def img_augmentation(x_test, y_test):
    x_rotat = []
    y_rotat = []
    x_flip = []
    y_flip = []
    x_nois = []
    for idx in range(len(x_test)):
        x,y = random_rotation(x_test[idx], y_test[idx])
        x_rotat.append(x)
        y_rotat.append(y)

        x,y = horizontal_flip(x_test[idx], y_test[idx])
        x_flip.append(x)
        y_flip.append(y)

    return np.array(x_rotat), np.array(y_rotat), np.array(x_flip), np.array(y_flip)

x_rotated, y_rotated, x_flipped, y_flipped = img_augmentation(x_train, y_train)
x_rotated_t, y_rotated_t, x_flipped_t, y_flipped_t = img_augmentation(x_test, y_test)

x_train_full = np.concatenate([x_train, x_rotated, x_flipped])
y_train_full = np.concatenate([y_train, y_rotated, y_flipped])

img_num = 114
plt.figure(figsize=(12,12))
plt.subplot(3,2,1)
plt.imshow(x_train[img_num])
plt.title('Original Image')
plt.subplot(3,2,2)
plt.imshow(y_train[img_num], plt.cm.binary_r)
plt.title('Original Mask')
plt.subplot(3,2,3)
plt.imshow(x_rotated[img_num])
plt.title('Rotated Image')
plt.subplot(3,2,4)
plt.imshow(y_rotated[img_num], plt.cm.binary_r)
plt.title('Rotated Mask')
plt.subplot(3,2,5)
plt.imshow(x_flipped[img_num])
plt.title('Flipped Image')
plt.subplot(3,2,6)
plt.imshow(y_flipped[img_num], plt.cm.binary_r)
plt.title('Flipped Mask')
plt.show()

aug = A.Compose([
    A.OneOf([
        A.RandomSizedCrop(min_max_height=(50, 101), height=original_height, width=original_width, p=0.5),
        A.PadIfNeeded(min_height=original_height, min_width=original_width, p=0.5)
    ], p=1),
    A.VerticalFlip(p=0.5),
    A.RandomRotate90(p=0.5),
    A.OneOf([
        A.ElasticTransform(alpha=120, sigma=120 * 0.05, alpha_affine=120 * 0.03, p=0.5),
        A.GridDistortion(p=0.5),
        A.OpticalDistortion(distort_limit=2, shift_limit=0.5, p=1)
        ], p=0.8),
    A.CLAHE(p=0.8),
    A.RandomBrightnessContrast(p=0.8),
    A.RandomGamma(p=0.8)])

random.seed(11)

def visualize(image, mask, original_image=None, original_mask=None):
    fontsize = 18

    if original_image is None and original_mask is None:
        f, ax = plt.subplots(2, 1, figsize=(8, 8))

        ax[0].imshow(image)
        ax[1].imshow(mask)
    else:
        f, ax = plt.subplots(2, 2, figsize=(8, 8))

        ax[0, 0].imshow(original_image)
        ax[0, 0].set_title('Original image', fontsize=fontsize)

        ax[1, 0].imshow(original_mask)
        ax[1, 0].set_title('Original mask', fontsize=fontsize)

        ax[0, 1].imshow(image)
        ax[0, 1].set_title('Transformed image', fontsize=fontsize)

        ax[1, 1].imshow(mask)
        ax[1, 1].set_title('Transformed mask', fontsize=fontsize)

augmented = aug(image=image, mask=mask)

image_heavy = augmented['image']
mask_heavy = augmented['mask']

visualize(image_heavy, mask_heavy, original_image=image, original_mask=mask)

transformed_image = transformed['image']
transformed_mask = transformed['mask']

tf.config.run_functions_eagerly(True)

os.environ["SM_FRAMEWORK"] = "tf.keras"
import segmentation_models as sm
tf.config.run_functions_eagerly(True)

model = sm.Unet()

model = sm.Unet('resnet34', encoder_weights='imagenet')

model = sm.Unet('resnet34', classes=1, activation='sigmoid')

backbone="resnet34"
pre_pros=sm.get_preprocessing(backbone)


x_train1=pre_pros(x_train)
x_test2=pre_pros(x_test)

model = sm.Unet(backbone, encoder_weights='imagenet')
model.compile(
    'Adam',
    loss=sm.losses.bce_jaccard_loss,
    metrics=[sm.metrics.iou_score],
)

x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
y_train=y_train.astype('float32')
y_test=y_test.astype('float32')

y_train = np.reshape(y_train, (*y_train.shape, 1))

y_train = y_train.astype('float32')

hist=model.fit(
   x=x_train,
   y=y_train,
   batch_size=16,
   epochs=100,
   validation_data=(x_test, y_test),
)

import matplotlib.pyplot as plt
loss,iou_score=model.evaluate(x_test,y_test)

plt.figure(figsize=(30, 5))
plt.subplot(121)
plt.plot(hist.history['iou_score'])
plt.plot(hist.history['val_iou_score'])
plt.title('Model iou_score')
plt.ylabel('iou_score')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')

# Plot training & validation loss values
plt.subplot(122)
plt.plot(hist.history['loss'])
plt.plot(hist.history['val_loss'])
plt.title('Model loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')
plt.show()

img_num = 34
img_pred = model.predict(x_test[img_num].reshape(1,192,256,3))
plt.figure(figsize=(16,16))
plt.subplot(1,3,1)
plt.imshow(x_test[img_num])
plt.title('Original Image')
plt.subplot(1,3,2)
plt.imshow(y_test[img_num], plt.cm.binary_r)
plt.title('Ground Truth')
plt.subplot(1,3,3)
plt.imshow(img_pred.reshape(192, 256), plt.cm.binary_r)
plt.title('Predicted Output')
plt.show()

backbone="resnext50"
pre_pros=sm.get_preprocessing(backbone)


x_train1=pre_pros(x_train)
x_test2=pre_pros(x_test)

model=sm.Unet(backbone,encoder_weights="imagenet")
model.compile(
    'Adam',
    loss=sm.losses.bce_jaccard_loss,
    metrics=[sm.metrics.iou_score],
)

x_train = x_train.astype('float32')
x_test = x_test.astype('float32')
y_train=y_train.astype('float32')
y_test=y_test.astype('float32')

hist=model.fit(
   x=x_train,
   y=y_train,
   batch_size=16,
   epochs=150,
   validation_data=(x_test, y_test),
)

print("IOU_SCORE",hist.history['iou_score'][-1]*100)
print("LOSS",hist.history['loss'][-1]*100)
print("VAL_IOU_SCORE",hist.history['val_iou_score'][-1]*100)
print("VAL_LOSS",hist.history['val_loss'][-1]*100)

plt.figure(figsize=(30, 5))
plt.subplot(121)
plt.plot(hist.history['iou_score'])
plt.plot(hist.history['val_iou_score'])
plt.title('Model iou_score')
plt.ylabel('iou_score')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')

# Plot training & validation loss values
plt.subplot(122)
plt.plot(hist.history['loss'])
plt.plot(hist.history['val_loss'])
plt.title('Model loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')
plt.show()

img_num = 42
img_pred = model.predict(x_test[img_num].reshape(1,192,256,3))
plt.figure(figsize=(16,16))
plt.subplot(1,3,1)
plt.imshow(x_test[img_num])
plt.title('Original Image')
plt.subplot(1,3,2)
plt.imshow(y_test[img_num], plt.cm.binary_r)
plt.title('Ground Truth')
plt.subplot(1,3,3)
plt.imshow(img_pred.reshape(192, 256), plt.cm.binary_r)
plt.title('Predicted Output')
plt.show()

backbone="inceptionv3"
pre_pros=sm.get_preprocessing(backbone)


x_train1=pre_pros(x_train)
x_test2=pre_pros(x_test)

model=sm.Unet(backbone,encoder_weights="imagenet")
model.compile(
    'Adam',
    loss=sm.losses.bce_jaccard_loss,
    metrics=[sm.metrics.iou_score],
)

hist=model.fit(
   x=x_train,
   y=y_train,
   batch_size=16,
   epochs=100,
   validation_data=(x_test, y_test),
)

loss,iou_score=model.evaluate(x_test2,y_test)

plt.figure(figsize=(30, 5))
plt.subplot(121)
plt.plot(hist.history['iou_score'])
plt.plot(hist.history['val_iou_score'])
plt.title('Model iou_score')
plt.ylabel('iou_score')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')

# Plot training & validation loss values
plt.subplot(122)
plt.plot(hist.history['loss'])
plt.plot(hist.history['val_loss'])
plt.title('Model loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')
plt.show()

img_num = 34
img_pred = model.predict(x_test[img_num].reshape(1,192,256,3))
plt.figure(figsize=(16,16))
plt.subplot(1,3,1)
plt.imshow(x_test[img_num])
plt.title('Original Image')
plt.subplot(1,3,2)
plt.imshow(y_test[img_num], plt.cm.binary_r)
plt.title('Ground Truth')
plt.subplot(1,3,3)
plt.imshow(img_pred.reshape(192, 256), plt.cm.binary_r)
plt.title('Predicted Output')
plt.show()

!pip install keras-unet-collection
from keras_unet_collection import models
from tensorflow  import keras

model = models.att_unet_2d((192, 256, 3), filter_num=[64, 128, 256, 512, 1024],n_labels=1,
                           stack_num_down=2, stack_num_up=2, activation='ReLU',
                           atten_activation='ReLU', attention='add', output_activation='Sigmoid',
                           batch_norm=True, pool=False, unpool=False,
                           backbone='VGG16', weights='imagenet',
                           freeze_backbone=True, freeze_batch_norm=True,
                           name='attunet')

from keras import backend as K
def iou(y_true, y_pred, smooth = 100):
    intersection = K.sum(K.abs(y_true * y_pred), axis=-1)
    sum_ = K.sum(K.square(y_true), axis = -1) + K.sum(K.square(y_pred), axis=-1)
    jac = (intersection + smooth) / (sum_ - intersection + smooth)
    return jac

def dice_coe(y_true, y_pred, smooth = 100):
    y_true_f = K.flatten(y_true)
    y_pred_f = K.flatten(y_pred)
    intersection = K.sum(y_true_f * y_pred_f)
    return (2. * intersection + smooth) / (K.sum(y_true_f) + K.sum(y_pred_f) + smooth)

from keras.metrics import Accuracy
os.environ['TF_KERAS'] = '1'
from keras.losses import binary_crossentropy
model.compile(loss=binary_crossentropy,
                   metrics=[Accuracy(),
                    dice_coe],
                  optimizer=keras.optimizers.Adam(learning_rate=1e4))

history=model.fit(
    x=x_train,
    y=y_train,
    batch_size=18,
    epochs=100,
    validation_data=(x_test,y_test),

)

loss,dice_coe,accuracy=model.evaluate(x_test,y_test)

backbone="densenet201"
pre_pros=sm.get_preprocessing(backbone)


x_train1=pre_pros(x_train)
x_test2=pre_pros(x_test)

model=sm.Unet(backbone,encoder_weights="imagenet")
model.compile(
    'Adam',
    loss=sm.losses.bce_jaccard_loss,
    metrics=[sm.metrics.iou_score],
)

hist=model.fit(
   x=x_train,
   y=y_train,
   batch_size=16,
   epochs=30,
   validation_data=(x_test, y_test),
)

print("IOU_SCORE",hist.history['iou_score'][-1]*100)
print("LOSS",hist.history['loss'][-1]*100)
print("VAL_IOU_SCORE",hist.history['val_iou_score'][-1]*100)
print("VAL_LOSS",hist.history['val_loss'][-1]*100)

plt.figure(figsize=(30, 5))
plt.subplot(121)
plt.plot(hist.history['iou_score'])
plt.plot(hist.history['val_iou_score'])
plt.title('Model iou_score')
plt.ylabel('iou_score')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')

# Plot training & validation loss values
plt.subplot(122)
plt.plot(hist.history['loss'])
plt.plot(hist.history['val_loss'])
plt.title('Model loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Test'], loc='upper left')
plt.show()

img_num = 34
img_pred = model.predict(x_test[img_num].reshape(1,192,256,3))
plt.figure(figsize=(16,16))
plt.subplot(1,3,1)
plt.imshow(x_test[img_num])
plt.title('Original Image')
plt.subplot(1,3,2)
plt.imshow(y_test[img_num], plt.cm.binary_r)
plt.title('Ground Truth')
plt.subplot(1,3,3)
plt.imshow(img_pred.reshape(192, 256), plt.cm.binary_r)
plt.title('Predicted Output')
plt.show()

backbone="senet154"
pre_pros=sm.get_preprocessing(backbone)


x_train1=pre_pros(x_train)
x_test2=pre_pros(x_test)

model=sm.Unet(backbone,encoder_weights="imagenet")
model.compile(
    'Adam',
    loss=sm.losses.bce_jaccard_loss,
    metrics=[sm.metrics.iou_score],
)

hist=model.fit(
   x=x_train,
   y=y_train,
   batch_size=16,
   epochs=30,
   validation_data=(x_test, y_test),
)

