

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, Model
from tensorflow.keras.applications import EfficientNetV2S
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import confusion_matrix, classification_report
import kagglehub
import cv2
import json
import matplotlib.pyplot as plt

# GPU Configuration
gpus = tf.config.experimental.list_physical_devices('GPU')
if gpus:
  for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)
print(f'GPU devices: {len(gpus)}')

keras.mixed_precision.set_global_policy('mixed_float16')

IMG_SIZE = (224, 224)
BATCH_SIZE = 16

def jpeg_compress(img, quality=90):
    params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, encimg = cv2.imencode('.jpg', img, params)
    return cv2.imdecode(encimg, 1)

def create_8channel_tensor(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f'Cannot load {image_path}')
    
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]
    
    # Resize to input size
    img_resized = cv2.resize(img, IMG_SIZE)
    img_float = img_resized.astype(np.float32) / 255.0
    
    # Channels 1-3: RGB
    rgb = img_float
    
    # ELA (Channels 4-6)
    img_half = cv2.resize(img, (w//2, h//2))
    img_comp = jpeg_compress(img_half, 90)
    img_comp = cv2.resize(img_comp, (w, h))
    img_comp_float = img_comp.astype(np.float32) / 255.0
    ela = np.abs(img_float - cv2.resize(img_comp_float, IMG_SIZE))
    ela = np.clip(ela * 20, 0, 1)  # Scale for visibility
    
    # SRM Noise (Channel 7)
    gray = cv2.cvtColor(img_resized, cv2.COLOR_RGB2GRAY).astype(np.float32)
    laplacian = cv2.Laplacian(gray, cv2.CV_32F)
    srm = np.abs(laplacian)
    srm = srm / (np.max(srm) + 1e-8)
    srm = srm.reshape(IMG_SIZE[0], IMG_SIZE[1], 1)
    
    # Sobel Magnitude (Channel 8)
    sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    sobel_mag = np.sqrt(sobel_x**2 + sobel_y**2)
    sobel_mag = (sobel_mag / (np.max(sobel_mag) + 1e-8)).reshape(IMG_SIZE[0], IMG_SIZE[1], 1)
    
    # Stack 8 channels
    tensor = np.concatenate([rgb, ela, srm, sobel_mag], axis=-1)
    return tensor.astype(np.float32)

@tf.function
def load_8ch(path, label):
    img = tf.numpy_function(create_8channel_tensor, [path], tf.float32)
    img.set_shape([224, 224, 8])
    label = tf.cast(label, tf.float32)
    return img, label

def load_dataset():
    print('Downloading CASIA 2.0...')
    dataset_root = kagglehub.dataset_download('divg07/casia-20-image-tampering-detection-dataset')
    
    authentic = []
    tampered = []
    for root, _, files in os.walk(dataset_root):
        dname = os.path.basename(root)
        if dname == 'Au':
            authentic += [os.path.join(root, f) for f in files if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        elif dname == 'Tp':
            tampered += [os.path.join(root, f) for f in files if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
    
    paths = authentic + tampered
    labels = np.array([0] * len(authentic) + [1] * len(tampered))
    print(f'Found {len(authentic)} authentic, {len(tampered)} tampered images')
    
    # Stratified split
    X_train, X_temp, y_train, y_temp = train_test_split(paths, labels, test_size=0.4, stratify=labels, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, stratify=y_temp, random_state=42)
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test)

def create_datasets(train_data, val_data, test_data):
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = train_data, val_data, test_data
    
    AUTOTUNE = tf.data.AUTOTUNE
    cache_prefix = './cache'
    os.makedirs(cache_prefix, exist_ok=True)
    
    train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train)) \\
        .shuffle(1024) \\
        .map(load_8ch, num_parallel_calls=AUTOTUNE) \\
        .cache(f'{cache_prefix}/train') \\
        .batch(BATCH_SIZE) \\
        .prefetch(AUTOTUNE)
    
    val_ds = tf.data.Dataset.from_tensor_slices((X_val, y_val)) \\
        .map(load_8ch, num_parallel_calls=AUTOTUNE) \\
        .cache(f'{cache_prefix}/val') \\
        .batch(BATCH_SIZE) \\
        .prefetch(AUTOTUNE)
    
    test_ds = tf.data.Dataset.from_tensor_slices((X_test, y_test)) \\
        .map(load_8ch) \\
        .batch(BATCH_SIZE) \\
        .prefetch(AUTOTUNE)
    
    return train_ds, val_ds, test_ds

def build_model():
    inputs = layers.Input(shape=(224, 224, 8))
    
    # Fusion: 8ch -> 3ch
    x = layers.Conv2D(32, 3, activation='relu', padding='same')(inputs)
    x = layers.BatchNormalization()(x)
    x = layers.Conv2D(3, 1, activation='sigmoid', padding='same')(x)
    
    # Backbone
    backbone = EfficientNetV2S(weights='imagenet', include_top=False, input_tensor=x)
    backbone.trainable = True
    
    # Deep unfreezing (last 120 layers)
    for i, layer in enumerate(backbone.layers):
        if i < len(backbone.layers) - 120:
            layer.trainable = False
    
    x = backbone.output
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.5)(x)
    outputs = layers.Dense(1, activation='sigmoid')(x)
    
    model = Model(inputs, outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-4),
        loss='binary_crossentropy',
        metrics=['accuracy', keras.metrics.Recall(name='recall')]
    )
    return model

def train_model(model, train_ds, val_ds):
    \"\"\"High-recall training strategy.\"\"\"
    # Class weights (boost forged recall)
    class_weights = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    class_weight_dict = {0: class_weights[0], 1: class_weights[1] * 1.5}
    
    # Callbacks
    callbacks_list = [
        keras.callbacks.EarlyStopping(monitor='val_recall', mode='max', patience=10, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor='val_recall', factor=0.5, patience=5, min_lr=1e-7)
    ]
    
    history = model.fit(
        train_ds, epochs=50, validation_data=val_ds,
        class_weight=class_weight_dict,
        callbacks=callbacks_list
    )
    
    return history

def evaluate_model(model, test_ds):
    \"\"\"Comprehensive evaluation.\"\"\"
    results = model.evaluate(test_ds, return_dict=True)
    print(f'Test Accuracy: {results[\"accuracy\"]:.4f}')
    print(f'Test Recall: {results[\"recall\"]:.4f}')
    
    y_pred = model.predict(test_ds)
    y_pred_bin = (y_pred > 0.5).astype(int).flatten()
    y_true = np.concatenate([y for _, y in test_ds])
    
    print('\\nConfusion Matrix:\\n', confusion_matrix(y_true, y_pred_bin))
    print('\\nClassification Report:\\n', classification_report(y_true, y_pred_bin))
    
    return results

def predict_forgery(model, image_path):
    \"\"\"Single image inference.\"\"\"
    tensor = create_8channel_tensor(image_path)
    tensor = np.expand_dims(tensor, 0).astype(np.float32)
    pred = model.predict(tensor, verbose=0)[0, 0]
    verdict = 'FORGED' if pred > 0.5 else 'AUTHENTIC'
    return verdict, pred

# MAIN EXECUTION
if __name__ == '__main__':
    # Load data
    print('='*60)
    print('LOADING DATASET...')
    train_data, val_data, test_data = load_dataset()
    
    # Create datasets
    print('CREATING PIPELINES...')
    train_ds, val_ds, test_ds = create_datasets(train_data, val_data, test_data)
    
    # Build & train
    print('BUILDING MODEL...')
    model = build_model()
    
    print('TRAINING...')
    history = train_model(model, train_ds, val_ds)
    
    # Evaluate
    print('EVALUATING...')
    results = evaluate_model(model, test_ds)
    
    # Save
    model.save('id_forgery_detector.h5')
    metadata = {
        'architecture': 'EfficientNetV2S-8ch',
        'unfrozen_layers': 120,
        'test_recall': float(results['recall']),
        'test_accuracy': float(results['accuracy'])
    }
    with open('metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print('\\n✓ PIPELINE COMPLETE')
    print('Model saved: id_forgery_detector.h5')
    print('To predict: verdict, score = predict_forgery(model, \"path.jpg\")')

# Example usage:
# verdict, score = predict_forgery(model, 'sample_id.jpg')
# print(f'{verdict} ({score:.3f})')
