"""
Test script to verify model integration for feature extraction and similarity search.
Run this to ensure the model is properly connected with the files.
"""

import os
import sys
import numpy as np
import pickle

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_model_loading():
    """Test if the model can be loaded properly"""
    print("=" * 60)
    print("TEST 1: Model Loading")
    print("=" * 60)
    
    try:
        from feature_extraction import FeatureExtractor
        from config import MODEL_PATH, MODEL_METADATA_PATH
        
        # Initialize feature extractor
        extractor = FeatureExtractor(model_path=MODEL_PATH, metadata_path=MODEL_METADATA_PATH)
        
        print(f"✅ Model loaded successfully")
        print(f"   Model type: {type(extractor.model)}")
        
        try:
            print(f"   Model input shape: {extractor.model.input_shape}")
            print(f"   Model output shape: {extractor.model.output_shape}")
            print(f"   Ready for feature extraction")
        except Exception as shape_error:
            print(f"   ⚠️  Could not access shapes: {shape_error}")
        
        return True
    except Exception as e:
        print(f"❌ Model loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_feature_extraction():
    """Test feature extraction from a sample image"""
    print("\n" + "=" * 60)
    print("TEST 2: Feature Extraction")
    print("=" * 60)
    
    try:
        from feature_extraction import FeatureExtractor
        from preprocessing import ImagePreprocessor
        
        # Initialize

        extractor = FeatureExtractor()
        preprocessor = ImagePreprocessor()

        
        # Check if there's a sample image in originals folder
        originals_dir = 'originals'
        if not os.path.exists(originals_dir):
            print(f"⚠️  Originals directory not found: {originals_dir}")
            print("   Creating sample test...")
            
            # Create a simple test image
            import cv2
            os.makedirs(originals_dir, exist_ok=True)
            test_img = np.random.randint(0, 255, (768, 1024), dtype=np.uint8)
            cv2.imwrite(os.path.join(originals_dir, 'test_sample.png'), test_img)
            test_path = os.path.join(originals_dir, 'test_sample.png')
        else:
            # Find any image in originals
            images = [f for f in os.listdir(originals_dir) 
                     if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            
            if images:
                test_path = os.path.join(originals_dir, images[0])
                print(f"   Using test image: {images[0]}")
            else:
                print("⚠️  No images in originals folder")
                return False
        
        # Extract features
        features = extractor.extract_features(test_path, preprocess=True)
        
        print(f"✅ Feature extraction successful")
        print(f"   Feature shape: {features.shape}")
        print(f"   Feature dtype: {features.dtype}")
        print(f"   Feature sample (first 5): {features[:5]}")
        
        return True
    except Exception as e:
        print(f"❌ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_similarity_calculation():
    """Test similarity calculation between embeddings"""
    print("\n" + "=" * 60)
    print("TEST 3: Similarity Calculation")
    print("=" * 60)
    
    try:
        from similarity import SimilarityCalculator
        
        # Initialize
        calculator = SimilarityCalculator()
        
        # Create two random embeddings
        emb1 = np.random.randn(512).astype(np.float32)
        emb2 = np.random.randn(512).astype(np.float32)
        
        # Normalize embeddings (as the model outputs)
        emb1 = emb1 / np.linalg.norm(emb1)
        emb2 = emb2 / np.linalg.norm(emb2)
        
        # Calculate similarities
        cosine_sim = calculator.calculate_cosine_similarity(emb1, emb2)
        euclidean_sim = calculator.calculate_euclidean_similarity(emb1, emb2)
        
        # Test with identical embeddings
        cosine_same = calculator.calculate_cosine_similarity(emb1, emb1)
        
        print(f"✅ Similarity calculation successful")
        print(f"   Cosine similarity (different): {cosine_sim:.4f}")
        print(f"   Euclidean similarity (different): {euclidean_sim:.4f}")
        print(f"   Cosine similarity (identical): {cosine_same:.4f}")
        
        return True
    except Exception as e:
        print(f"❌ Similarity calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_integration():
    """Test database integration for reference documents"""
    print("\n" + "=" * 60)
    print("TEST 4: Database Integration")
    print("=" * 60)
    
    try:
        # Check if database is set up
        from db import db, ReferenceDocument
        from app import app
        
        with app.app_context():
            # Try to query reference documents
            refs = ReferenceDocument.query.all()
            
            print(f"✅ Database connection successful")
            print(f"   Reference documents in DB: {len(refs)}")
            
            if refs:
                for ref in refs:
                    print(f"   - {ref.name}: embedding={'Yes' if ref.embedding_data else 'No'}")
            else:
                print("   ⚠️  No reference documents found in database")
                print("   Upload reference documents via admin panel to enable similarity search")
            
            return True
    except Exception as e:
        print(f"❌ Database integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False



    print("\n" + "=" * 60)
    print("TEST 5: Full Pipeline (Image → Feature → Similarity)")
    print("=" * 60)
    
    try:
        from feature_extraction import FeatureExtractor
        from similarity import SimilarityCalculator
        from preprocessing import ImagePreprocessor
        import cv2
        
        # Initialize components
        extractor = FeatureExtractor(use_pretrained=True)
        calculator = SimilarityCalculator()
        preprocessor = ImagePreprocessor()
        
        # Create a test image
        test_image = np.random.randint(0, 255, (768, 1024), dtype=np.uint8)
        test_path = 'uploads/test_pipeline.png'
        os.makedirs('uploads', exist_ok=True)
        cv2.imwrite(test_path, test_image)
        
        # Extract features
        embedding = extractor.extract_features(test_path, preprocess=True)
        
        # Create mock reference embeddings
        reference_embeddings = {
            'doc1.npy': np.random.randn(512).astype(np.float32),
            'doc2.npy': np.random.randn(512).astype(np.float32),
        }
        
        # Normalize reference embeddings
        for key in reference_embeddings:
            reference_embeddings[key] = reference_embeddings[key] / np.linalg.norm(reference_embeddings[key])
        
        # Compare with references
        results = calculator.compare_with_references(embedding, reference_embeddings)
        
        print(f"✅ Full pipeline successful")
        print(f"   Extracted embedding shape: {embedding.shape}")
        print(f"   Best match: {results['best_match']}")
        print(f"   Best similarity: {results['best_similarity']:.4f}")
        
        # Clean up
        os.remove(test_path)
        
        return True
    except Exception as e:
        print(f"❌ Full pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MODEL INTEGRATION TEST SUITE")
    print("=" * 60 + "\n")
    
    results = {
        "Model Loading": test_model_loading(),
        "Feature Extraction": test_feature_extraction(),
        "Similarity Calculation": test_similarity_calculation(),
        "Database Integration": test_database_integration(),
        "Full Pipeline": False,
        "Forgery Detection": False,
        "8-Channel Pipeline": False,

    }
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("🎉 All tests passed! Model is properly connected.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)


