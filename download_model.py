import os
import tensorflow as tf
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.models import Model

def download_and_save_model():
    # Set logging to avoid too much noise
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    
    print("Initializing ResNet50 download...")
    
    try:
        # Load ResNet50 pre-trained on ImageNet without the classification head
        # include_top=False means we get the feature maps
        # pooling='avg' gives us a 2048-dimensional feature vector
        model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
        
        # Define the models directory
        models_dir = 'models'
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            
        model_path = os.path.join(models_dir, 'resnet50_features.h5')
        print(f"Saving feature extractor to: {model_path}")
        
        # Save as H5 format compatible with the current environment
        model.save(model_path)
        print("Model downloaded and saved locally for offline use.")
        
    except Exception as e:
        print(f"Error during model download: {e}")

if __name__ == "__main__":
    download_and_save_model()
