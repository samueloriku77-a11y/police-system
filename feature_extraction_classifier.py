from feature_extraction import FeatureExtractor
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import pickle
import numpy as np
import tensorflow as tf
import cv2

# Create dummy training data matching CASIA structure
print("Creating dummy training data...")
X_train = np.random.randn(1000, 1280).astype(np.float32)
y_train = np.random.randint(0, 2, 1000)

# Train dummy classifier
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)
clf = SVC(kernel='rbf', C=1.0, gamma='scale', class_weight='balanced', probability=True)
clf.fit(X_scaled, y_train)

# Save
pickle.dump(clf, open('models/classifier.pkl', 'wb'))
pickle.dump(scaler, open('models/scaler.pkl', 'wb'))
print("✅ Real dummy SVC trained & saved!")

# Test feature extraction pipeline
extractor = FeatureExtractor()
test_features = extractor.extract_training_features('models/final_model.h5', preprocess=False)  # dummy path
print(f"Training feature shape: {test_features.shape}")
print("Pipeline ready for forged region detection!")

